from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import os

#Input with validation
def define_input():
    while True:
        print("Enter all parameters in format: input players folder path, EB shapefile path, output folder path")
        print("Example: \"C:/Users/Desktop/output/players\", \"C:/Users/Desktop/output/EB.shp\", \"C:/Users/Desktop/output/local_metrics\"")
        
        user_input = input().strip()
        
        if not user_input:
            print("Error: Input cannot be empty.")
            continue
            
        try:
            parts = [part.strip() for part in user_input.split(',')]
            
            if len(parts) != 3:
                print(f"Error: Expected 3 parameters, got {len(parts)}. Please check your input format.")
                continue
            
            input_folder = Path(parts[0].strip().strip('"'))
            grid_file = Path(parts[1].strip().strip('"'))
            output_folder = Path(parts[2].strip().strip('"'))
            
            #Validate input folder
            if not input_folder.exists() or not input_folder.is_dir():
                print(f"Error: Input folder does not exist or is not a directory: {input_folder}")
                continue
            
            #Validate EB shapefile
            if not grid_file.exists() or not grid_file.is_file():
                print(f"Error: EB shapefile does not exist: {grid_file}")
                continue
            if not grid_file.suffix.lower() == ".shp":
                print("Error: EB file must have a .shp extension.")
                continue
            
            #Validate or create output folder
            if not output_folder.exists():
                try:
                    output_folder.mkdir(parents=True, exist_ok=True)
                    print(f"Created output directory: {output_folder}")
                except Exception as e:
                    print(f"Error: Could not create output directory: {e}")
                    continue
            
            return input_folder, grid_file, output_folder
            
        except Exception as e:
            print(f"Error parsing input: {str(e)}")
            print("Please check your input format and try again.")

input_folder, grid_layer_path, output_folder = define_input()
print("Input file paths collected successfully.")

#Create output directory if it doesn't exist
output_folder.mkdir(parents=True, exist_ok=True)
print(f"Output directory created or already exists: {output_folder}")

#Load EB layer and select relevant columns
print("Loading grid layer shapefile...")
grid_gdf = gpd.read_file(grid_layer_path)[['geometry', 'distance', 'EB_PPA']]
print(f"Number of polygons in grid_gdf: {len(grid_gdf)}")

#Collect all shapefile paths from input folder
input_files = [f for f in input_folder.glob("*.shp")]
print(f"Found {len(input_files)} shapefile(s) in input folder.")

#Process data
print("Starting data processing for shapefiles...")
for input_file in input_files:
    layer_name = input_file.stem
    print(f"\nProcessing shapefile: {input_file.name}...")
    
    #Load shooting data
    points_gdf = gpd.read_file(input_file)
    print(f"Number of points in {input_file.name}: {len(points_gdf)}")

    #Match CRS's
    if points_gdf.crs != grid_gdf.crs:
        print(f"Converting CRS for {input_file.name} to match grid CRS...")
        points_gdf = points_gdf.to_crs(grid_gdf.crs)
    else:
        print(f"CRS of {input_file.name} matches grid CRS.")

    #Calculate points (PTS)
    print(f"Calculating points scored for {input_file.name}...")
    if 'action' in points_gdf.columns and 'made' in points_gdf.columns:
        points_gdf['PTS'] = points_gdf['action'] * points_gdf['made']
    else:
        print(f"Columns 'action' or 'made' missing in {input_file.name}. Setting PTS=0.")
        points_gdf['PTS'] = 0

    #Count shot attempts (FGA)
    joined_gdf = gpd.sjoin(grid_gdf, points_gdf[['geometry']], how="inner", predicate="contains")
    print(f"Calculating shot attempts (FGA) for {input_file.name}...")
    fga_df = joined_gdf.groupby(joined_gdf.index).size().reset_index(name='FGA')

    result_gdf = grid_gdf.loc[fga_df['index']].copy()
    result_gdf['FGA'] = fga_df['FGA'].values

    #Calculate Points Per Basket (PPB)
    print(f"Calculating Points Per Basket (PPB) for {input_file.name}...")
    if 'distance' in grid_gdf.columns:
        result_gdf['PPB'] = np.where(grid_gdf.loc[result_gdf.index, 'distance'] > 6.62, 3, 2)
    else:
        print(f"Column 'distance' missing. Setting PPB=2.")
        result_gdf['PPB'] = 2

    #Calculate Expected local Points (ELPTS)
    print(f"Calculating expected local points (ELPTS) for {input_file.name}...")
    if 'EB_PPA' in grid_gdf.columns:
        result_gdf['ELPTS'] = grid_gdf.loc[result_gdf.index, 'EB_PPA'] * result_gdf['FGA']
    else:
        print(f"Column 'EB_PPA' missing. Setting EB_PPA=1.")
        result_gdf['ELPTS'] = 1 * result_gdf['FGA']

    #Calculate sum of points in grid cells (PTS_sum)
    joined_summary = gpd.sjoin(result_gdf, points_gdf[['geometry', 'PTS']], how="left", predicate="contains")
    pts_sum = joined_summary.groupby(joined_summary.index)['PTS'].sum().reset_index(name='PTS')
    result_gdf['PTS'] = pts_sum['PTS'].fillna(0).values

    #Calculate local Points Relative to league Average (LPRLA)
    print(f"Calculating local points relative to league average (LPRLA) for {input_file.name}...")
    result_gdf['LPRLA'] = result_gdf['PTS'] - result_gdf['ELPTS']

    #Calculate local Points per Attempt (LPPA)
    print(f"Calculating local points per attempt (LPPA) for {input_file.name}...")
    result_gdf['LPPA'] = result_gdf['PTS'] / result_gdf['FGA'].replace(0, np.nan)

    #Calculate local Spatial Shooting Efficiency (LSScE)
    print(f"Calculating local spatial shooting efficiency (LSScE) for {input_file.name}...")
    if 'EB_PPA' in grid_gdf.columns:
        result_gdf['LSScE'] = result_gdf['LPPA'] - grid_gdf.loc[result_gdf.index, 'EB_PPA']
    else:
        result_gdf['LSScE'] = result_gdf['LPPA'] - 1

    print(f"Number of rows in result_gdf for {input_file.name}: {len(result_gdf)}")

    #Save results as shapefiles and CSVs
    final_output_name = f"{layer_name}_localmetrics"
    result_gdf.to_file(output_folder / f"{final_output_name}.shp")
    result_gdf.to_csv(output_folder / f"{final_output_name}.csv", index=False)

    print(f"Processed {input_file.name}. Files saved in: {output_folder}")

print("Data processing completed for all shapefiles.")

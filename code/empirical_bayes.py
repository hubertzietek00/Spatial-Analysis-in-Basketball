import numpy as np
from scipy.spatial import distance
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import os
from pathlib import Path

#Input with validation
def define_input():
    while True:
        print("Enter all parameters in format: csv file path, grid file path, output file path")
        print("Example: \"C:/Users/Desktop/output/shooting_data.csv\", \"C:/Users/Desktop/grid_file.shp\", \"C:/Users/Desktop/output/EB.shp\"")
        
        user_input = input().strip()
        
        if not user_input:
            print("Error: Input cannot be empty.")
            continue
            
        try:
            parts = [part.strip() for part in user_input.split(',')]
            
            if len(parts) != 3:
                print(f"Error: Expected 3 parameters, got {len(parts)}. Please check your input format.")
                continue
            
            csv_file = parts[0].strip().strip('"')
            grid_file = parts[1].strip().strip('"')
            output_file = parts[2].strip().strip('"')
            
            #Validate file paths
            if not csv_file or not grid_file or not output_file:
                print("Error: All file paths must be filled.")
                continue
                
            if not csv_file.lower().endswith('.csv'):
                print("Error: CSV file must have a .csv extension.")
                continue
                
            if not grid_file.lower().endswith('.shp'):
                print("Error: Grid file must have a .shp extension.")
                continue
                
            if not output_file.lower().endswith('.shp'):
                print("Error: Output file must have a .shp extension.")
                continue
            
            #Check if input files exist
            if not os.path.isfile(csv_file):
                print(f"Error: CSV file does not exist: {csv_file}")
                continue
                
            if not os.path.isfile(grid_file):
                print(f"Error: Grid shapefile does not exist: {grid_file}")
                continue
            
            #Validate output directory
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                    print(f"Created output directory: {output_dir}")
                except Exception as e:
                    print(f"Error: Could not create output directory: {e}")
                    continue
            
            #Basket coordinates
            basket_coords = (0, 12.425)
            
            return csv_file, grid_file, output_file, basket_coords
            
        except Exception as e:
            print(f"Error parsing input: {str(e)}")
            print("Please check your input format and try again.")

#Prepare data for Empirical Bayes analysis
def prepare_data_for_eb(csv_path, grid_shp_path):
    print("Checking existence of input files...")
    if not os.path.exists(csv_path): 
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not os.path.exists(grid_shp_path): 
        raise FileNotFoundError(f"Shapefile not found: {grid_shp_path}")

    print("Loading CSV file...")
    try:
        shots_df = pd.read_csv(csv_path)
    except Exception as e:
        raise ValueError(f"Error while loading csv file: {e}")

    #Validate data
    required_columns = ['x', 'y', 'action', 'made']
    missing_columns = [col for col in required_columns if col not in shots_df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    if shots_df.empty:
        raise ValueError("CSV file is empty.")

    if not shots_df['made'].isin([0, 1]).all():
        raise ValueError("Column 'made' must contain only 0 or 1 values.")

    if shots_df['action'].min() <= 0:
        raise ValueError("Column 'action' must contain positive values.")

    print("Calculating points scored...")
    shots_df['points'] = shots_df['action'] * shots_df['made'] 

    #Make point geometry 
    try:
        geometry = [Point(xy) for xy in zip(shots_df['x'], shots_df['y'])]
        shots_gdf = gpd.GeoDataFrame(shots_df, geometry=geometry, crs='EPSG:3857')
    except Exception as e:
        raise ValueError(f"Error while making point geometries: {e}")

    print("Loading grid shapefile...")
    try:
        grid_gdf = gpd.read_file(grid_shp_path)
    except Exception as e:
        raise ValueError(f"Error while loading shapefile: {e}")

    if grid_gdf.empty:
        raise ValueError("Grid shapefile is empty.")

    if grid_gdf.crs != 'EPSG:3857':
        grid_gdf = grid_gdf.to_crs('EPSG:3857')

    shots_with_grid = gpd.sjoin(shots_gdf, grid_gdf, how='left', predicate='within')

    unassigned_shots = shots_with_grid['index_right'].isna().sum()
    if unassigned_shots > 0:
        print(f"Note: {unassigned_shots} shots were not assigned to any grid cell.")

    shots_assigned = shots_with_grid.dropna(subset=['index_right'])

    if shots_assigned.empty:
        raise ValueError("No shots were assigned to any grid cell. Check coordinate system compatibility.")

    #Calculate statistics for grid cells
    print("Calculating statistics for grid cells...")
    grid_stats = shots_assigned.groupby('index_right').agg({
        'points': 'sum',
        'action': 'count'
    }).reset_index()

    grid_stats = grid_stats.rename(columns={
        'action': 'attempts',
        'points': 'points'
    })

    #Calculate Points Per Attempt (PPA)
    print("Calculating Points Per Attempt (PPA)...")
    grid_stats['PPA'] = np.where(
        grid_stats['attempts'] > 0,
        grid_stats['points'] / grid_stats['attempts'],
        0
    )

    result_gdf = grid_gdf.merge(grid_stats, left_index=True, right_on='index_right', how='left')

    result_gdf['attempts'] = result_gdf['attempts'].fillna(0).astype(int)
    result_gdf['points'] = result_gdf['points'].fillna(0).astype(int)
    result_gdf['PPA'] = result_gdf['PPA'].fillna(0)

    if 'left' not in result_gdf.columns:
        print("Calculating grid bounds...")
        bounds = result_gdf.bounds
        result_gdf['left'] = bounds['minx']
        result_gdf['right'] = bounds['maxx']
        result_gdf['bottom'] = bounds['miny']
        result_gdf['top'] = bounds['maxy']

    print("Data preparation for Empirical Bayes completed.")
    return result_gdf

#Perform main Empirical Bayes analysis
def do_eb(csv_path, grid_shp_path, output_path='EB.shp', basket_coords=(0, 12.425)):
    print("Starting Empirical Bayes analysis...")
    grid_data = prepare_data_for_eb(csv_path, grid_shp_path)

    grid_data['x'] = (grid_data['left'] + grid_data['right']) / 2
    grid_data['y'] = (grid_data['bottom'] + grid_data['top']) / 2

    grid_data['dist_to_basket'] = np.sqrt(
        (grid_data['x'] - basket_coords[0]) ** 2 +
        (grid_data['y'] - basket_coords[1]) ** 2
    )

    numeric_columns = ['attempts', 'points', 'PPA']
    for col in numeric_columns:
        grid_data[col] = pd.to_numeric(grid_data[col], errors='coerce').fillna(0)

    invalid_grids = grid_data[grid_data['points'] > grid_data['attempts'] * 3]
    if not invalid_grids.empty:
        print("Warning: Some grids have invalid points (points > attempts * 3).")

    active_grids = grid_data[grid_data['attempts'] > 0].copy()

    if active_grids.empty:
        raise ValueError("No grids with attempts for analysis.")

    #Define function to get neighborhood parameters for each cell
    def get_neighborhood_params(row, gdf):
        d = row['dist_to_basket']
        if d < 9.144:  #Close to basket
            equidistant_range = 0.3658
            close_range = 1.524
        else:  #Far from basket - larger neighborhood
            extra_feet = d - 9.144
            equidistant_range = 0.3658 + (0.1524 * extra_feet)
            close_range = 1.524 + (0.3048 * extra_feet)

        neighborhood = gdf[
            (abs(gdf['dist_to_basket'] - d) <= equidistant_range) &
            (distance.cdist([[row['x'], row['y']]], gdf[['x', 'y']].values)[0] <= close_range) &
            (gdf['attempts'] > 0)
        ]

        return neighborhood

    #Set up Empirical Bayes parameters
    print("Initializing Empirical Bayes parameters...")
    phi_values = []     
    w_hat_values = []  
    theta_values = []    

    #Calculate Empirical Bayes parameters for each active cell
    print("Calculating Empirical Bayes parameters for active grids...")
    for idx, row in active_grids.iterrows():
        print(f"Processing grid {idx}...")
        neighborhood = get_neighborhood_params(row, active_grids)

        if neighborhood.empty:
            print(f"No neighbors found for grid {idx}, using raw PPA.")
            phi_values.append(0)
            w_hat_values.append(0)
            theta_values.append(row['PPA'])
            continue

        #Calculate neighborhood statistics
        print(f"Calculating statistics for neighborhood of grid {idx}...")
        total_shots = neighborhood['attempts'].sum()
        total_makes = neighborhood['points'].sum()

        gamma_i = total_makes / total_shots if total_shots > 0 else 0

        #Calculate variance
        print(f"Calculating variance for grid {idx}...")
        n_bar_j = neighborhood['attempts'].mean()
        n_j = neighborhood['attempts']
        r_j = neighborhood['PPA']

        gamma_j = neighborhood['points'] / neighborhood['attempts']
        gamma_j = gamma_j.replace([np.inf, -np.inf], 0).fillna(0)

        #Calculate variance parameter
        numerator = np.sum(n_j * (r_j - gamma_j) ** 2)
        denominator = np.sum(n_j)

        if denominator > 0 and n_bar_j > 0:
            phi_i = (numerator / denominator) - (gamma_i / n_bar_j)
            phi_i = max(0, phi_i)
        else:
            phi_i = 0

        phi_values.append(phi_i)

        #Calculate shrinkage weight
        print(f"Calculating shrinkage weight for grid {idx}...")
        n_i = row['attempts']
        if n_i > 0 and (phi_i + gamma_i / n_i) != 0:
            w_hat_i = phi_i / (phi_i + gamma_i / n_i)
            w_hat_i = max(0, min(1, w_hat_i))
        else:
            w_hat_i = 0

        w_hat_values.append(w_hat_i)

        #Calculate smoothed PPA
        print(f"Calculating smoothed PPA for grid {idx}...")
        r_i = row['PPA']
        theta_i = w_hat_i * r_i + (1 - w_hat_i) * gamma_i
        theta_values.append(theta_i)

        if theta_i > 3 or theta_i < 0:
            print(f"Note - Grid {idx}: theta_i={theta_i:.3f} (r_i={r_i:.3f}, gamma_i={gamma_i:.3f})")

    #Add Empirical Bayes parameters to active grids
    print("Adding Empirical Bayes parameters to active grids...")
    active_grids['CellVar'] = phi_values
    active_grids['ShrinkWt'] = w_hat_values
    active_grids['EB_PPA'] = theta_values

    #Merge results with full grid data
    grid_data = grid_data.merge(
        active_grids[['CellVar', 'ShrinkWt', 'EB_PPA']],
        left_index=True,
        right_index=True,
        how='left'
    )

    #Set Empirical Bayes parameters to 0 for grids without attempts
    grid_data['CellVar'] = grid_data['CellVar'].where(grid_data['attempts'] > 0, 0)
    grid_data['ShrinkWt'] = grid_data['ShrinkWt'].where(grid_data['attempts'] > 0, 0)
    grid_data['EB_PPA'] = grid_data['EB_PPA'].where(grid_data['attempts'] > 0, 0)

    #Save results to shapefile
    print("Saving results to shapefile...")
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            print(f"Creating output directory: {output_dir}")
            os.makedirs(output_dir)
            
        grid_data = grid_data.rename(columns={'dist_to_basket': 'distance'})    

        grid_data.to_file(output_path)

    except Exception as e:
        print(f"Error while saving: {e}")
        raise

    print("Empirical Bayes analysis completed.")
    return grid_data

#Run main block with single input
if __name__ == "__main__":

    #Collect all parameters in one input
    csv_file, grid_file, output_file, basket_coords = define_input()
    
    print(f"Parameters set:")
    print(f"CSV file: {csv_file}")
    print(f"Grid file: {grid_file}")
    print(f"Output file: {output_file}")
    print(f"Basket coordinates: {basket_coords}")

    #Run Empirical Bayes analysis
    try:
        result = do_eb(
            csv_path=csv_file,
            grid_shp_path=grid_file,
            output_path=output_file,
            basket_coords=basket_coords
        )
        print(f"Analysis completed successfully! Results saved to: {output_file}")
    except Exception as e:
        print(f"Error during analysis: {e}")

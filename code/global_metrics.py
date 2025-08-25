import os
import pandas as pd
import numpy as np

#Input with validation
def define_input():
    while True:
        print("Enter both parameters in format: input folder path, output folder path")
        print("Example: \"C:/Users/Desktop/output/local_metrics\", \"C:/Users/Desktop/output/global_metrics\"")
        user_input = input().strip()

        if not user_input:
            print("Error: Input cannot be empty.")
            continue

        try:
            parts = [part.strip() for part in user_input.split(',')]
            if len(parts) != 2:
                print(f"Error: Expected 2 parameters, got {len(parts)}. Please check your input format.")
                continue

            input_folder = parts[0].strip().strip('"')
            output_folder = parts[1].strip().strip('"')

            #Validate input folder
            if not os.path.isdir(input_folder):
                print(f"Error: Input folder does not exist: {input_folder}")
                continue

            #Validate or create output folder
            if not os.path.exists(output_folder):
                try:
                    os.makedirs(output_folder)
                    print(f"Created output folder: {output_folder}")
                except Exception as e:
                    print(f"Error: Could not create output folder: {e}")
                    continue

            return input_folder, output_folder

        except Exception as e:
            print(f"Error parsing input: {str(e)}")
            print("Please check your input format and try again.")


input_folder, output_folder = define_input()
print("Folder paths collected successfully.")

#Collect list of CSV files
print(f"Scanning input folder for CSV files...")
csv_files = [f for f in os.listdir(input_folder) if f.endswith('.csv')]
print(f"Found {len(csv_files)} CSV file(s) in input folder.")

if not csv_files:
    print(f"No CSV files found in {input_folder}.")
    exit()

#Process each CSV file
print("Starting processing of CSV files...")
for csv_file in csv_files:
    input_path = os.path.join(input_folder, csv_file)

    #Load CSVs
    try:
        df = pd.read_csv(input_path, sep=',')
        print(f"Successfully loaded {csv_file}")
    except Exception as e:
        print(f"Failed to load {csv_file}: {e}")
        continue

    #Clean numerical data
    for column in df.columns[1:]:
        if pd.api.types.is_numeric_dtype(df[column]):
            df[column] = df[column].apply(lambda x: str(x).replace('.', ',') if pd.notnull(x) else x)
            df[column] = pd.to_numeric(df[column].str.replace(',', '.'), errors='coerce')

    #Calculate metrics
    print(f"Calculating metrics for {csv_file}...")
    sum_elpts = df['ELPTS'].sum() if 'ELPTS' in df.columns else 0
    sum_pts_sum = df['PTS'].sum() if 'PTS' in df.columns else 0
    sum_fga = df['FGA'].sum() if 'FGA' in df.columns else 0
    made_shots = (df['PTS'] / df['PPB']).sum() if ('PTS' in df.columns and 'PPB' in df.columns) else 0

    if len(df.columns) >= 7:
        fga_col = df.columns[3]
        ppb_col = df.columns[4]
        pts_sum_col = df.columns[6]

        #Two-pointers
        print(f"Calculating two-point shot metrics for {csv_file}...")
        two_pt_made = df[(df[ppb_col] == 2) & (df[pts_sum_col] > 0)][pts_sum_col].sum() / 2
        two_pt_fga = df[df[ppb_col] == 2][fga_col].sum()
        two_pt_pct = (two_pt_made / two_pt_fga * 100) if two_pt_fga > 0 else 0

        #Three-pointers
        print(f"Calculating three-point shot metrics for {csv_file}...")
        three_pt_made = len(df[(df[ppb_col] == 3) & (df[pts_sum_col] > 0)])
        three_pt_fga = df[df[ppb_col] == 3][fga_col].sum()
        three_pt_pct = (three_pt_made / three_pt_fga * 100) if three_pt_fga > 0 else 0

        fga_sum = df[fga_col].sum()

        #eFG%
        def calculate_efg_pct(df, fga_col, ppb_col, pts_sum_col):
            temp_calc = 0.0
            ppb_3_sum = 0.0
            for _, row in df.iterrows():
                if row[ppb_col] == 3:
                    value = row[pts_sum_col] / 3
                    temp_calc += value
                    ppb_3_sum += value
                elif row[ppb_col] == 2:
                    temp_calc += row[pts_sum_col] / 2

            fga_total = df[fga_col].sum()
            efg_pct = (((temp_calc + ppb_3_sum * 0.5) / fga_total)*100) if fga_total != 0 else 0
            return efg_pct

        print(f"Calculating Effective Field Goal Percentage for {csv_file}...")
        efg_pct = calculate_efg_pct(df, fga_col, ppb_col, pts_sum_col)

    else:
        two_pt_pct = 0
        three_pt_pct = 0
        fga_sum = 0
        efg_pct = 0

    #Final metrics
    print(f"Calculating final metrics for {csv_file}...")
    eppa = sum_elpts / sum_fga if sum_fga != 0 else 0
    ppa = sum_pts_sum / sum_fga if sum_fga != 0 else 0
    ssce = ppa - eppa
    prla = ssce * sum_fga
    FG_pct = (made_shots / df['FGA'].sum()) * 100 if ('PTS' in df.columns and 'FGA' in df.columns and df['FGA'].sum() > 0) else 0

    #Create DataFrame with metrics
    stats_df = pd.DataFrame({
        'EPPA': [eppa],
        'PPA': [ppa],
        'SScE': [ssce],
        'PRLA': [prla],
        'FG_pct': [FG_pct],
        '2FG_pct': [two_pt_pct],
        '3FG_pct': [three_pt_pct],
        'eFG_pct': [efg_pct],
        'FGA_sum': [fga_sum],
    })

    df_with_stats = pd.concat([df, stats_df], axis=1)

    #Save results
    print(f"Saving results for {csv_file}...")
    output_file = os.path.splitext(csv_file)[0].replace("_localmetrics", "") + '_globalmetrics.xlsx'
    output_path = os.path.join(output_folder, output_file)

    try:
        df_with_stats.to_excel(output_path, index=False, float_format='%.15g')
        print(f"Successfully saved {output_file} in {output_path}")
    except Exception as e:
        print(f"Failed to save {output_file}: {e}")

print("Data processing and saving completed for all CSV files.")

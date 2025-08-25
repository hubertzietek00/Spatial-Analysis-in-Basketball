import os
import pandas as pd

#Input with validation
def define_input():
    while True:
        print("Enter parameters in format: folder path, output Excel file path")
        print("Example: \"C:/Users/Desktop/output/global_metrics\", \"C:/Users/Desktop/output/global_metrics/statbook.xlsx\"")
        user_input = input().strip()

        if not user_input:
            print("Error: Input cannot be empty.")
            continue

        try:
            parts = [part.strip() for part in user_input.split(',')]
            if len(parts) != 2:
                print(f"Error: Expected 2 parameters, got {len(parts)}. Please check your input format.")
                continue

            folder_path = parts[0].strip().strip('"')
            output_file = parts[1].strip().strip('"')

            #Validate folder path
            if not os.path.exists(folder_path):
                print(f"Error: Folder path does not exist: {folder_path}")
                continue

            #Validate output file extension
            if not output_file.lower().endswith('.xlsx'):
                print("Error: Output file must have a .xlsx extension.")
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

            return folder_path, output_file

        except Exception as e:
            print(f"Error parsing input: {str(e)}")
            print("Please check your input format and try again.")


#Process excel files
def process_excel_files(folder_path, output_filename):
    print("Starting processing of Excel files...")
    all_data = []

    #Collect excel files
    print(f"Scanning folder for Excel files: {folder_path}")
    excel_files = [f for f in os.listdir(folder_path) if f.endswith(('.xls', '.xlsx'))]
    print(f"Found {len(excel_files)} Excel file(s) in folder.")

    if not excel_files:
        print(f"No Excel files found in {folder_path}.")
        return

    #Process each excel file
    for file in excel_files:
        file_path = os.path.join(folder_path, file)

        try:
            df = pd.read_excel(file_path, header=None)
            print(f"Successfully loaded {file}")
        except Exception as e:
            print(f"Failed to load {file}: {e}")
            continue

        #Remove first 10 columns (with local metrics)
        df = df.iloc[:, 10:]

        #Select only second row
        if not df.empty:
            df = df.iloc[1:2]
        else:
            print(f"File {file} is empty, skipping...")
            continue

        #Insert player name
        player_name = os.path.splitext(file)[0]
        df.insert(0, "player", player_name)

        all_data.append(df)

    if not all_data:
        print("No valid data to process.")
        return

    #Merge all DataFrames
    merged_df = pd.concat(all_data, ignore_index=True)

    #Assign final column names 
    column_names = [
        "player", "EPPA", "PPA", "SScE", "PRLA", "FG_pct", "2FG_pct", "3FG_pct", "eFG_pct", "FGA"]
    merged_df.columns = column_names

    #Save excel file
    try:
        merged_df.to_excel(output_filename, index=False)
        print(f"Output file saved as: {output_filename}")
    except Exception as e:
        print(f"Failed to save {output_filename}: {e}")


#Main
if __name__ == "__main__":
    folder_path, output_file = define_input()
    print("Input parameters collected successfully.")
    process_excel_files(folder_path, output_file)
    print("Processing completed.")

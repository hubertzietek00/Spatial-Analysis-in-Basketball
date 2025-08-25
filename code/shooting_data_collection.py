import requests
import re
import pandas as pd
import os
import geopandas as gpd
from shapely.geometry import Point

#Input with validation
def define_input():
    while True:
        print("Enter all parameters in format: league, clue, start_id, end_id, output folder, csv filename")
        print("Example: POL, 2 Liga, 2310000, 2450000, \"C:/Users/Desktop/output\", shooting_data.csv")
        
        user_input = input().strip()
        
        if not user_input:
            print("Error: Input cannot be empty.")
            continue
            
        try:
            parts = [part.strip() for part in user_input.split(',')]
            
            if len(parts) != 6:
                print(f"Error: Expected 6 parameters, got {len(parts)}. Please check your input format.")
                continue
            
            league = parts[0].strip('"')
            clue = parts[1].strip('"')
            
            # Validate start_id and end_id
            try:
                start_id = int(parts[2].strip('"'))
                end_id = int(parts[3].strip('"'))
            except ValueError:
                print("Error: start_id and end_id must be valid integers.")
                continue
            
            output_folder = parts[4].strip().strip('"')
            export_filename = parts[5].strip().strip('"')
            
            #Basic validation
            if not league or not clue or not output_folder or not export_filename:
                print("Error: All fields must be filled.")
                continue
                
            if start_id > end_id:
                print("Error: start_id cannot be greater than end_id.")
                continue
            
            return league, clue, start_id, end_id, output_folder, export_filename
            
        except Exception as e:
            print(f"Error parsing input: {str(e)}")
            print("Please check your input format and try again.")

#Collect data from user
league, clue, start_id, end_id, output_folder, export_filename = define_input()
export = os.path.join(output_folder, export_filename)
print(f"Parameters set: League={league}, Clue={clue}, Start ID={start_id}, End ID={end_id}")
print(f"Output folder: {output_folder}, Filename: {export_filename}")
print("User input collection completed.")

#Find games' URLs
print("Searching for game URLs...")
baseurl = 'https://www.fibalivestats.com/u/{}'.format(league)
old_urls = []
for g_id in range(start_id, end_id + 1):
    url = "{}/{}/".format(baseurl, g_id)
    resp = requests.get(url)
    if resp.status_code == 200 and resp.text.find(clue) > -1:
        print(f"Valid URL found: {url}")
        old_urls.append(url)
    else:
        print(f"Skipping URL: {url} (Clue not found)")
print(f"Found {len(old_urls)} valid URLs.")

#Convert URLs to JSON data
def convert_urls(old_urls):
    print("Converting URLs to JSON format...")
    new_urls = []
    pattern = re.compile(r"https://www\.fibalivestats\.com/u/\w+/(\d+)/")
    
    for url in old_urls:
        match = pattern.match(url)
        if match:
            match_id = match.group(1)
            new_url = f"https://fibalivestats.dcd.shared.geniussports.com/data/{match_id}/data.json"
            new_urls.append(new_url)
        else:
            print(f"Failed to match URL: {url}")
    print("URL conversion completed.")
    return new_urls

json_urls = convert_urls(old_urls)
for url in json_urls:
    print(f"JSON URL: {url}")

#Fetch JSON data from a URL
def url_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        print(f"Successfully fetched data from: {url}")
        return response.json()
    else:
        print(f"Error. Status code: {response.status_code} for {url}")
        return None

#Convert and rotate court coordinates
def coords(x, y):
    minX, maxX = -7.5, 7.5
    minY, maxY = -14.0, 14.0
    coord_x = x / 100
    coord_y = y / 100
    rot_x = -(coord_y - 0.5)
    rot_y = coord_x - 0.5
    final_x = minX + (rot_x + 0.5) * (maxX - minX)
    final_y = minY + (rot_y + 0.5) * (maxY - minY)
    
    #flipping coordinates if shot is taken beyond half-court
    if final_y < 0:
        final_y = -final_y
        final_x = -final_x
    return final_x, final_y

#Process data
def process_data(json_data, clue=None):
    print("Processing JSON data...")
    shooting_data = []
    teams = json_data.get("tm", {})
    team_codes = {key: data.get("code", f"Unknown Code {key}") for key, data in teams.items()}
    
    for team_key, team_data in teams.items():
        team_name = team_data.get("name", "Unknown Team")
        team_code = team_data.get("code", "Unknown Code")
        opponent_key = "1" if team_key == "2" else "2"
        opponent_code = team_codes.get(opponent_key, "Unknown Code")

        for shot in team_data.get("shot", []):
            if isinstance(shot, dict):
                action = shot.get("actionType", None)
                if action == "3pt":
                    action = 3
                elif action == "2pt":
                    action = 2

                shooting_data.append({
                    "team": team_name,
                    "team_code": team_code,
                    "opponent": opponent_code,
                    "player": shot.get("player", "Unknown Player"),
                    "shirtNum": shot.get("shirtNumber", "Unknown"),
                    "quarter": shot.get("per", None),
                    "period": shot.get("perType", None),
                    "action": action,
                    "made": shot.get("r", None),
                    "x": shot.get("x", None),
                    "y": shot.get("y", None),
                    "actionNum": shot.get("actionNumber", None)
                })
    
    df = pd.DataFrame(shooting_data)
    if not df.empty:
        df[['x', 'y']] = df.apply(lambda row: coords(row['x'], row['y']), axis=1, result_type="expand")
        print("Coordinate conversion completed.")
    else:
        print("No shooting data found.")
    print("Data processing completed.")
    return df

#Process all games and combine data
print("Starting processing of all games...")
total_data = pd.DataFrame()
for url in json_urls:
    data_json = url_data(url)
    if data_json:
        data_frame = process_data(data_json, clue)
        if not data_frame.empty:
            total_data = pd.concat([total_data, data_frame], ignore_index=True)
            print(f"Added data from {url} to total dataset.")
        else:
            print(f"No data to add from {url}.")
print("Processing of all games completed.")

#Create output folder if it doesn't exist
if not os.path.exists(output_folder):
    print(f"Creating output folder: {output_folder}")
    os.makedirs(output_folder)
else:
    print("Output folder already exists.")

#Export data to CSV
print("Exporting data to CSV...")
if not total_data.empty:
    if not os.path.exists(export):
        total_data.to_csv(export, index=False)
    else:
        print(f"Appending to existing CSV file: {export}")
        total_data.to_csv(export, index=False, mode='a', header=False)
    print(f"Data has been saved to {export}")
else:
    print("No data has been found to save.")

# ------------------------------------------------------------
# Section: exporting each player's data as a separate SHP and CSV file
# ------------------------------------------------------------

input_csv_path = export  

#checking if CSV file exists before reading
if os.path.exists(input_csv_path):
    print("Reading CSV file...")
    df = pd.read_csv(input_csv_path)
    
    #Create players' folder in output directory
    players_folder = os.path.join(output_folder, "players")
    print(f"Checking players folder: {players_folder}")
    if not os.path.exists(players_folder):
        print(f"Creating players folder: {players_folder}")
        os.makedirs(players_folder)
    else:
        print("Players folder already exists.")
    
    #Create geometry for spatial data
    geometry = [Point(xy) for xy in zip(df['x'], df['y'])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry)
    
    gdf.crs = "EPSG:3857"
    
    #Generate files
    print("Generating SHP and CSV files for each player...")
    for player in df['player'].unique():
        player_df = gdf[gdf['player'] == player]
        if not player_df.empty:
            file_name = re.sub(r'\s+', '_', player.replace('.', ''))
            #export to SHP in players' folder
            shp_output_path = os.path.join(players_folder, f"{file_name}.shp")
            print(f"Saving SHP file for player {player}: {shp_output_path}")
            player_df.to_file(shp_output_path, driver='ESRI Shapefile')
            
            #export to CSV in players' folder
            csv_output_path = os.path.join(players_folder, f"{file_name}.csv")
            print(f"Saving CSV file for player {player}: {csv_output_path}")
            player_df.drop(columns='geometry').to_csv(csv_output_path, index=False)
        else:
            print(f"No data found for player {player}, skipping SHP and CSV file creation.")
    
    print(f"SHP and CSV files have been created in: {players_folder}")
else:
    print(f"File {input_csv_path} not found. Make sure the data scraping completed successfully.")

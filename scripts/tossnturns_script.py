# import pandas as pd
# import zipfile
# from pathlib import Path

# processed_dir = Path("C:/Users/ryadl/OneDrive - King's College London/Applied Bioinformatics/Research_Project/EMFIT_Local_Backup/emfit4/Emfit/Emfit/data/processed")

# dataset = Path("C:/Users/ryadl/OneDrive - King's College London/Applied Bioinformatics/Research_Project/EMFIT_Local_Backup/emfit4/Emfit/Emfit/data/raw")

# for zip_file in dataset.rglob('*.zip'):
#     participant_id = zip_file.parts[-5] # Gets the participant ID 
#     visit_num = zip_file.parts[-4] # Gets which Visit it is
#     night_date = zip_file.parts[-3] # Gets the date the night started

#     output_folder = processed_dir/participant_id/visit_num/night_date/"annotations" 
#     output_folder.mkdir(parents=True, exist_ok=True) # Produces an output folder (with parents) within the processed directory.

#     print(f"Successfully made the {output_folder} directory.")

#     with zipfile.ZipFile(zip_file, 'r') as z:
#         all_files = z.namelist()

#         summary_file = min(all_files, key=len) # Summary file will always be the shortest file
#         summary_df = pd.read_csv(z.open(summary_file))
#         print("Created dataframe for summary file!")

#         unix_start_time = summary_df.loc[0, "from"] # Grabs the Unix start time from the summary file.
#         print("Found the UNIX start time!")
        
#         for file in all_files:
#             if "tossnturns" in file:
#                 toss_file = file
                
#                 try:
#                     tossnturn_in_zip = pd.read_csv(z.open(toss_file))
#                 except pd.errors.EmptyDataError:
#                     print("No toss/turn data found for this night, skipping...")
#                     continue

            
#                 tossnturn_in_zip['Onset'] = tossnturn_in_zip['timestamp'] - unix_start_time # Removed the 5 second offset
#                 tossnturn_in_zip['Duration'] = 0
#                 tossnturn_in_zip['Description'] = "Toss/Turn"
#                 final_df = tossnturn_in_zip[['Onset', 'Duration', 'Description']]
#                 final_filename = (f"{participant_id}_{visit_num}_{night_date}_annotations.csv")
#                 full_output_path = output_folder / final_filename
#                 final_df.to_csv(full_output_path, index=False, header=False)
#                 print(f"Annotation file created at: {output_folder}")
#                 break



import pandas as pd
import zipfile
from pathlib import Path

processed_dir = Path("C:/Users/ryadl/OneDrive - King's College London/Applied Bioinformatics/Research_Project/EMFIT_Local_Backup/emfit4/Emfit/Emfit/data/processed")
dataset = Path("C:/Users/ryadl/OneDrive - King's College London/Applied Bioinformatics/Research_Project/EMFIT_Local_Backup/emfit4/Emfit/Emfit/data/raw")

# Track which nights have already been processed to avoid duplicates
processed_nights = set()

for zip_file in sorted(dataset.rglob('*.zip')):
    participant_id = zip_file.parts[-5]
    visit_num = zip_file.parts[-4]
    night_date = zip_file.parts[-3]

    # Create a unique key for this night
    night_key = (participant_id, visit_num, night_date)

    output_folder = processed_dir / participant_id / visit_num / night_date / "annotations"
    output_folder.mkdir(parents=True, exist_ok=True)

    final_filename = f"{participant_id}_{visit_num}_{night_date}_annotations.csv"
    full_output_path = output_folder / final_filename

    # Skip if annotation already exists for this night
    if full_output_path.exists():
        print(f"Skipping {night_key} — annotation already exists.")
        continue

    # Skip if we've already processed this night in this run
    if night_key in processed_nights:
        print(f"Skipping duplicate zip for {night_key}")
        continue

    print(f"Processing: {night_key}")

    try:
        with zipfile.ZipFile(zip_file, 'r') as z:
            all_files = z.namelist()

            # Summary file is shortest filename
            summary_file = min(all_files, key=len)

            try:
                summary_df = pd.read_csv(
                    z.open(summary_file),
                    encoding='latin-1'      # Fix for non-UTF-8 files
                )
            except Exception as e:
                print(f"  Could not read summary for {night_key}: {e}")
                continue

            if "from" not in summary_df.columns:
                print(f"  Warning: 'from' column missing in {zip_file.name}, skipping.")
                continue

            unix_start_time = summary_df.loc[0, "from"]

            toss_found = False
            for file in all_files:
                if "tossnturns" not in file:
                    continue

                try:
                    tossnturn_df = pd.read_csv(
                        z.open(file),
                        encoding='latin-1'
                    )
                except pd.errors.EmptyDataError:
                    print(f"  No toss/turn data for {night_key}, skipping.")
                    break

                tossnturn_df['Onset'] = tossnturn_df['timestamp'] - unix_start_time
                tossnturn_df['Duration'] = 0
                tossnturn_df['Description'] = "Toss/Turn"

                final_df = tossnturn_df[['Onset', 'Duration', 'Description']]
                final_df.to_csv(full_output_path, index=False, header=False)

                print(f"  Annotation saved: {full_output_path}")
                processed_nights.add(night_key)
                toss_found = True
                break

            if not toss_found and night_key not in processed_nights:
                print(f"  No tossnturns file found in {zip_file.name}")
                processed_nights.add(night_key)  # Still mark as processed

    except zipfile.BadZipFile:
        print(f"  Bad zip file, skipping: {zip_file}")



# # 1. Define the paths separately
# zip_path = "C:/Users/ryadl/OneDrive - King's College London/Applied Bioinformatics/Research_Project/EMFIT_Local_Backup/emfit_test3/Emfit/Emfit/data/raw/MS25/Visit_1/20240116/zip/MS25_Emfit1_20240116_2235_20240117_0801_UTC+0.zip"
# csv_inside_zip = "0053F5-presence-period-2024-01-16--22.35-08.01-tossnturns.csv"

# # 2. Open the zip and read the specific CSV into pandas
# with zipfile.ZipFile(zip_path, 'r') as z:
#     with z.open(csv_inside_zip) as f:
#         df = pd.read_csv(f)

# # Define start time of the .edf recording (in UNIX epoch) ADD +5 seconds to the start time to correctly sync.
# edf_start_unix = 1705444529

# # Calculate the relative onset in seconds
# df['Onset'] = df['timestamp'] - edf_start_unix

# # Add the required EDFbrowser columns
# df['Duration'] = 0                # 0 creates a vertical line
# df['Description'] = 'Toss/Turn'   # The label that will appear on the graph

# # Filter for only the columns EDFbrowser wants.
# export_df = df[['Onset', 'Duration', 'Description']]

# # Export without headers or indexes so EDFbrowser can read it cleanly
# export_df.to_csv("C:/Users/ryadl/OneDrive - King's College London/Applied Bioinformatics/Research_Project/EMFIT_Local_Backup/emfit_test3/Emfit/Emfit/logs/MS25_20240116_edf_annotations_2.csv", index=False, header=False)

# print("Annotations successfully created!")
from datetime import datetime
from pathlib import Path
import csv
import shutil

dataset = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/data/raw")
log_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/logs/emfit_num_log.csv")

# === Load existing log file as a dictionary ===
with open(log_path, newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    log_rows = list(reader)

# Converts list of rows into a dictionary keyed by participant_id. .strip() removes whitespace
log_lookup = {row['participant_id'].strip(): row for row in log_rows} 
all_night_keys = set()


for participant in dataset.iterdir():
    if not participant.is_dir():
        continue
    participant_id = participant.name

    for visit in participant.iterdir():
        if not visit.is_dir():  # Guard against stray files
            continue

        # =====================
        # Fix edge case folders (e.g. 20231115.csv, 20231115.edf)
        # =====================
        for item in list(visit.iterdir()):
            if item.is_dir() and item.name.endswith(('.csv', '.edf')):
                night_folder = visit / item.stem  # e.g. 20231115
                night_folder.mkdir(exist_ok=True)
                for file in item.iterdir():  # Move contents up
                    shutil.move(str(file), str(night_folder / file.name))
                item.rmdir()  # Remove now-empty edge case folder
                print(f"Fixed edge case folder: {item.name} → {item.stem}")

        # =====================
        # Build night list
        # Only include date-named directories, exclude extension folders
        # =====================
        night_list = sorted([
            n for n in visit.glob("202*")
            if n.is_dir() and not n.name.endswith(('.csv', '.edf'))
        ])

        if not night_list:
            continue

        night_anchor = datetime.strptime(night_list[0].name, "%Y%m%d")

        # =====================
        # Rename nights and update log
        # =====================
        for night in night_list:
            night_object = datetime.strptime(night.name, "%Y%m%d")
            night_number = (night_object - night_anchor).days + 1
            night_key = f"night_{night_number}"
            all_night_keys.add(night_key)

            # Update log with original date
            if participant_id not in log_lookup:
                log_lookup[participant_id] = {'participant_id': participant_id, 'emfit_id': 'N/A'} # If a participant isn't in the log, adds them.
            log_lookup[participant_id][night_key] = night.name

            # Rename folder
            destination = night.parent / f"Night_{night_number}"
            if destination.exists():
                print(f"Skipping {night.name} — Night_{night_number} already exists")
                continue
            else:
                print(f"Renaming {night.name} → Night_{night_number}")
                night.rename(destination)

# =====================
# Write updated log
# =====================
all_night_keys = sorted(all_night_keys, key=lambda x: int(x.split('_')[1])) # Sorts the night columns numerically
new_fieldnames = ['participant_id', 'emfit_id'] + all_night_keys # Creates the column list, where participant_id and emfit_id is always first.

with open(log_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=new_fieldnames, extrasaction='ignore') # Overwrites the log file with the updated values.
    writer.writeheader()
    for row in log_lookup.values():
        writer.writerow(row)

print("Done. Log updated.")


# for participants in dataset.iterdir(): # Loops through each participant
#     if not participants.is_dir(): # In case there are other files alongside the participant folders
#             continue

#     for visits in participants.iterdir(): # Loops through each visit within each participant.
        
#         for item in visits.iterdir(): # In case there are other files alongside the night folders
             
#             if item.is_dir() and item.name.endswith(('.csv', '.edf')): # In case there are .csv or .edf folders alongside the visit folders
                
#                 stem_night_folder = item.stem
#                 night_folder = visits / stem_night_folder # Builds the path for the night folder
#                 item.rename(night_folder) # Moves the item to the night folder
#                 item.rmdir() # Removes the original folder if it is empty.
                


#         # Creates a list of nights within each visit, excluding non-directories and directories which end with .csv and .edf
#         night_list = sorted([n for n in visits.glob("202*") if n.is_dir() and not n.name.endswith(('.csv', '.edf'))])
        
#         if not night_list: # In case visits have no data folders.
#             continue

#         for night in night_list: # Loops through the night

#             # Computes the night number
#             night_object = datetime.strptime(str(night.name), "%Y%m%d")
#             night_anchor = datetime.strptime(str(night_list[0].name), "%Y%m%d")
#             night_number = (night_object - night_anchor).days + 1
            
#             destination = night.parent /f"Night_{night_number}" # Builds the destination path
#             if destination.exists():
#                 print ("Skipping, Night folder already exists...")
#                 continue
#             else:
#                 night.rename(destination)
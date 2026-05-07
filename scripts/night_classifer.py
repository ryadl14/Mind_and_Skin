from datetime import datetime
from pathlib import Path
import csv
import shutil
import re

dataset = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/data/raw") # NOTE EMFIT5 IN PATH
log_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/logs/emfit_num_log.csv") # NOTE EMFIT5 IN PATH

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

        if not night_list: # Ensures night_list is not empty.
            continue

        night_anchor = datetime.strptime(night_list[0].name, "%Y%m%d")

        # =====================
        # Rename nights and update log
        # =====================
        for night in night_list:
            night_object = datetime.strptime(night.name, "%Y%m%d")
            night_number = (night_object - night_anchor).days + 1
            night_key = f"{visit.name}_night_{night_number}" # Includes visit number to emfit_num_log to prevent nights across multiple visits overriding each other.
            all_night_keys.add(night_key)

            # Update log with original date
            if participant_id not in log_lookup:
                log_lookup[participant_id] = {'participant_id': participant_id, 'emfit_id': 'N/A'} # If a participant isn't in the log, adds them.
            log_lookup[participant_id][night_key] = datetime.strptime(night.name, "%Y%m%d").strftime("%d/%m/%Y") # Changes the date format to dd/mm/yyyy

            nested_edf = night / "edf" / "edf" # Catches nested edf files and moves the .edf file up and out.
            if nested_edf.is_dir():
                for file in nested_edf.iterdir():
                    shutil.move(str(file), str(night / "edf"))
                nested_edf.rmdir()

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
all_night_keys = sorted(all_night_keys, key=lambda x: (int(x.split('_')[1]), int(x.split('_')[3]))) # Sorts the night (and visit) columns numerically
new_fieldnames = ['participant_id', 'emfit_id'] + all_night_keys # Creates the column list, where participant_id and emfit_id is always first.

with open(log_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=new_fieldnames, extrasaction='ignore') # Overwrites the log file with the updated values.
    log_lookup = {
        re.sub(r'_Visit.*', '', k): v # Catches any trailing _Visit* suffixes in the participant column.
        for k, v in log_lookup.items()
    }
    
    writer.writeheader() # Writes the column names as the first row of the CSV, then the for loop iterates over each participant's data dictionary and writes it as a row.
    for row in log_lookup.values():
        writer.writerow(row)

print("Done. Log updated.")
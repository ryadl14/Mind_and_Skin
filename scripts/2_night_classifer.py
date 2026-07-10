from datetime import datetime
from pathlib import Path
import csv
import shutil
import re
import pandas as pd

dataset = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/raw") 
log_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/emfit_num_log.csv") 
output_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/emfit_dates.csv")

# ====================================== 
# Load emfit_num_log.csv as a dictionary 
# ======================================

with open(log_path, newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    log_rows = list(reader)

# Converts list of rows into a dictionary keyed by participant_id. | .strip() removes whitespace
log_lookup = {row['participant_id'].strip(): row for row in log_rows} 
all_night_keys = set() # Initialises an empty set.

# Loops through all participants and visits.
for participant in dataset.iterdir():
    if not participant.is_dir():
        continue
    participant_id = participant.name

    for visit in participant.iterdir():
        if not visit.is_dir():  # Guard against stray files
            continue

        # Fix edge case folders (e.g. 20231115.csv, 20231115.edf)
        for item in list(visit.iterdir()):
            if item.is_dir() and item.name.endswith(('.csv', '.edf')):
                night_folder = visit / item.stem  # e.g. 20231115
                night_folder.mkdir(exist_ok=True)
                for file in item.iterdir():  # Move contents up
                    shutil.move(str(file), str(night_folder / file.name))
                item.rmdir()  # Remove now-empty edge case folder
                print(f"Fixed edge case folder: {item.name} → {item.stem}")

        # Build night list in each visit, only include date-named directories, exclude extension folders
        night_list = sorted([
            n for n in visit.glob("202*")
            if n.is_dir() and not n.name.endswith(('.csv', '.edf'))
        ])

        if not night_list: # Ensures night_list is not empty.
            continue

        night_anchor = datetime.strptime(night_list[0].name, "%Y%m%d") # Selects the earliest data as the 'anchor'.

        # =====================
        # Rename nights and update log
        # =====================

        for night in night_list:
            night_object = datetime.strptime(night.name, "%Y%m%d") # Saves night as a datetime object
            night_number = (night_object - night_anchor).days # Night 0 indexed
            night_key = f"{visit.name}_night_{night_number}" # Includes visit number to emfit_num_log to prevent nights across multiple visits overriding each other.
            all_night_keys.add(night_key) # Adds them to the night_key.

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

log_lookup = {
    re.sub(r'_Visit.*', '', k): v # Catches any trailing _Visit* suffixes in the participant column.
    for k, v in log_lookup.items()
}

try: # Updates the log
    with open(log_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in log_lookup.values():
            writer.writerow(row)
    print("Done. Log updated.")
except PermissionError:
    print("ERROR: Cannot write to log — close the emfit_num_log first and rerun.")


# ================================================================
# Create emfit_dates.csv, based on emfit_num_log to match metadata
# ================================================================

def pad_participant(pid):
    # Convert MS04 → MS004, MS25 → MS025
    num = re.search(r'\d+', str(pid)).group() # Extract the number from the participant ID
    return f"MS{int(num):03d}" # Zero-pad to 3 digits

# Find participants with Visit_2 data
multi_visit = {
    pid for pid, row in log_lookup.items()
    if any(k.startswith('Visit_2') and v is not None 
           for k, v in row.items())
} # Builds a set of participant IDs that have any Visit_2 night data

# Get max night number
max_night = max(
    int(k.split('_night_')[1]) 
    for k in all_night_keys
) # Finds the highest night number across all participants to define column range

night_cols = [f"N{i}" for i in range(max_night + 1)] # Creates column names N0, N1, N2...
output_rows = []

for pid, row in log_lookup.items():
    if not pid:
        continue # Skip empty participant IDs
    
    padded = pad_participant(pid) # Convert to metadata format e.g. MS004

    visits = [1, 2] if pid in multi_visit else [1] # Two rows for multi-visit, one for single

    for visit_num in visits:
        # Build the ID for this row e.g. MS004V2 or MS004
        row_id = f"{padded}V{visit_num}" if pid in multi_visit else padded
        
        new_row = {'ID': row_id}
        for n in range(max_night + 1):
            col = f"Visit_{visit_num}_night_{n}" # e.g. Visit_1_night_0
            new_row[f"N{n}"] = row.get(col) # Gets the date, None if not present
        
        output_rows.append(new_row)

# Build and save dataframe
output_df = pd.DataFrame(output_rows, columns=['ID'] + night_cols)

try:
    output_df.to_csv(output_path, index=False)
    print(f"Metadata format log saved to: {output_path}")
except PermissionError:
    print("ERROR: Cannot write metadata log — close the file first and rerun.")
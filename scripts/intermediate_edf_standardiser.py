import pandas as pd
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import shutil

# ===========
# From this script, I learned that the filenames have already been standardised to local time.
# Therefore, the purpose of this script is to double-check it and ensure that the manually-written filenames are correct.
# rename_counter tracks how many files were renamed.

raw_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/data/raw")
intermediate_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/data/intermediate")
log_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/logs/header_check_log.csv")

rename_counter = 0
uk_tz = ZoneInfo("Europe/London")
eest_tz = ZoneInfo("Europe/Helsinki")

if not intermediate_dir.exists() or not any(intermediate_dir.iterdir()): # Skip copytree if intermediate folder already exists, empty or full.
    shutil.copytree(raw_dir, intermediate_dir, dirs_exist_ok=True) # Copies all of the raw_directory and moves it to intermediate.

log_df = pd.read_csv(log_path)

for _, row in log_df.iterrows(): # Iterates over all rows in log_df
    raw_path = Path(row['filename']) # Makes the path into a Path object
    intermediate_path = intermediate_dir / raw_path.relative_to(raw_dir) # Strips the data/raw prefix and substitutes in the intermediate directory instead.

    if not intermediate_path.exists(): # Check if the path exists, skips if not found.
        print(f"File not found, skipping: {intermediate_path}")
        continue

    header_start = datetime.strptime(row['header_start'], "%d/%m/%Y %H:%M:%S") # Gets the header start datetime
    header_start = header_start.replace(tzinfo=eest_tz) # Attaches the Helsinki (Finnish) timezone.
    header_start_uk = header_start.astimezone(uk_tz) # Converts to UK local time, switching between GMT and BST depending on the date.
    utc_offset = int(header_start_uk.utcoffset().total_seconds() // 3600)
    utc_string = f"UTC+{utc_offset}" if utc_offset >= 0 else f"UTC{utc_offset}"

    header_end = datetime.strptime(row['header_end'], "%d/%m/%Y %H:%M:%S") # Gets the header end datetime
    header_end = header_end.replace(tzinfo=eest_tz)
    header_end_uk = header_end.astimezone(timezone.utc) + header_start_uk.utcoffset() # Catches edge case where recording occurs during timezone switch (currently not working)
    header_end_uk = header_end_uk.replace(tzinfo=header_start_uk.tzinfo) # Uses the start date's timezone (usually BST)

    start_date = header_start_uk.strftime("%Y%m%d") # Isolates the start date
    start_time = header_start_uk.strftime("%H%M") # Isolates the start time
    end_date = header_end_uk.strftime("%Y%m%d") # Isolates the end date
    end_time = header_end_uk.strftime("%H%M") # Isolates the end time

    participant = row['participant_id']
    emfit_id = raw_path.stem.split('_')[1]  # Extracts EmfitX from original filename

    if start_date == end_date: # If the recording was same day
        new_stem = f"{participant}_{emfit_id}_{start_date}_{start_time}_{end_time}_{utc_string}"
    else: # Standard two day recording
        new_stem = f"{participant}_{emfit_id}_{start_date}_{start_time}_{end_date}_{end_time}_{utc_string}"

    new_path = intermediate_path.parent / f"{new_stem}.edf" # Creates the new file path.

    if new_path.exists(): # Checks if it has already been ran before.
        print(f"Skipping — already renamed: {new_path.name}")
        continue

    intermediate_path.rename(new_path) 
    print(f"Renamed: {intermediate_path.name} → {new_path.name}")
    rename_counter += 1

print(f"Rename counter: {rename_counter}")


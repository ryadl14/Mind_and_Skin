import pandas as pd
import mne
import edfio
import csv
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import shutil

# ===========
# This script:
# 1. Copies raw data to intermediate directory
# 2. Updates EDF headers from EEST to UK local time
# 3. Compares filenames against corrected header times and renames if mismatched
# 4. Regenerates header_check_log.csv

raw_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/raw")
intermediate_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/intermediate")
log_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/header_check_log.csv")

rename_counter = 0
header_update_counter = 0
uk_tz = ZoneInfo("Europe/London")
eest_tz = ZoneInfo("Europe/Helsinki")

# =====================
# STEP 1: Copy only EDF files from raw to intermediate
# =====================
print("Copying EDF files to intermediate directory...")

edf_count = 0
for edf_path in raw_dir.rglob("*.edf"):
    # Mirror the folder structure in intermediate
    relative_path = edf_path.relative_to(raw_dir)
    dest_path = intermediate_dir / relative_path
    
    # Create parent directories if they don't exist
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Only copy if not already there
    if not dest_path.exists():
        shutil.copy2(edf_path, dest_path)
        edf_count += 1
    else:
        print(f"Already exists, skipping: {dest_path.name}")

print(f"Copied {edf_count} EDF files to intermediate.")

# =====================
# STEP 2: Update EDF headers from EEST to UK local time
# =====================
print("\nUpdating EDF headers to UK local time...")

for edf_path in intermediate_dir.rglob("*.edf"):
    try:
        edf = edfio.read_edf(str(edf_path))

        # Build full datetime with EEST timezone
        current_dt = datetime(
            edf.recording.startdate.year,
            edf.recording.startdate.month,
            edf.recording.startdate.day,
            edf.starttime.hour,
            edf.starttime.minute,
            edf.starttime.second,
            tzinfo=eest_tz
        )

        # Convert to UK local time
        uk_dt = current_dt.astimezone(uk_tz)

        # Write corrected header
        edf.recording = edfio.Recording(startdate=uk_dt.date())
        edf.starttime = uk_dt.time()
        edf.write(str(edf_path))

        header_update_counter += 1

    except Exception as e:
        print(f"Error updating header for {edf_path.name}: {e}")

print(f"Headers updated: {header_update_counter}")

# =====================
# STEP 3: Regenerate header_check_log.csv using updated headers
# =====================
print("\nRegenerating header_check_log.csv...")

mne.set_log_level('WARNING')

column_names = ['filename', 'participant_id', 'visit', 'night', 
                'header_start', 'filename_start', 'header_end', 
                'filename_end', 'offset_minutes', 'match']

try:
    with open(log_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=column_names, extrasaction='ignore')
        writer.writeheader()

        for edf in intermediate_dir.rglob('*.edf'):
            raw = mne.io.read_raw_edf(edf, preload=False)
            filename = Path(edf).stem

            participant = None
            visit = edf.parts[-4]
            night = edf.parts[-3]

            try:
                parts = edf.stem.split('_')
                participant = parts[0]
                start_date = parts[2]
                start_time = parts[3]

                if len(parts) > 4 and parts[4].isdigit() and len(parts[4]) == 8:
                    end_date = parts[4]
                    end_time = parts[5]
                elif len(parts) > 4 and parts[4].isdigit():
                    end_date = start_date
                    end_time = parts[4]
                elif len(parts) > 5 and parts[5].isdigit() and len(parts[5]) == 8:
                    end_date = parts[5]
                    end_time = parts[6]
                else:
                    end_date = start_date
                    end_time = parts[5]

            except IndexError:
                recording_duration_secs = raw.n_times / raw.info['sfreq']
                header_start_datetime = raw.info['meas_date']
                header_end = header_start_datetime + timedelta(seconds=recording_duration_secs)
                header_start_datetime = header_start_datetime.strftime("%d/%m/%Y %H:%M:%S")
                header_end = header_end.strftime("%d/%m/%Y %H:%M:%S")
                writer.writerow({
                    'filename': edf,
                    'participant_id': participant,
                    'visit': visit,
                    'night': night,
                    'header_start': header_start_datetime,
                    'filename_start': None,
                    'header_end': header_end,
                    'filename_end': None,
                    'offset_minutes': None,
                    'match': False
                })
                continue

            header_start_datetime = raw.info['meas_date']

            filename_start_datetime = start_date + " " + start_time
            filename_start_datetime = datetime.strptime(filename_start_datetime, "%Y%m%d %H%M")
            filename_start_datetime = filename_start_datetime.replace(tzinfo=timezone.utc)

            offset_minutes = header_start_datetime - filename_start_datetime
            offset_minutes = offset_minutes.total_seconds() / 60

            filename_start_datetime = filename_start_datetime.strftime("%d/%m/%Y %H:%M:00")

            if end_time is not None:
                filename_end_datetime = end_date + " " + end_time
                filename_end_datetime = datetime.strptime(filename_end_datetime, "%Y%m%d %H%M")
                filename_end_datetime = filename_end_datetime.replace(tzinfo=timezone.utc)
                filename_end_datetime = filename_end_datetime.strftime("%d/%m/%Y %H:%M:00")
            else:
                filename_end_datetime = None

            try:
                utc_offset = int(parts[-1].replace('UTC+', '').replace('UTC-', ''))
            except ValueError:
                print(f"Cannot parse UTC offset fromm {edf.stem}. defaulting to 0")
                print(f"parts[-1] = {parts[-1]}")
                utc_offset = 0

            expected_offset = utc_offset * 60
            match = abs(offset_minutes - expected_offset) < 1

            recording_duration_secs = raw.n_times / raw.info['sfreq']
            header_end = header_start_datetime + timedelta(seconds=recording_duration_secs) if isinstance(header_start_datetime, datetime) else None

            header_start_datetime = raw.info['meas_date'].strftime("%d/%m/%Y %H:%M:%S")
            header_end = (raw.info['meas_date'] + timedelta(seconds=recording_duration_secs)).strftime("%d/%m/%Y %H:%M:%S")

            writer.writerow({
                'filename': edf,
                'participant_id': participant,
                'visit': visit,
                'night': night,
                'header_start': header_start_datetime,
                'filename_start': filename_start_datetime,
                'header_end': header_end,
                'filename_end': filename_end_datetime,
                'offset_minutes': offset_minutes,
                'match': match
            })

    print("header_check_log.csv regenerated.")
except PermissionError:
    print("ERROR: Cannot write header_check_log — close the file first.")

# =====================
# STEP 4: Compare filenames against corrected header times and rename
# =====================
print("\nComparing filenames against corrected headers...")

log_df = pd.read_csv(log_path)

for _, row in log_df.iterrows():
    raw_path = Path(row['filename'])

    try: # Guard against not finding MS85 V1N5 in raw data for some reason?
        intermediate_path = intermediate_dir / raw_path.relative_to(raw_dir)
    except:
        print(f"File not in raw directory, skipping: {raw_path.name}")
        continue

    if not intermediate_path.exists():
        print(f"File not found, skipping: {intermediate_path}")
        continue

    if pd.isna(row['header_start']) or pd.isna(row['header_end']):
        print(f"Missing header data, skipping: {intermediate_path.name}")
        continue

    # Header times are now already in UK time — no conversion needed
    header_start_uk = datetime.strptime(row['header_start'], "%d/%m/%Y %H:%M:%S")
    header_start_uk = header_start_uk.replace(tzinfo=uk_tz)

    start_offset = header_start_uk.utcoffset()
    if start_offset is None:
        start_offset = timedelta(0)

    utc_offset = int(start_offset.total_seconds() // 3600)
    utc_string = f"UTC+{utc_offset}" if utc_offset >= 0 else f"UTC{utc_offset}"

    header_end = datetime.strptime(row['header_end'], "%d/%m/%Y %H:%M:%S")
    header_end = header_end.replace(tzinfo=eest_tz)
    header_end_uk = header_end.astimezone(timezone.utc) + start_offset
    header_end_uk = header_end_uk.replace(tzinfo=header_start_uk.tzinfo)

    start_date = header_start_uk.strftime("%Y%m%d")
    start_time = header_start_uk.strftime("%H%M")
    end_date = header_end_uk.strftime("%Y%m%d")
    end_time = header_end_uk.strftime("%H%M")

    participant = row['participant_id']
    emfit_id = raw_path.stem.split('_')[1]

    if start_date == end_date:
        new_stem = f"{participant}_{emfit_id}_{start_date}_{start_time}_{end_time}_{utc_string}"
    else:
        new_stem = f"{participant}_{emfit_id}_{start_date}_{start_time}_{end_date}_{end_time}_{utc_string}"

    new_path = intermediate_path.parent / f"{new_stem}.edf"

    if new_path.exists():
        print(f"Skipping — already renamed: {new_path.name}")
        continue

    intermediate_path.rename(new_path)
    print(f"Renamed: {intermediate_path.name} → {new_path.name}")
    rename_counter += 1

print(f"\nRename counter: {rename_counter}")
print("Done.")
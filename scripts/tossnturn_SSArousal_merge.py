import pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

processed_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/processed")
raw_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/raw")

uk_tz = ZoneInfo("Europe/London")

for participant_dir in processed_dir.glob("MS*"):
    participant_id = participant_dir.name

    for visit_dir in participant_dir.glob("Visit_*"):

        print(f"\n=== {participant_id} | {visit_dir.name} ===")

        # === Find the SSandArousal file ===
        ss_files = list(visit_dir.glob("*_acti_psg_SSandArousal.csv"))
        if not ss_files:
            print(f"{participant_id} does not have a SSandArousal file, skipping...")
            continue

        ss_file = ss_files[0]
        print(f"Found SSandArousal file: {ss_file.name}")

        # === Skip if already processed ===
        new_filename = ss_file.stem.replace("_acti_psg_SSandArousal", "_acti_psg_SSandArousal_1s_tt") + ".csv"
        new_path = ss_file.parent / new_filename
        if new_path.exists():
            print(f"Already processed, skipping: {new_filename}")
            continue

        # === Find the matching Night_0 tossnturns file in raw ===
        raw_participant_dir = raw_dir / participant_id
        if not raw_participant_dir.exists():
            print(f"{participant_id} not found in raw, skipping...")
            continue

        night0_dir = raw_participant_dir / visit_dir.name / "Night_0"
        if not night0_dir.exists():
            print(f"{participant_id} has no Night_0 folder in raw, skipping...")
            continue

        tossnturns_files = list((night0_dir / "summary_csvs").glob("*_tossnturns.csv"))
        if not tossnturns_files:
            print(f"{participant_id} has no tossnturns file for Night_0, skipping...")
            continue

        tossnturns_file = tossnturns_files[0]
        print(f"Found tossnturns file: {tossnturns_file.name}")

        # === Load tossnturns and convert Unix timestamps to UK local time ===
        tt_df = pd.read_csv(tossnturns_file)

        if 'timestamp' not in tt_df.columns:
            print(f"  No 'timestamp' column found in {tossnturns_file.name}, skipping...")
            continue

        tt_timestamps_uk = []
        for ts in tt_df['timestamp']:
            try:
                dt_utc = datetime.fromtimestamp(int(ts), tz=ZoneInfo("UTC"))
                dt_uk = dt_utc.astimezone(uk_tz)
                dt_uk_naive = dt_uk.replace(tzinfo=None, microsecond=0)
                tt_timestamps_uk.append(dt_uk_naive)
            except (ValueError, OSError):
                print(f"  Could not parse timestamp: {ts}")
                continue

        tt_timestamps_set = set(tt_timestamps_uk)

        # === Load SSandArousal and create the tossnturn column ===
        try:
            ss_df = pd.read_csv(ss_file, low_memory=False)
        except pd.errors.EmptyDataError:
            print(f"  Empty file, skipping: {ss_file.name}")
            continue
        except UnicodeDecodeError:
            ss_df = pd.read_csv(ss_file, low_memory=False, encoding='latin-1')

        if ss_df.empty:
            print(f"  No data in file, skipping: {ss_file.name}")
            continue

        ss_df['Date'] = pd.to_datetime(ss_df['Date'])
        ss_df['tossnturn'] = ss_df['Date'].apply(lambda d: 1 if d.to_pydatetime().replace(microsecond=0) in tt_timestamps_set else None)

        matched_count = int(ss_df['tossnturn'].sum())
        print(f"Matched {matched_count} of {len(tt_timestamps_set)} toss/turn events.")

        # === Save with new filename ===
        new_filename = ss_file.stem.replace("_acti_psg_SSandArousal", "_acti_psg_SSandArousal_1s_tt") + ".csv"
        new_path = ss_file.parent / new_filename
        ss_df.to_csv(new_path, index=False)
        print(f"Saved: {new_filename}")

print("\nDone.")
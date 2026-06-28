import pandas as pd
from pathlib import Path
from datetime import datetime
import re

# === Paths ===
raw_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/raw")
intermediate_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/intermediate")

metadata_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/documentation/MS_Metadata_Copy.csv")
emfit_dates_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/emfit_dates.csv")
n0_comparison_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/n0_comparison.csv")
corrections_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/documentation/hardcoded_date_correction.csv")

DRY_RUN = False # For testing purposes, switch to False to actually change the names.

# === Parse date helper ===
def parse_date(date_str):
    if pd.isna(date_str):
        return None
    try:
        return datetime.strptime(str(date_str).strip(), "%d/%m/%Y")
    except ValueError:
        print(f"Unexpected date format: {date_str}")
        return None

# === Folder lookup with zero-padding fallback ===
def find_participant_folder(base_dir, participant_id):

    match = re.match(r'(MS)0*(\d+)(V(\d+))?$', participant_id)
    if not match:
        return None

    prefix = match.group(1)
    num = int(match.group(2))
    visit_num = match.group(4)  # e.g. '1' or '2', None if no visit suffix

    # Generate candidate folder names with different zero-padding levels
    candidate_names = [
        f"{prefix}{num:03d}",  # MS053
        f"{prefix}{num:02d}",  # MS53
        f"{prefix}{num}",      # MS53 (no padding)
    ]

    for name in candidate_names:
        candidate = base_dir / name
        if candidate.exists():
            return candidate, visit_num  # Return participant folder AND visit filter

    return None, None

# === Load corrections CSV ===
corrections = {}
if corrections_path.exists():
    corr_df = pd.read_csv(corrections_path)
    for _, row in corr_df.iterrows():
        corrections[row['ID']] = {
            'metadata_N0': parse_date(row['correct_metadata_N0']),
            'emfit_N0': parse_date(row['corrected_emfit_N0']),
            'flat_shift': int(row['flat_shift']) if pd.notna(row.get('flat_shift')) else None
        }
    print(f"Loaded {len(corrections)} hardcoded corrections: {list(corrections.keys())}\n")
else:
    print("No corrections file found, proceeding without overrides.\n")

# === Load files ===
n0_df = pd.read_csv(n0_comparison_path)
emfit_dates_df = pd.read_csv(emfit_dates_path)
metadata_df = pd.read_csv(metadata_path, header=1)
metadata_df = metadata_df.rename(columns={'Unnamed: 0': 'ID'})
metadata_df = metadata_df[metadata_df['ID'].notna()]
metadata_df['ID'] = metadata_df['ID'].str.replace(r'A$', '', regex=True).str.strip()
metadata_df = metadata_df[['ID', 'N0']].copy()

# === Filter to participants needing renaming ===
to_rename = n0_df[n0_df['difference'] == 'Y']['ID'].tolist()
print(f"Participants needing renaming: {len(to_rename)}")
print(f"IDs: {to_rename}\n")

# === Initialise rename_maps dictionary ===
rename_maps = {}

# === Rename nights ===
for participant_id in to_rename:

    # === Apply hardcoded corrections if present ===
    if participant_id in corrections:
        corr = corrections[participant_id]
        psg_n0 = corr['metadata_N0']
        corrected_emfit_n0 = corr['emfit_N0']
        flat_shift = corr['flat_shift']

        if psg_n0 == corrected_emfit_n0:
            print(f"  [SKIP] {participant_id} dates now match after correction, no renaming needed.")
            continue

        emfit_row = emfit_dates_df[emfit_dates_df['ID'] == participant_id]
        if emfit_row.empty:
            print(f"  [SKIP] No EMFIT dates found for {participant_id}")
            continue

        night_cols = [col for col in emfit_dates_df.columns if col.startswith('N') and col[1:].isdigit()]

        # Flat shift — increment all existing night numbers by the shift value
        if flat_shift is not None:
            rename_map = {int(col[1:]): int(col[1:]) + flat_shift for col in night_cols if pd.notna(emfit_row[col].values[0])}
            print(f"{participant_id} | Using flat shift +{flat_shift} | Rename map: {rename_map}")

        else:
            # Standard date arithmetic correction
            rename_map = {}
            for col in night_cols:
                date_val = emfit_row[col].values[0]
                emfit_date = parse_date(date_val)
                if emfit_date is None:
                    continue
                old_night_num = int(col[1:])
                new_night_num = (emfit_date - psg_n0).days
                rename_map[old_night_num] = new_night_num
            print(f"{participant_id} | Using hardcoded correction | PSG N0: {psg_n0.strftime('%d/%m/%Y')} | EMFIT N0: {corrected_emfit_n0.strftime('%d/%m/%Y')} | Rename map: {rename_map}")

    else:
        # === Standard path ===
        meta_row = metadata_df[metadata_df['ID'] == participant_id]
        if meta_row.empty:
            print(f"[SKIP] No metadata found for {participant_id}")
            continue

        psg_n0 = parse_date(meta_row['N0'].values[0])
        if psg_n0 is None:
            print(f"[SKIP] Could not parse PSG N0 date for {participant_id}")
            continue

        emfit_row = emfit_dates_df[emfit_dates_df['ID'] == participant_id]
        if emfit_row.empty:
            print(f"[SKIP] No EMFIT dates found for {participant_id}")
            continue

        night_cols = [col for col in emfit_dates_df.columns if col.startswith('N') and col[1:].isdigit()]
        rename_map = {}
        for col in night_cols:
            date_val = emfit_row[col].values[0]
            emfit_date = parse_date(date_val)
            if emfit_date is None:
                continue
            old_night_num = int(col[1:])
            new_night_num = (emfit_date - psg_n0).days
            rename_map[old_night_num] = new_night_num

        print(f"{participant_id} | PSG N0: {psg_n0.strftime('%d/%m/%Y')} | Rename map: {rename_map}")

    # === NEW: Store rename_map for log update ===
    rename_maps[participant_id] = rename_map


    # === Apply renames across raw and intermediate only ===
    for base_dir in [raw_dir, intermediate_dir]:

        participant_path, visit_filter = find_participant_folder(base_dir, participant_id)
        if participant_path is None:
            print(f"  [SKIP] No folder in {base_dir.name} for {participant_id}")
            continue

        if participant_path.name.startswith("Visit_"):
            visit_dirs = [participant_path]
        else:
            visit_dirs = sorted(participant_path.glob("Visit_*"))

        for visit_dir in visit_dirs:
            if not visit_dir.is_dir():
                continue

            if visit_filter and visit_dir.name != f"Visit_{visit_filter}":
                continue

            # Build full rename plan — only include nights that exist on disk
            plan = []
            for old_num, new_num in rename_map.items():
                old_path = visit_dir / f"Night_{old_num}"
                if not old_path.exists():
                    print(f"  [SKIP] Night_{old_num} not found in {base_dir.name}/{participant_path.name}/{visit_dir.name}")
                    continue
                plan.append((old_num, new_num))

            if not plan:
                continue

            if DRY_RUN:
                for old_num, new_num in sorted(plan, key=lambda x: -x[0]):
                    print(f"  [DRY RUN] Would rename: Night_{old_num} → Night_{new_num} ({base_dir.name}/{participant_path.name}/{visit_dir.name})")
            else:
                # Pass 1: rename all source folders to temp names
                for old_num, new_num in plan:
                    old_path = visit_dir / f"Night_{old_num}"
                    tmp_path = visit_dir / f"Night_{old_num}_tmp"
                    try:
                        old_path.rename(tmp_path)
                        print(f"  Temp rename: Night_{old_num} → Night_{old_num}_tmp ({base_dir.name}/{participant_path.name}/{visit_dir.name})")
                    except PermissionError:
                        print(f"  ERROR: Permission denied on temp rename of Night_{old_num} in {base_dir.name}/{participant_path.name}/{visit_dir.name}")

                # Pass 2: rename all temp folders to final destinations
                for old_num, new_num in plan:
                    tmp_path = visit_dir / f"Night_{old_num}_tmp"
                    new_path = visit_dir / f"Night_{new_num}"
                    if not tmp_path.exists():
                        print(f"  [SKIP] Temp Night_{old_num}_tmp not found — pass 1 may have failed")
                        continue
                    if new_path.exists():
                        print(f"  ERROR: Night_{new_num} already exists after temp rename — manual intervention needed for {participant_path.name}/{visit_dir.name}")
                        continue
                    try:
                        tmp_path.rename(new_path)
                        print(f"  Renamed: Night_{old_num} → Night_{new_num} ({base_dir.name}/{participant_path.name}/{visit_dir.name})")
                    except PermissionError:
                        print(f"  ERROR: Permission denied on final rename of Night_{old_num}_tmp in {base_dir.name}/{participant_path.name}/{visit_dir.name}")

# === Update n0_comparison log — only runs on live execution ===
if not DRY_RUN:
    print("\nUpdating n0_comparison log...")

    n0_df = pd.read_csv(n0_comparison_path)
    new_emfit_n0_values = []
    notes_values = []

    typo_ids = {
        pid for pid, corr in corrections.items()
        if corr['metadata_N0'] == corr['emfit_N0']
    }

    for _, row in n0_df.iterrows():
        pid = row['ID']

        if row['difference'] in ['N', 'N/A']:
            new_emfit_n0_values.append('N/A')
            notes_values.append('N/A')
            continue

        if pid in typo_ids:
            new_emfit_n0_values.append('N/A')
            notes_values.append('Typo in metadata, no change')
            continue

        if pid not in rename_maps or not rename_maps[pid]:
            new_emfit_n0_values.append('N/A')
            notes_values.append('N/A')
            continue

        rmap = rename_maps[pid]
        earliest_old = min(rmap.keys())
        earliest_new = rmap[earliest_old]
        new_emfit_n0_values.append(f'Night_{earliest_new}')

        if pid in corrections and corrections[pid]['flat_shift'] is not None:
            notes_values.append(f'EMFIT started late, first recording is Night_{earliest_new}')
        elif pid in corrections:
            notes_values.append('Typo in metadata, corrected')
        else:
            notes_values.append('N/A')

    n0_df['new_emfit_n0'] = new_emfit_n0_values
    n0_df['notes'] = notes_values

    try:
        n0_df.to_csv(n0_comparison_path, index=False)
        print("n0_comparison log updated with new_emfit_n0 and notes columns.")
    except PermissionError:
        print("ERROR: Cannot write n0_comparison log — close the file first and rerun.")

if DRY_RUN:
    print("\n[DRY RUN COMPLETE] No files were renamed.")
else:
    print("\nDone.")
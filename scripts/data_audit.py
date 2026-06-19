import pandas as pd
from pathlib import Path
import re

raw_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/raw")
processed_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/processed")
groups_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/documentation/MS_Metadata_Groups.csv")
output_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/emfit_participant_data.csv")

# === Hardcoded lookup overrides for participants whose on-disk visit
# doesn't match what's recorded in the groups metadata file ===
LOOKUP_OVERRIDES = {
    'MS04': 'MS04V2', # V1 data missing, hardcode to use V2 data
    'MS42': 'MS42V1', # No V2 data available, harcode to use V1
    'MS51': 'MS51V1', # No V2 data available, harcode to use V1
}

# === Load groups/EASI metadata ===
groups_df = pd.read_csv(groups_path)
groups_df['subject'] = groups_df['subject'].str.strip()

def find_group_easi(groups_df, row_id):
    lookup_key = LOOKUP_OVERRIDES.get(row_id, row_id)

    match = re.match(r'MS0*(\d+)(V\d+)?$', lookup_key)
    if not match:
        return None, None

    num = int(match.group(1))
    visit_suffix = match.group(2) or ''

    candidate_subjects = [
        f"MS{num}{visit_suffix}",
        f"MS{num:02d}{visit_suffix}",
        f"MS{num:03d}{visit_suffix}",
    ]

    for cid in candidate_subjects:
        match_row = groups_df[groups_df['subject'] == cid]
        if not match_row.empty:
            group_val = match_row['Group'].values[0]
            easi_val = match_row['EASI'].values[0]
            return group_val, easi_val

    return None, None

def get_base_number(row_id):
    # Extract the numeric participant identifier, ignoring visit suffix
    match = re.match(r'MS0*(\d+)', row_id)
    return int(match.group(1)) if match else None

rows = []

# === Build participant/visit pairs from raw ===
for participant_path in sorted(raw_dir.glob("MS*")):
    if not participant_path.is_dir():
        continue

    base_participant_id = participant_path.name

    for visit_dir in sorted(participant_path.glob("Visit_*")):
        if not visit_dir.is_dir():
            continue

        visit_num = visit_dir.name.replace("Visit_", "")
        all_visits = sorted(participant_path.glob("Visit_*"))
        if len(all_visits) > 1:
            row_id = f"{base_participant_id}V{visit_num}"
        else:
            row_id = base_participant_id

        has_edf = any(visit_dir.rglob("edf/*.edf"))
        has_csv = any(visit_dir.rglob("csv/*.csv"))
        has_zip = any(visit_dir.rglob("zip/*.zip"))
        has_summary_csvs = any(visit_dir.rglob("summary_csvs/*"))

        night0_dir = visit_dir / "Night_0"
        has_night0_edf = (night0_dir / "edf").exists() and any((night0_dir / "edf").glob("*.edf"))

        processed_participant_dir = processed_dir / base_participant_id / visit_dir.name

        has_akti = False
        has_ssarousal = False
        has_ssarousal_tt = False

        if processed_participant_dir.exists():
            has_akti = any(processed_participant_dir.glob("*_PSG_akti.txt"))
            has_ssarousal = any(processed_participant_dir.glob("*_acti_psg_SSandArousal.csv"))
            has_ssarousal_tt = any(processed_participant_dir.glob("*_acti_psg_SSandArousal_1s_tt.csv"))

        eligible_for_sync = has_night0_edf and has_akti

        group_val, easi_val = find_group_easi(groups_df, row_id)

        rows.append({
            'participant_id': row_id,
            'base_number': get_base_number(row_id),  # used only for group fill, dropped before save
            'group': group_val,
            'easi': easi_val,
            'has_edf': 'Y' if has_edf else '',
            'has_csv': 'Y' if has_csv else '',
            'has_zip': 'Y' if has_zip else '',
            'has_summary_csvs': 'Y' if has_summary_csvs else '',
            'has_night0_edf': 'Y' if has_night0_edf else '',
            'has_akti': 'Y' if has_akti else '',
            'has_ssarousal': 'Y' if has_ssarousal else '',
            'has_ssarousal_tt': 'Y' if has_ssarousal_tt else '',
            'eligible_for_sync': eligible_for_sync,
        })

output_df = pd.DataFrame(rows)

# === Lock group to a single consistent value per participant across visits ===
# EASI is intentionally left untouched — it can vary per visit
group_fill = output_df.groupby('base_number')['group'].transform(
    lambda g: g.ffill().bfill()
)
output_df['group'] = output_df['group'].fillna(group_fill)

# Drop helper column before saving
output_df = output_df.drop(columns=['base_number'])

try:
    output_df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")
    print(f"\nTotal participant/visit rows: {len(output_df)}")
    print(f"Eligible for sync: {output_df['eligible_for_sync'].sum()}")
    print(f"Not eligible: {(~output_df['eligible_for_sync']).sum()}")
    print(f"Missing group after fill: {output_df['group'].isna().sum()}")
    print(f"Missing EASI: {output_df['easi'].isna().sum()}")
except PermissionError:
    print("ERROR: Cannot write emfit_participant_data.csv — close the file first and rerun.")
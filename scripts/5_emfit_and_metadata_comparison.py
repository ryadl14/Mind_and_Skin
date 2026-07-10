import pandas as pd
from pathlib import Path
from datetime import datetime

metadata_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/documentation/MS_Metadata_Copy.csv")
emfit_format_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/emfit_dates.csv")
output_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/n0_comparison.csv")

# === Load metadata ===
metadata_df = pd.read_csv(metadata_path, header=1)

# Rename participant ID column first before dropping other Unnamed columns
metadata_df = metadata_df.rename(columns={'Unnamed: 0': 'ID'})

unnamed_cols = [col for col in metadata_df.columns if col.startswith('Unnamed')]
metadata_df = metadata_df.drop(columns=unnamed_cols)

print(metadata_df.columns.tolist())  # Check what columns exist

metadata_df = metadata_df.rename(columns={'Unnamed: 0': 'ID'}) if 'Unnamed: 0' in metadata_df.columns else metadata_df
metadata_df = metadata_df[metadata_df['ID'].notna()]
metadata_df = metadata_df[['ID', 'N0']].copy()  # Only need ID and N0

# === Load EMFIT metadata format ===
emfit_df = pd.read_csv(emfit_format_path)
emfit_df = emfit_df[['ID', 'N0']].copy()  # Only need ID and N0

# === Normalise metadata ID ===
# MS025A → MS025, keep MS004V1 as is
metadata_df['ID'] = metadata_df['ID'].str.replace(r'A$', '', regex=True).str.strip()

# === Merge on ID ===
merged = pd.merge(metadata_df, emfit_df, on='ID', how='left',
                  suffixes=('_metadata', '_emfit'))

# === Compare dates ===
def parse_date(date_str):
    # Parse date string to datetime, return None if invalid
    if pd.isna(date_str):
        return None
    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d/%m/%y']:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    return None

rows = []
for _, row in merged.iterrows():
    meta_date = parse_date(row['N0_metadata'])
    emfit_date = parse_date(row['N0_emfit'])

    # Calculate difference
    if meta_date and emfit_date:
        diff_days = abs((meta_date - emfit_date).days)
        difference = 'N' if diff_days == 0 else 'Y'
        one_day_flag = 'Y' if diff_days == 1 else 'N'
    else:
        difference = 'N/A'  # Missing data
        one_day_flag = 'N/A'

    rows.append({
        'ID': row['ID'],
        'metadata_N0': row['N0_metadata'],
        'emfit_N0': row['N0_emfit'],
        'difference': difference,
        '1_day_flag': one_day_flag
    })

output_df = pd.DataFrame(rows)

try:
    output_df.to_csv(output_path, index=False)
    print(f"Comparison saved to: {output_path}")
    print(f"\nSummary:")
    print(f"Total participants: {len(output_df)}")
    print(f"Matches:            {len(output_df[output_df['difference'] == 'N'])}")
    print(f"Differences:        {len(output_df[output_df['difference'] == 'Y'])}")
    print(f"1-day differences:  {len(output_df[output_df['1_day_flag'] == 'Y'])}")
    print(f"Missing data:       {len(output_df[output_df['difference'] == 'N/A'])}")
except PermissionError:
    print("ERROR: Cannot write comparison file — close it first and rerun.")
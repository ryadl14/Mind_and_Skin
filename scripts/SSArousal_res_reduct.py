import pandas as pd
from pathlib import Path

processed_dir = Path("C:/Users/ryadl/Desktop/EMFIT_Local/Emfit_1/data/processed")

for participant_dir in processed_dir.glob("MS*"):
    for visit_dir in participant_dir.glob("Visit_*"):
        
        psg_files = list(visit_dir.glob("*_acti_psg_SSandArousal.csv"))
        
        if not psg_files:
            print(f"No PSG file found for {participant_dir.name}/{visit_dir.name}, skipping...")
            continue
        
        psg_file = psg_files[0] # Saves the (hopefully) one file as psg_file.
        print(f"Processing {psg_file.name}...")

        try:
            df = pd.read_csv(psg_file, low_memory=False)
        except pd.errors.EmptyDataError:
            print(f"Empty file, skipping: {psg_file.name}")
            continue
        except UnicodeDecodeError:
            df = pd.read_csv(psg_file, low_memory=False, encoding='latin-1')

        if df.empty:
            print(f"No data in file, skipping: {psg_file.name}")
            continue

        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        df['Scratch'] = df['Scratch'].fillna(0)

        resampled = df.resample('1s').agg({
            'Scratch_Pred': 'mean', # Takes the mean scratch prediction scrore.
            'Scratch': 'max', # Saves the scratch binary as the highest level i.e. if there is a scratch at any point during the second, the entire second is scratch.
            'Sleep.stage': lambda x: x.mode()[0] if not x.mode().empty else None, # Takes the mode of the sleep stage across the second.
            'Is_Arousal': lambda x: x.dropna().iloc[0] if not x.dropna().empty else None # Takes the first non-null value across the second.
        })

        # Save output
        output_path = visit_dir / psg_file.name.replace('_acti_psg_SSandArousal.csv', '_acti_psg_SSandArousal_1s.csv')
        resampled.to_csv(output_path)
        print(f"Saved: {output_path.name}")

print("Done.")
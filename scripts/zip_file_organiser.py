import zipfile
from pathlib import Path

dataset = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/raw") # NOTE EMFIT_1 IN PATH

FILE_TYPE_MAP = { # A dictionary mapping the suffix found in the zip file names.
    'bedexits': 'bedexits',
    'hrv': 'hrv',
    'sleepclasses': 'sleep_classes',
    'tossnturns': 'tossnturns',
    'vitals': 'vitals',
}

for participant in dataset.iterdir(): # Loops over everything in data/raw, skips non-directories and captures their ID's.
    if not participant.is_dir():
        continue
    participant_id = participant.name

    for visit in participant.iterdir(): # Loops over the visit folders in each participant directory, skips non-directories and captures Visit_ into V.
        if not visit.is_dir():
            continue
        visit_num = visit.name.replace("Visit_", "V")

        for night in visit.iterdir(): # Loops over night folders, skips anything that isn't a Night_X directory, converts Night_1 to N1
            if not night.is_dir() or not night.name.startswith("Night_"):
                continue
            night_num = night.name.replace("Night_", "N")
            standard_prefix = f"{participant_id}_{visit_num}_{night_num}" # Builds the standard prefix.

            for zip_file in night.glob("zip/*.zip"): # Finds the zip files.
                summary_csv_dir = night / "summary_csvs"
                summary_csv_dir.mkdir(exist_ok=True)

                with zipfile.ZipFile(zip_file, 'r') as z: # Opens the zip files in read mode and get a list of all the names.
                    all_files = z.namelist()

                    for file in all_files:
                        # Determine file type by checking suffix
                        file_type = None
                        for key in FILE_TYPE_MAP:
                            if file.endswith(f"-{key}.csv"):
                                file_type = FILE_TYPE_MAP[key]
                                break
                        
                        # If no type matched, it's the summary file
                        if file_type is None:
                            file_type = "summary"

                        new_filename = f"{standard_prefix}_{file_type}.csv" # Final name of the files
                        output_path = summary_csv_dir / new_filename

                        if output_path.exists():
                            print(f"Skipping {new_filename} — already exists")
                            continue

                        with z.open(file) as zf:
                            output_path.write_bytes(zf.read())
                            print(f"Extracted: {new_filename}")

print("Done.")
import mne
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
import shutil

raw_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/data/raw")
intermediate_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/data/intermediate")
log_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/logs/header_check_log.csv")

shutil.copytree(raw_dir, intermediate_dir, dirs_exist_ok=True)
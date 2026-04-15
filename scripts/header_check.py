import mne
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
mne.set_log_level('WARNING') # Silences verbose messages

files = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/data/raw")
log = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/logs/header_check_log.csv")

column_names = ['filename', 'participant_id', 'visit', 'night', 'header_start', 'filename_start', 'header_end', 'filename_end', 'offset_minutes', 'match' ]
with open(log, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=column_names, extrasaction='ignore') 
    writer.writeheader()
    
    for edf in files.rglob('*.edf'):
            raw = mne.io.read_raw_edf(edf, preload=False)
            filename = Path(edf).stem
            print (f"Processing {filename}!")
            
            # Default values for participant, visit and night in the event the try block fails before they are created
            participant = None
            visit = edf.parts[-4]
            night = edf.parts[-3]

            try:
                parts = edf.stem.split('_')
                participant = parts[0]
                start_date = parts[2]
                start_time = parts[3]
                
                visit = edf.parts[-4]
                night = edf.parts[-3]

                # Checks if there are more than 4 parts in the filename
                # Checks if the 4th chunk is digits (to counter recordings that cross timezones)
                # Distinguishes between times (4 digits) and dates (8 digits)
                if len(parts) > 4 and parts[4].isdigit() and len(parts[4]) > 4:
                    end_date = parts[4]
                    end_time = parts[5]
                elif parts[4].isdigit(): # Runs when there is no end date (same day recording)
                    end_date = start_date
                    end_time = parts [4]
                else: # Edge case where recording occurs across two different timezones
                    end_date = parts[5]
                    end_time = parts[6]
            except IndexError:
                recording_duration_secs = raw.n_times / raw.info['sfreq']
                header_start_datetime = raw.info['meas_date']
                header_end = header_start_datetime + timedelta(seconds=recording_duration_secs)
                writer.writerow({
                    'filename': edf,
                    'participant_id': participant,
                    'visit': visit,
                    'night': night,
                    'header_start': None,
                    'filename_start': None,
                    'header_end': None,
                    'filename_end': None,
                    'offset_minutes': None,
                    'match': False
                })
                continue
                 

            header_start_datetime = raw.info['meas_date'] # Gets the header start datetime
            
            filename_start_datetime= start_date + " " + start_time
            filename_start_datetime = datetime.strptime(filename_start_datetime, "%Y%m%d %H%M") # Sets the filename date and time as a datetime object
            filename_datetime = filename_start_datetime.replace(tzinfo=timezone.utc) # Sets it as UTC
           
            offset_minutes = header_start_datetime - filename_datetime
            offset_minutes = offset_minutes.total_seconds() / 60 # Gets the minute offset

            if end_time is not None: # In the event there is no end_time
                filename_end_datetime = end_date + " " + end_time
                filename_end_datetime = datetime.strptime(filename_end_datetime, "%Y%m%d %H%M") # Sets the filename date and time as a datetime object
                filename_end_datetime = filename_end_datetime.replace(tzinfo=timezone.utc) # Sets it as UTC
            else:
                 filename_end_datetime = None

            match = abs(offset_minutes - 120) < 1

            recording_duration_secs = raw.n_times / raw.info['sfreq'] # Calculates the seconds in a recording by dividing the number of samples by the sampling frequency.
            header_end = header_start_datetime + timedelta(seconds=recording_duration_secs)

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


    

# Set base directory
EMFIT_DIR="C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1" # < - YOU WILL LIKELY NEED TO CHANGE THIS
echo "Setting up EMFIT at: $EMFIT_DIR"

# ============================
# Creating directory structure
# ============================

echo "Creating directories"
mkdir -p "$EMFIT_DIR/data/raw"
mkdir -p "$EMFIT_DIR/data/intermediate"
mkdir -p "$EMFIT_DIR/data/processed"
mkdir -p "$EMFIT_DIR/scripts"
mkdir -p "$EMFIT_DIR/documentation/"
mkdir -p "$EMFIT_DIR/logs/"

# ==============================================================================
# Creates a log file extracting which Emfit device is used for each participant
# ==============================================================================

# Create the log file with participant_id and emfit_id as headers.
echo "participant_id,emfit_id" > "$EMFIT_DIR/logs/emfit_num_log.csv"

echo "Removing _emfit from participant names and saving to emfit_num_log."
for subject in "$EMFIT_DIR"/MS*; do
    participant_name=$(basename "$subject" | sed "s/_Emfit[^_]*//")  # Extract the MSXX name as participant name
    emfit_num=$(basename "$subject" | sed "s/MS[^_]*_//" | sed "s/_.*//") # Extract the Emfit ID as emfit_num
    if [[ $emfit_num == $participant_name ]]; then
        emfit_num="N/A" # If there is no Emfit_ID, make it N/A.
    fi
    echo "$participant_name, $emfit_num" >> $EMFIT_DIR/logs/emfit_num_log.csv # Append both into the csv file.

    # Checks to make sure the emfit tag has been cut off.
    if [[ "$participant_name" != $(basename "$subject") ]]; then
        mv "$subject" "$EMFIT_DIR/$participant_name" # Renames the folder to just the participant ID's
    fi
done
echo "Log saved to emfit_num_log.csv"

# Removes the trailing _emfit from the visit folders.
for visit in "$EMFIT_DIR"/MS*/Visit_*; do
    visit_name=$(basename "$visit" | sed "s/_Emfit[^_]*//")  # Extract the MSXX name as participant name 
    visit_folder=$(dirname "$visit")

    if [[ "$visit_name" != $(basename "$visit") ]]; then
        mv "$visit" "$visit_folder/$visit_name"
    fi
done


# ==============================================================================
# Migrate all folders to data/raw
# ==============================================================================

echo "Moving EMFIT files and folders under data/raw"
for subject in "$EMFIT_DIR"/MS*; do
    if [[ -d "$subject" ]]; then # Checks subject is a directory
        subject_id=$(basename "$subject") # Grabs the base name of the directory
        subject_dir="$EMFIT_DIR/data/raw/$subject_id" # Sets the name of the directory under the data/raw.
        mv "$subject" "$subject_dir" # Renames and relocates the current directory under data/raw.
    fi
done

echo "Checking edge cases where Visit is in the participant folder name."
for subject_path in "$EMFIT_DIR"/data/raw/MS*; do
    folder_name=$(basename "$subject_path")

    if [[ "$folder_name" == *"Visit"* ]]; then
        echo "Processing edge case: $folder_name"
        visit_number=$(echo "$folder_name" | sed 's/.*[^0-9]//') # Extracts which visit number it is.
        participant_name=$(echo "$folder_name" | cut -d'_' -f1) # Extracts the participant name. 
        mkdir -p "$EMFIT_DIR"/data/raw/"$participant_name"/"Visit_${visit_number}" # Makes a new participant names and visit number nested within it.
        shopt -s dotglob # Allows hidden files to be transferred as well (Necessary?)
        mv "$subject_path"/* "$EMFIT_DIR"/data/raw/"$participant_name"/"Visit_${visit_number}" # Moves everything into the Visit directory
        shopt -u dotglob # Unsets this option (best practice)
        echo "Cleaning up empty files."
        rmdir "$subject_path" # Deletes the now empty original directory.
    else
        echo "Processing standard subject: $folder_name"
    fi
done

shopt -s extglob dotglob # Inverse wildcard, matches everything that ISN'T [pattern]

for subject_path in "$EMFIT_DIR"/data/raw/MS*; do
    if ls "$subject_path"/Visit_1* > /dev/null 2>&1|| ls "$subject_path"/Visit_2* > /dev/null 2>&1; then # If a Visit_1 or Visit_2 folder already exists, skips.
        echo "Visit folder already exists for $(basename "$subject_path"). Skipping..."
        continue
    else
        mkdir -p "$subject_path/Visit_1" # Makes a Visit_1 folder
        mv "$subject_path"/!("Visit_1") "$subject_path/Visit_1" # Moves everything into the Visit_1 folder.   
    fi
done
shopt -u extglob dotglob # Turns it off.

# ==============================================================================
# Night and file type classification 
# ==============================================================================

echo "Sorting files into date and file type folders."
shopt -s extglob
for nights in "$EMFIT_DIR"/data/raw/MS*/Visit_*/@(*.zip|*.edf|*.csv); do
    fname=$(basename "$nights") # Strip the full path, keep just the filename
    stem="${fname%.*}" # Remove file extension to get the filename stem

    # Classify each field by pattern, not position; handles the differing variants in the filenames
    dates=(); times=()
    IFS='_' read -ra parts <<< "$stem" # Splits the stem by underscores into an array
    for p in "${parts[@]}"; do
        [[ "$p" =~ ^[0-9]{8}$ ]] && dates+=("$p") # Dates are 8 digit long patterns e.g. 20250106
        [[ "$p" =~ ^[0-9]{4}$ ]] && times+=("$p") # Times are 4 digit long patterns e.g. 2104
    done

    # Skip files with no recognisable date or time tokens.
    # (e.g. loose summary/log files sitting in the Visit folder)
    if [ ${#dates[@]} -eq 0 ] || [ ${#times[@]} -eq 0 ]; then
        echo "  Skipping (unrecognised filename pattern): $fname"
        continue
    fi

    file_date="${dates[0]}" # First date token = recording start date
    start_hhmm="${times[0]}" # First time token = recording start time
    end_hhmm="${times[${#times[@]}-1]}" # Last time token = recording end time

    # Convert HHMM string to total minutes since midnight for arithmetic, 10# forces base-10 interpretation, preventing parsing errors.
    start_min=$(( 10#${start_hhmm:0:2} * 60 + 10#${start_hhmm:2:2} ))
    end_min=$(( 10#${end_hhmm:0:2} * 60 + 10#${end_hhmm:2:2} ))
    duration=$(( end_min - start_min ))
    [ "$duration" -lt 0 ] && duration=$(( duration + 1440 )) # Add 24h in minutes if recording crossed midnight

    start_hour=$(( 10#${start_hhmm:0:2} )) # Extract hour component for the early-morning check below

    # Assign early-morning continuation recordings to the previous calendar night
    # A recording starting before 09:00 and lasting at least 30 minutes
    # is assumed to be a continuation of the previous night rather than a new day
    if [ "$start_hour" -lt 9 ] && [ "$duration" -ge 30 ]; then 
        night_id=$(date -d "${file_date} -1 day" +%Y%m%d) # Subtract a day so it falls in the previous night.
    else
        night_id="$file_date" # Standard case — use the start date as-is
    fi

    night_folder=$(dirname "$nights")
    file_ext="${nights##*.}"
    mkdir -p "$night_folder/$night_id/$file_ext"
    mv "$nights" "$night_folder/$night_id/$file_ext"
done
shopt -u extglob
    
    

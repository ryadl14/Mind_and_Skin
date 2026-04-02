## Set base project directory
#if [[ $(basename "$PWD") == "Emfit"]]; then
#    EMFIT_DIR=$(realpath "$PWD")
#fi
## ^ Will come back later to adjust conditions.

# Set base directory
EMFIT_DIR="C:/Users/ryadl/Desktop/EMFIT_local/Emfit"
echo "Setting up EMFIT at: $EMFIT_DIR"

# ============================
# Creating directory structure
# ============================

echo "Creating directories"
mkdir -p "$EMFIT_DIR/data/raw"
mkdir -p "$EMFIT_DIR/data/processed"
mkdir -p "$EMFIT_DIR/scripts"
mkdir -p "$EMFIT_DIR/documentation/"
mkdir -p "$EMFIT_DIR/logs/"

# ==============================================
# Creates a log file extracting which Emfit it is
# ===============================================
# Currently running into an issue where the participant ID's have EmfitX at the end. 
# I do not want to delete these in case it is important later, so the goal is save it as an .csv log.

# Create the log file with participant_id and emfit_id as headers.
echo "participant_id,emfit_id" > "$EMFIT_DIR/logs/emfit_num_log.csv"

# Loop throught the directory.
echo "Removing _emfit from participant names and saving to emfit_num_log."
for subject in "$EMFIT_DIR"/MS*; do
    participant_name=$(basename "$subject" | sed "s/_Emfit[^_]*//")  # Extract the MSXX name as participant name
    emfit_num=$(basename "$subject" | sed "s/MS[^_]*_//" | sed "s/_.*//") # Extract the Emfit ID as emfit_num
    if [[ $emfit_num == $participant_name ]]; then
        emfit_num="N/A" # If there is no Emfit_id, N/A.
    fi
    echo "$participant_name, $emfit_num" >> $EMFIT_DIR/logs/emfit_num_log.csv # Append both into the csv file.

    # Checks to make sure the emfit tag has been cut off.
    if [[ "$participant_name" != $(basename "$subject") ]]; then
        mv "$subject" "$EMFIT_DIR/$participant_name" # Renames the folder just the participant ID's
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


# ===============================
# Migrate all folders to data/raw
# ===============================
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

# =====================
# NIGHT AND FILE CLASSIFICATION
# =====================
echo "Creating file specific folders with night folders"
shopt -s extglob
for nights in "$EMFIT_DIR"/data/raw/MS*/Visit_*/@(*.zip|*.edf|*.csv); do
    night_id=$(basename "$nights" | cut -d'_' -f3)
    night_folder=$(dirname "$nights")
    file_ext="${nights##*.}"
    mkdir -p "$night_folder/$night_id/$file_ext" 
    mv "$nights" "$night_folder/$night_id/$file_ext"
done
shopt -u extglob
    
    

ONEDRIVE_DIR="C:/Users/ryadl/OneDrive - King's College London/GSTT DMS - PSG" # Saves the location of the SSandArousal root.
PROCESSED_DIR="$HOME/Desktop/EMFIT_Local/Emfit_1/data/processed"              # Will saved them into my local version in the data/processed directory.

for participant_dir in "$ONEDRIVE_DIR"/MS*/; do # Loops over all participant (MSXX) folders.
    folder_name=$(basename "$participant_dir")  # Saves the folder name.

    # Extract participant ID and visit number
    participant_id=$(echo "$folder_name" | sed 's/V[0-9]*//') # Grabs the participant ID
    visit_num=$(echo "$folder_name" | grep -oE 'V[0-9]+' | grep -oE '[0-9]+') # Grabs the visit number if there is one.

    # Default to Visit_1 if no visit number found
    if [[ -z "$visit_num" ]]; then
        visit_num="1"
    fi

    source_file="$participant_dir/extracted_csv/${folder_name}_acti_psg_SSandArousal.csv" # Creates the source file path.
    dest_dir="$PROCESSED_DIR/$participant_id/Visit_${visit_num}" # Creates the destination file path.
    dest_file="$dest_dir/${folder_name}_acti_psg_SSandArousal.csv"

    # Skip if already copied locally
    if [[ -f "$dest_file" ]]; then
        echo "Already exists locally for $folder_name, skipping..."
        continue
    fi

    if [[ ! -f "$source_file" ]]; then # If there is no SSandArousal file, skips
        echo "No PSG file found for $folder_name, skipping..."
        continue
    fi

    mkdir -p "$dest_dir" # Makes the destination directory
    cp "$source_file" "$dest_dir/" # Copies the file from the EMFIT OneDrive to the destination directory
    echo "Copied PSG file for $folder_name → $dest_dir"
done

echo "Done."
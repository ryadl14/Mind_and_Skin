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

    dest_dir="$PROCESSED_DIR/$participant_id/Visit_${visit_num}" # Makes the destination directory.
    mkdir -p "$dest_dir"

    # === SSandArousal file ===
    source_ss="$participant_dir/extracted_csv/${folder_name}_acti_psg_SSandArousal.csv"
    dest_ss="$dest_dir/${folder_name}_acti_psg_SSandArousal.csv"

    if [[ -f "$dest_ss" ]]; then
        echo "SSandArousal already exists for $folder_name, skipping..."
    elif [[ -f "$source_ss" ]]; then
        cp "$source_ss" "$dest_dir/"
        echo "Copied SSandArousal for $folder_name"
    else
        echo "No SSandArousal file found for $folder_name"
    fi

    # === PSG akti file ===
    source_akti="$participant_dir/${folder_name}_PSG_akti.txt"
    dest_akti="$dest_dir/${folder_name}_PSG_akti.txt"

    if [[ -f "$dest_akti" ]]; then
        echo "PSG akti already exists for $folder_name, skipping..."
    elif [[ -f "$source_akti" ]]; then
        cp "$source_akti" "$dest_dir/"
        echo "Copied PSG akti for $folder_name"
    else
        echo "No PSG akti file found for $folder_name"
    fi

done

echo "Done."
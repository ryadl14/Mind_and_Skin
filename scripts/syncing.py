import pandas as pd

metadata_df = pd.read_csv("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/documentation/MS_Metadata_Copy.csv", header=1) # Loads the metadata
log_df = pd.read_csv("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/logs/emfit_num_log.csv") # Loads the emfit_num_log

# ====
# Cleaning the metadata
# ====

metadata_df = metadata_df.rename(columns={'Unnamed: 0': 'participant_id'}) # Renames the first column as participant_id.
unnamed_cols = [col for col in metadata_df.columns if col.startswith('Unnamed')] # Gets all the column names that start with 'Unnamed' and puts them in a list.
metadata_df = metadata_df.drop(unnamed_cols, axis='columns') # Drops all columns starting with 'Unnamed'


# ====
# Melting the metadata
# ====

melted_metadata = metadata_df.melt(id_vars=['participant_id']) # Melts the dataframe into long format
melted_metadata = melted_metadata.rename(columns={'variable' : 'Night','value' : 'date'}) # Renames the variable and value columns to Night and date.
melted_metadata = melted_metadata.dropna(axis='index') # Removes any rows where night is NA.
print(melted_metadata)

# ====
# Melting the log
# ====

melted_log = log_df.melt(id_vars=['participant_id', 'emfit_id'], var_name="Night")
melted_log = melted_log.rename(columns={'value': 'date'})
melted_log = melted_log.dropna(axis='index')
print (melted_log)

# ====
# There is a difference in syntax between the log and the metadata. The log will be normalised to match the metadata's conventions.
# This includes:
## Nights represented as N0, N1 etc. and 0-indexed, rather than 1-indexed.
## Visit number included in the participant ID (e.g. MS004V1 and MS004V2) 

# Log file normalisation
# ====

melted_log['n_visit'] = melted_log['Night'].str.split('_').str[1] # Parses the Night column and extracts the visit number.
melted_log['n_night'] = melted_log['Night'].str.split('_').str[3].astype(int) # Parses the Night column and extracts the night number.
melted_log['n_night'] = melted_log['n_night'] - 1 # Normalise night 1 into night 0


unique_visits = melted_log.groupby('participant_id')['n_visit'].nunique() # Creates a series with the number of visits for each participant

melted_log['unique_visits'] = melted_log['participant_id'].map(unique_visits) # Creates a column called unique_visits, which maps the number of visits to the correct participant.

melted_log['participant_id'] = melted_log.apply(
    lambda row: row['participant_id'] + f'V{row["n_visit"]}' if row['unique_visits'] > 1 else row['participant_id'], axis=1 # Looks at each of the participant_id rows, and add V followed by the number of visits, only if the number of visits is greater than 1, effectively making it so that only V2 is possible. otherwise, leave the participant_id as is
)

# Reorder log
    
with pd.option_context('display.max_rows', None, 'display.max_columns', None):  # more options can be specified also
    print(melted_log)



import pandas as pd

metadata_df = pd.read_csv("C:/Users/ryadl/Desktop/EMFIT_local/Emfit/documentation/MS_Metadata_Copy.csv", header=1)
log_df = pd.read_csv("C:/Users/ryadl/Desktop/EMFIT_local/Emfit5/logs/emfit_num_log.csv")

print("==================================")
print("METADATA")
print("==================================")
print(metadata_df[10:17])
print("==================================")
print("LOG")
print("==================================")
print(log_df)
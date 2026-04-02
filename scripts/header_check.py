import mne
raw = mne.io.read_raw_edf("C:/Users/ryadl/Desktop/MS40_Emfit1_20240924_1413_20240925_2052_UTC+1.edf", preload=False)
print(raw.info)
print(raw.ch_names)

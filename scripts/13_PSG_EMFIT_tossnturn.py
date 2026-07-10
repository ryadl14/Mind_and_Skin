import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate, resample, hilbert
from scipy.ndimage import uniform_filter1d
from scipy.stats import pearsonr
import mne
from pathlib import Path
from datetime import datetime
import re

mne.set_log_level('WARNING')

# === Paths ===
raw_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/raw")
intermediate_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/intermediate")
processed_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/data/processed")
n0_comparison_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/n0_comparison.csv")
emfit_num_log_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/emfit_num_log.csv")
participant_data_path = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/logs/emfit_participant_data.csv")

# === Constants ===
PSG_FS = 32
EMFIT_FS = 100
SMOOTH_WINDOW_S = 10
CORR_ZOOM_S = 600
MAX_LAG_SECONDS = 3600  # ±1 hour — PSG starts at scheduled time, EMFIT starts when participant gets into bed


def resolve_participant_visit(row_id, raw_dir):
    """Parse a row_id like 'MS8' or 'MS53V1' into (base_id, visit_dir_name)."""
    match = re.match(r'(MS\d+)(V(\d+))?$', row_id)
    if not match:
        raise ValueError(f"Could not parse row_id: {row_id}")
    base_id = match.group(1)
    visit_num = match.group(3)

    participant_path = raw_dir / base_id
    if not participant_path.exists():
        raise FileNotFoundError(f"No raw folder found for {base_id}")

    if visit_num:
        visit_dir_name = f"Visit_{visit_num}"
        if not (participant_path / visit_dir_name).exists():
            raise FileNotFoundError(f"No {visit_dir_name} folder for {base_id}")
    else:
        visit_dirs = sorted(participant_path.glob("Visit_*"))
        if len(visit_dirs) != 1:
            raise ValueError(f"Expected exactly one visit for {base_id}, found {len(visit_dirs)}")
        visit_dir_name = visit_dirs[0].name

    return base_id, visit_dir_name

def get_start_hour(filename: str) -> int:
    """Extract start hour from an EMFIT filename, robust to variable field
    counts (mid-recording UTC labels, rollover dates)."""
    times = [t for t in filename.split('_') if re.fullmatch(r'\d{4}', t)]
    if not times:
        raise ValueError(f"Could not parse start time from {filename}")
    return int(times[0][:2])


def find_n0_row(n0_df, base_id, visit_dir_name):
    """Padding-aware lookup of a participant's row in n0_comparison.csv."""
    match = re.match(r'MS0*(\d+)$', base_id)
    if not match:
        return pd.DataFrame()
    num = int(match.group(1))
    visit_suffix = visit_dir_name.replace('Visit_', 'V')
    candidate_ids = [
        f"MS{num:03d}", f"MS{num:03d}{visit_suffix}",
        f"MS{num:02d}", f"MS{num:02d}{visit_suffix}",
        f"MS{num}", f"MS{num}{visit_suffix}",
    ]
    for cid in candidate_ids:
        row = n0_df[n0_df['ID'].str.strip() == cid]
        if not row.empty:
            return row
    return pd.DataFrame()


def fix_rollover(psg):
    hms = pd.to_timedelta(psg['HMS'].str.strip())
    rollover = 0
    corrected = []
    for i in range(len(hms)):
        if i > 0 and hms.iloc[i] < hms.iloc[i - 1]:
            rollover += 1
        corrected.append(hms.iloc[i] + pd.to_timedelta(rollover, unit='day'))
    return pd.to_timedelta(corrected)


def process_participant(row_id):
    result = {
        'participant_id': row_id,
        'lag_seconds': None,
        'lag_warning': '',
        'toss_turn_count': None,
        'scratch_count': None,
        'recording_duration_hours': None,
        'toss_turn_per_hour': None,
        'scratch_per_hour': None,
        'sync_correlation_psg': None,
        'sync_correlation_pvalue': None,
        'sync_status': 'OK',
        'error_reason': ''
    }


    try:
        base_id, visit_dir_name = resolve_participant_visit(row_id, raw_dir)
        PARTICIPANT = base_id
        VISIT = visit_dir_name

        processed_participant_dir = processed_dir / base_id / visit_dir_name
        intermediate_participant_dir = intermediate_dir / base_id / visit_dir_name

        # === Load PSG akti file (default / V1 / V2 fallback) ===
        akti_path = processed_participant_dir / f"{PARTICIPANT}_PSG_akti.txt"
        if not akti_path.exists():
            v1_path = processed_participant_dir / f"{PARTICIPANT}V1_PSG_akti.txt"
            v2_path = processed_participant_dir / f"{PARTICIPANT}V2_PSG_akti.txt"
            if VISIT == "Visit_1" and v1_path.exists():
                akti_path = v1_path
            elif VISIT == "Visit_2" and v2_path.exists():
                akti_path = v2_path
            else:
                raise FileNotFoundError(f"No akti file found for {PARTICIPANT} {VISIT}")

        akti = pd.read_csv(akti_path, sep='\t')
        akti['time_delta'] = fix_rollover(akti)

        # === True PSG date from n0_comparison.csv ===
        n0_df = pd.read_csv(n0_comparison_path)
        n0_row = find_n0_row(n0_df, base_id, visit_dir_name)
        if n0_row.empty:
            raise ValueError(f"Could not find {row_id} in n0_comparison.csv")

        psg_date_str = n0_row['metadata_N0'].values[0]
        psg_date = datetime.strptime(psg_date_str.strip(), "%d/%m/%Y").date()

        akti_start_hms = akti['HMS'].iloc[0].strip()
        h, m, s = akti_start_hms.split(':')
        akti_start_dt = datetime.combine(psg_date, datetime.min.time()).replace(
            hour=int(h), minute=int(m), second=int(float(s))
        )

        
        ## THIS HAS NOT BEEN TESTED, PREVIOUSLY JUST SELECTED THE LONGEST NIGHT ## 
        
        # === Longest night-window EDF in Night_0 ===
        edf_dir = intermediate_participant_dir / "Night_0" / "edf"
        edf_candidates = list(edf_dir.glob("*.edf"))
        if not edf_candidates:
            raise FileNotFoundError(f"No Night_0 EDF found for {row_id}")

        # Restrict to files starting in the night window (20:00-08:59) — excludes
        # daytime naps/recordings that happen to share this Night_0 folder.
        night_candidates = [
            p for p in edf_candidates
            if get_start_hour(p.name) >= 20 or get_start_hour(p.name) < 9
        ]

        if not night_candidates:
            raise FileNotFoundError(
                f"No night-window EDF files found for {row_id} Night_0 "
                f"(found {len(edf_candidates)} daytime-only files)"
            )

        if len(edf_candidates) > len(night_candidates):
            print(f"{row_id}: excluded {len(edf_candidates) - len(night_candidates)} daytime file(s) from selection")

        # Check duration of each night-window candidate without loading full data
        durations = []
        for path in night_candidates:
            raw_header = mne.io.read_raw_edf(path, preload=False)
            durations.append(raw_header.n_times / raw_header.info['sfreq'])

        if len(night_candidates) > 1:
            print(f"{row_id}: WARNING — {len(night_candidates)} night-window fragments found for Night_0 — "
                  f"selecting longest only; other fragment(s) excluded from this analysis")

        edf_path = night_candidates[durations.index(max(durations))]

        raw = mne.io.read_raw_edf(edf_path, preload=True)
        bcg_channel = 'BCG-Raw-Low' if 'BCG-Raw-Low' in raw.ch_names else 'BCG-Raw-High'
        emfit_signal = raw.get_data(picks=bcg_channel)[0]

        # === Downsample, normalise, envelope ===
        downsample_factor = EMFIT_FS / PSG_FS
        n_samples_psg_rate = int(len(emfit_signal) / downsample_factor)
        emfit_downsampled = resample(emfit_signal, n_samples_psg_rate)

        psg_signal = akti['Akti.ext.'].values
        psg_norm = (psg_signal - np.nanmean(psg_signal)) / (np.nanstd(psg_signal) + 1e-12)
        emfit_norm = (emfit_downsampled - np.nanmean(emfit_downsampled)) / (np.nanstd(emfit_downsampled) + 1e-12)

        smooth_window_samples = SMOOTH_WINDOW_S * PSG_FS
        psg_smooth = uniform_filter1d(np.abs(hilbert(psg_norm)), size=smooth_window_samples)
        emfit_smooth = uniform_filter1d(np.abs(hilbert(emfit_norm)), size=smooth_window_samples)

        # === Cross-correlation, constrained to ±MAX_LAG_SECONDS ===
        correlation_full = correlate(psg_smooth, emfit_smooth, mode='full')
        lags_full = np.arange(-(len(emfit_smooth) - 1), len(psg_smooth))

        lag_window_mask = (lags_full / PSG_FS >= -MAX_LAG_SECONDS) & (lags_full / PSG_FS <= MAX_LAG_SECONDS)
        constrained_lags = lags_full[lag_window_mask]
        constrained_corr = correlation_full[lag_window_mask]
        lag_samples = constrained_lags[np.argmax(constrained_corr)]
        lag_seconds = lag_samples / PSG_FS

        global_max_lag = lags_full[np.argmax(correlation_full)] / PSG_FS
        lag_warning = ''
        if abs(global_max_lag - lag_seconds) > 5:
            lag_warning = f"Unconstrained max ({global_max_lag:.1f}s) vs constrained ({lag_seconds:.1f}s)"

        # === Apply lag correction to EMFIT signal ===
        lag_samples_emfit = int(abs(lag_seconds) * EMFIT_FS)
        if lag_seconds < 0:
            emfit_aligned = emfit_signal[lag_samples_emfit:]
        else:
            emfit_aligned = np.pad(emfit_signal, (lag_samples_emfit, 0))

        emfit_aligned_ds = resample(emfit_aligned, int(len(emfit_aligned) / downsample_factor))
        emfit_aligned_ds_norm = (emfit_aligned_ds - np.nanmean(emfit_aligned_ds)) / (np.nanstd(emfit_aligned_ds) + 1e-12)
        emfit_aligned_envelope = uniform_filter1d(np.abs(hilbert(emfit_aligned_ds_norm)), size=smooth_window_samples)

        full_duration_samples = min(len(psg_smooth), len(emfit_aligned_envelope))
        full_duration_seconds = full_duration_samples / PSG_FS

        # === Toss/turn + scratch — NO lag correction, already true wall-clock ===
        tt_files = list(processed_participant_dir.glob("*_acti_psg_SSandArousal_1s_tt.csv"))
        if not tt_files:
            raise FileNotFoundError(f"No _1s_tt file found for {row_id}")

        tt_df = pd.read_csv(tt_files[0])
        tt_df['Date'] = pd.to_datetime(tt_df['Date'])

        tossnturn_rows = tt_df[tt_df['tossnturn'] == 1]
        tossnturn_seconds = (tossnturn_rows['Date'] - akti_start_dt).dt.total_seconds().values

        scratch_rows = tt_df[tt_df['Scratch'] == 1]
        scratch_seconds = (scratch_rows['Date'] - akti_start_dt).dt.total_seconds().values

        toss_turn_count = len(tossnturn_seconds)
        scratch_count = len(scratch_seconds)

        recording_duration_seconds = (tt_df['Date'].iloc[-1] - tt_df['Date'].iloc[0]).total_seconds()
        recording_duration_hours = recording_duration_seconds / 3600

        toss_turn_per_hour = toss_turn_count / recording_duration_hours if recording_duration_hours > 0 else None
        scratch_per_hour = scratch_count / recording_duration_hours if recording_duration_hours > 0 else None

        # === Sync quality: correlate 1Hz binary toss/turn indicator against PSG envelope ===
        sync_correlation_psg = None
        sync_correlation_pvalue = None
        error_reason = ''

        if toss_turn_count > 0:
            full_duration_int = int(full_duration_seconds)
            psg_1hz = np.array([
                np.mean(psg_smooth[i * PSG_FS:(i + 1) * PSG_FS])
                for i in range(full_duration_int)
            ])
            toss_turn_binary = np.zeros(full_duration_int)
            valid_seconds = tossnturn_seconds[
                (tossnturn_seconds >= 0) & (tossnturn_seconds < full_duration_int)
            ].astype(int)
            toss_turn_binary[valid_seconds] = 1

            if toss_turn_binary.sum() > 0 and np.nanstd(psg_1hz) > 0:
                corr_coef, p_value = pearsonr(psg_1hz, toss_turn_binary)
                sync_correlation_psg = corr_coef
                sync_correlation_pvalue = p_value
        else:
            error_reason = 'No toss/turn events detected'

        # === Build and save combined figure (always overwritten) ===
        fig, axs = plt.subplots(2, 1, figsize=(16, 10))

        mask = (lags_full / PSG_FS >= lag_seconds - CORR_ZOOM_S) & (lags_full / PSG_FS <= lag_seconds + CORR_ZOOM_S)
        axs[0].plot(lags_full[mask] / PSG_FS, correlation_full[mask])
        axs[0].axvline(x=lag_seconds, color='r', linestyle='--', label=f'Peak lag: {lag_seconds:.2f}s')
        axs[0].set_xlim(lag_seconds - CORR_ZOOM_S, lag_seconds + CORR_ZOOM_S)
        axs[0].set_title(f'Cross-correlation — {PARTICIPANT} {VISIT} (zoomed to peak ±{CORR_ZOOM_S}s)')
        axs[0].set_xlabel('Lag (seconds)')
        axs[0].set_ylabel('Correlation')
        axs[0].legend()

        time_axis_full = np.linspace(0, full_duration_seconds, full_duration_samples)
        axs[1].plot(time_axis_full, psg_smooth[:full_duration_samples], label='PSG envelope', alpha=0.7)
        axs[1].plot(time_axis_full, emfit_aligned_envelope[:full_duration_samples], label='EMFIT envelope (aligned)', alpha=0.7)

        y_max = max(np.nanmax(psg_smooth[:full_duration_samples]), np.nanmax(emfit_aligned_envelope[:full_duration_samples]))

        tt_in_range = tossnturn_seconds[(tossnturn_seconds >= 0) & (tossnturn_seconds <= full_duration_seconds)]
        scratch_in_range = scratch_seconds[(scratch_seconds >= 0) & (scratch_seconds <= full_duration_seconds)]

        if len(tt_in_range) > 0:
            axs[1].eventplot(tt_in_range, lineoffsets=-0.06 * y_max, linelengths=0.08 * y_max, colors='green', alpha=0.8, label='Toss/turn')
        if len(scratch_in_range) > 0:
            axs[1].eventplot(scratch_in_range, lineoffsets=-0.16 * y_max, linelengths=0.08 * y_max, colors='red', alpha=0.8, label='Scratch')

        axs[1].set_ylim(-0.25 * y_max, y_max * 1.05)

        psg_start_timedelta = akti['time_delta'].iloc[0]

        def seconds_to_hms(seconds_from_psg_start):
            absolute = psg_start_timedelta + pd.to_timedelta(seconds_from_psg_start, unit='s')
            total_seconds = int(absolute.total_seconds())
            h = (total_seconds // 3600) % 24
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            return f"{h:02d}:{m:02d}:{s:02d}"

        n_ticks = 10
        tick_positions = np.linspace(0, full_duration_seconds, n_ticks)
        tick_labels = [seconds_to_hms(t) for t in tick_positions]

        axs[1].set_title(f'Full-night aligned envelopes — {PARTICIPANT} {VISIT} (PSG starts {seconds_to_hms(0)})')
        axs[1].set_xlabel('Time (HH:MM:SS)')
        axs[1].set_ylabel('Envelope amplitude')
        axs[1].set_xticks(tick_positions)
        axs[1].set_xticklabels(tick_labels, rotation=30)
        axs[1].legend()

        plt.tight_layout()
        save_path = processed_participant_dir / f"{PARTICIPANT}_sync_plot.png"
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

        # === Save lag to emfit_num_log.csv ===
        log_df = pd.read_csv(emfit_num_log_path)
        if 'EMFIT_PSG_lag_seconds' not in log_df.columns:
            log_df['EMFIT_PSG_lag_seconds'] = None
        participant_match = log_df['participant_id'].str.strip() == base_id
        if participant_match.any():
            log_df.loc[participant_match, 'EMFIT_PSG_lag_seconds'] = round(lag_seconds, 2)
            log_df.to_csv(emfit_num_log_path, index=False)

        result.update({
            'lag_seconds': round(lag_seconds, 2),
            'lag_warning': lag_warning,
            'toss_turn_count': toss_turn_count,
            'scratch_count': scratch_count,
            'recording_duration_hours': round(recording_duration_hours, 2),
            'toss_turn_per_hour': round(toss_turn_per_hour, 2) if toss_turn_per_hour is not None else None,
            'scratch_per_hour': round(scratch_per_hour, 2) if scratch_per_hour is not None else None,
            'sync_correlation_psg': round(sync_correlation_psg, 4) if sync_correlation_psg is not None else None,
            'sync_correlation_pvalue': sync_correlation_pvalue,
            'sync_status': 'OK',
            'error_reason': error_reason
        })

    except Exception as e:
        result['sync_status'] = 'FAILED'
        result['error_reason'] = str(e)

    return result


# === Main loop ===
participant_df = pd.read_csv(participant_data_path)
eligible = participant_df[
    (participant_df['eligible_for_sync'] == True) &
    (participant_df['has_ssarousal_tt'] == 'Y')
]

print(f"Processing {len(eligible)} eligible participants...\n")

results = []
for row_id in eligible['participant_id']:
    print(f"=== {row_id} ===")
    res = process_participant(row_id)
    if res['sync_status'] == 'OK':
        print(f"  Lag: {res['lag_seconds']}s | Toss/turn: {res['toss_turn_count']} | "
              f"Scratch: {res['scratch_count']} | Sync corr: {res['sync_correlation_psg']}")
        if res['lag_warning']:
            print(f"  WARNING: {res['lag_warning']}")
        if res['error_reason']:
            print(f"  NOTE: {res['error_reason']}")
    else:
        print(f"  FAILED: {res['error_reason']}")
    results.append(res)

# === Merge results back into emfit_participant_data.csv ===
new_cols = ['lag_seconds', 'lag_warning', 'toss_turn_count', 'scratch_count',
            'recording_duration_hours', 'toss_turn_per_hour', 'scratch_per_hour',
            'sync_correlation_psg', 'sync_correlation_pvalue', 'sync_status', 'error_reason']

for col in new_cols:
    if col not in participant_df.columns:
        participant_df[col] = None

results_lookup = {r['participant_id']: r for r in results}
for idx, row in participant_df.iterrows():
    pid = row['participant_id']
    if pid in results_lookup:
        for col in new_cols:
            participant_df.at[idx, col] = results_lookup[pid].get(col)

try:
    participant_df.to_csv(participant_data_path, index=False)
    print(f"\nUpdated: {participant_data_path}")
except PermissionError:
    print("\nERROR: Cannot write emfit_participant_data.csv — close the file first and rerun.")

# === Summary ===
n_ok = sum(1 for r in results if r['sync_status'] == 'OK')
n_failed = sum(1 for r in results if r['sync_status'] == 'FAILED')
warned = [r['participant_id'] for r in results if r['lag_warning']]

print(f"\n=== SUMMARY ===")
print(f"Succeeded: {n_ok} | Failed: {n_failed}")
if warned:
    print(f"Lag warnings (worth a manual spot-check): {warned}")
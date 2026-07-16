# Mind & Skin — EMFIT Sleep Data Pipeline

A reproducible pipeline to clean, standardise, and synchronise under-mattress
**EMFIT QS** ballistocardiography (BCG) sleep recordings against **polysomnography
(PSG)** and **wrist actigraphy**, and to quantify nocturnal restlessness
(toss-and-turns), scratching, and sleep duration in adolescents with atopic
dermatitis (AD).

Built for the **Mind & Skin** study — a longitudinal investigation at Guy's & St
Thomas' NHS Foundation Trust and King's College London into the relationship
between AD and nocturnal sleep disruption in adolescents.

> **Research question:** Are toss & turn events more frequent in adolescents with
> atopic dermatitis than in controls?

---

## Study at a glance

Participants (~70, IDs `MS001`–`MS089`, not all populated) fall into three groups,
each seen across two visits of ~15 nights:

- **Group 1** — AD with systemic therapy (`#E69F00`)
- **Group 2** — AD without systemic therapy (`#56B4E9`)
- **Group 3** — Healthy control (`#009E73`)

On **Night 0** of each visit, three devices record concurrently: **PSG** (gold-standard
staging, ground truth, Night 0 only), **EMFIT QS** (under-mattress BCG at 100 Hz,
all nights), and **wrist actigraphy** (a
collaborator's model provides scratch predictions, all nights).

> ⚠️ Raw EMFIT data must be downloaded from the EMFIT servers within **7 days** of
> recording, or it is permanently deleted.

---

## Requirements

- **Python** 3.13.2 (developed in the `mind_skin` conda environment)
- **Bash** (for the `.sh` orchestration scripts)

| Package      | Version | Purpose |
|--------------|---------|---------|
| pandas       | 2.3.3   | Dataframe manipulation, CSV I/O |
| numpy        | 2.2.6   | Numerical arrays, signal processing |
| mne          | 1.11.0  | EDF reading and header extraction |
| edfio        | 0.4.13  | EDF header writing / correction |
| matplotlib   | 3.10.7  | Plotting and figure generation |
| scipy        | 1.16.3  | Signal processing, statistical tests |
| seaborn      | 0.13.2  | Statistical visualisation |
| great-tables | 0.22.0  | Publication-ready HTML tables |

Standard library modules (`pathlib`, `csv`, `shutil`, `re`, `datetime`, `zoneinfo`)
ship with the interpreter.

```bash
git clone https://github.com/ryadl14/Mind_and_Skin.git
conda create -n mind_skin python=3.13.2
conda activate mind_skin
pip install pandas==2.3.3 numpy==2.2.6 mne==1.11.0 edfio==0.4.13 \
            matplotlib==3.10.7 scipy==1.16.3 seaborn==0.13.2 great-tables==0.22.0
```

> The pipeline was developed on Windows with data under
> `C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1/`. **Update the path constants at the
> top of each script before running on a new machine or HPC.** Raw OneDrive data is
> downloaded locally so the originals are never modified.

---

## Directory layout

`preprocessing_script.sh` builds and populates this structure; all scripts assume it
exists.

```
Emfit_1/
├── data/
│   ├── raw/            # untouched original files (never modified)
│   │   └── MSXX/Visit_X/Night_X/
│   │       ├── edf/            # raw EDF signal files
│   │       ├── csv/            # raw CSV files
│   │       ├── zip/            # EMFIT summary ZIPs
│   │       └── summary_csvs/   # extracted from ZIPs
│   ├── intermediate/   # EDF copies with timezone-corrected headers
│   └── processed/      # derived outputs (PSG_akti, SSandArousal, sync plots)
├── scripts/
├── documentation/
└── logs/
```

Participant IDs follow `MSxx` (single visit) or `MSxxVX` (multi-visit). Raw
recording filenames follow:

```
MSxx_Emfitx_<startdate:yyyymmdd>_<starttime:hhmm>_<enddate:yyyymmdd>_<endtime:hhmm>_UTC±h
e.g. MS36_Emfit3_20240724_2250_20240725_1241_UTC+1
```

### Key log files (`logs/`)

| File | Purpose |
|------|---------|
| `emfit_num_log.csv` | Maps participant + visit → night numbers; stores EMFIT device ID and `lag_seconds` after sync. **Contains device serials — kept out of the public repo (see below).** |
| `emfit_dates.csv` | EMFIT Night 0 date from filenames, formatted to match metadata (`MS032V1` style). |
| `n0_comparison.csv` | EMFIT Night 0 vs PSG metadata date, side by side; drives `night_renamer.py`. |
| `emfit_participant_data.csv` | Master audit file: data-availability flags, sync eligibility, lag, toss/turn + scratch counts, sync correlation. |
| `header_check_log.csv` | EDF header vs filename timestamp comparison; offset (minutes) and match flag. |
| `hardcoded_date_correction.csv` | Manual corrections for MS028, MS063V2 (year typos) and MS064 (flat shift). |
| `headers_corrected.txt` | Guard file (in `intermediate/`) tracking which EDF headers have been timezone-corrected — prevents double-subtraction on re-run. |

---

## Pipeline

Run the scripts **in this order** — each depends on the outputs of the one before
it. Skipping or reordering steps can silently corrupt downstream outputs. Some, but not all, scripts are
idempotent (guarded against re-runs).

| #  | Script | Purpose |
|----|--------|---------|
| 1  | `preprocessing_script.sh` | Build directory structure; strip `_EmfitX` suffixes (device serial → `emfit_num_log.csv`); sort files into dated → `edf/`/`csv/`/`zip/` folders. |
| 2  | `night_classifier.py` | Rename dated folders (`YYYYMMDD` → `Night_0`, `Night_1`, …), earliest date = Night 0; write `emfit_num_log.csv` + `emfit_dates.csv`. **Now includes a post-midnight heuristic — see note below.** |
| 3  | `header_check.py` | Verify EDF header timestamp matches filename; handles 4 filename variants (1-/2-day × DST); log offsets to `header_check_log.csv`. |
| 4  | `intermediate_edf_standardiser.py` | Copy EDFs to `intermediate/`; convert headers EEST (UTC+2) → UK local (DST-aware via `zoneinfo`); guard via `headers_corrected.txt`; rename mismatched filenames. |
| 5  | `emfit_and_metadata_syncing.py` | Compare EMFIT Night 0 vs curated PSG metadata date → `n0_comparison.csv` (`difference` = Y/N/blank). |
| 6  | `night_renamer.py` | Re-anchor night labels so **Night 0 = the PSG visit night**; two-pass rename (`_tmp` suffix) to avoid chain collisions; applies hardcoded corrections. |
| 7  | `zip_file_organiser.py` | Unzip summary archives → `MSXX_VX_NX_<suffix>.csv` in `summary_csvs/` (suffixes: bedexits, hrv, sleepclasses, tossnturns, vitals; no suffix = summary). |
| 8  | `PSG_importer.sh` | Download Night 0 `acti_psg_SSandArousal.csv` (32 Hz; scratch, scratch-prediction, sleep stage, arousal) and `PSG_akti.txt` (raw 32 Hz actigraphy) into `processed/`. |
| 9  | `SSArousal_res_reduct.py` | Resample SSandArousal 32 Hz → 1 Hz (scratch = ≥50% of second; stage = mode; arousal = any). **Overwrites the 32 Hz file.** |
| 10 | `tossnturn_SSArousal_merge.py` | Merge EMFIT toss/turn events (UNIX → UK local) into the 1 s SSandArousal file → `MSXX_acti_psg_SSandArousal_1s_tt.csv`. |
| 11 | `PSG_EMFIT_sync.ipynb` | Per-night interactive sync: select EDF, extract `BCG-Raw-Low`, z-score + Hilbert-envelope both signals, cross-correlate for lag, apply correction, overlay toss/turn + scratch rug plots. **Includes EDF-selection + lag-constraint heuristics — see note below.** |
| 12 | `data_audit.py` | Build `emfit_participant_data.csv`: availability flags + `eligible_for_sync` (needs Night 0 EDF **and** PSG akti); group/EASI lookup. |
| 13 | `PSG_EMFIT_tossnturn.py` | Batch version of the sync notebook across all eligible participants (try/except-isolated); writes lag, counts, rates, and sync-correlation metrics back to the audit file + a sync PNG each. |
| 14 | `tossnturn_analysis.ipynb` | Core research question: group comparisons of toss/turn + scratch counts/rates and sleep duration; EASI scatterplots (Groups 1 & 2). |
| 15 | `baseline_comparison.ipynb` | Demographic/clinical baseline: age (Kruskal–Wallis), gender (Chi-square), EASI (Mann–Whitney U), onset <2 yrs (Fisher's exact). |
### Running it

```bash
conda activate mind_skin

bash   scripts/preprocessing_script.sh
python scripts/night_classifier.py
python scripts/emfit_and_metadata_syncing.py
python scripts/night_renamer.py
python scripts/header_check.py
python scripts/intermediate_edf_standardiser.py
python scripts/zip_file_organiser.py
bash   scripts/PSG_importer.sh
python scripts/SSArousal_res_reduct.py
python scripts/tossnturn_SSArousal_merge.py
# open PSG_EMFIT_sync.ipynb for interactive single-participant syncing
python scripts/data_audit.py
python scripts/PSG_EMFIT_tossnturn.py
# open tossnturn_analysis.ipynb and baseline_comparison.ipynb for analysis
```

> **Current state:** 27 participants are eligible for sync and processed
> successfully through `PSG_EMFIT_tossnturn.py`.
> `emfit_participant_data.csv` is the definitive record of results.

---

## ⚠️ Heuristics added since the handover documentation

The handover documentation **predates** two heuristics
that are now part of the code. Where the doc says these steps don't handle an edge
case, the current code does:

- **`night_classifier.py` — post-midnight recording starts.** The documentation notes
  this script "does not account for post-midnight recording starts." That is now
  handled: a recording that **starts before 09:00 and lasts ≥30 minutes** is rolled
  back and assigned to the **previous calendar night**, so recordings that begin after
  midnight are no longer misclassified as their own separate night. Token-based
  filename parsing (8-digit = date, 4-digit = time) makes this robust across all four
  filename variants.
- **`PSG_EMFIT_sync.ipynb` — EDF selection and lag constraint.** Beyond simply taking
  the longest EDF, the notebook now selects the longest EDF whose start falls within a
  valid overnight window, avoiding daytime or fragment files being chosen for a night.
  The cross-correlation lag search is also constrained to **±1 hour
  (`MAX_LAG_SECONDS = 3600`)**, with a warning printed whenever the unconstrained
  global maximum diverges from the constrained result by more than 5 seconds — those
  participants should be spot-checked against their sync plots.

---

## Key methodological notes

- **Lag correction applies to the BCG signal only.** `lag_seconds` aligns the raw EMFIT
  BCG array to the PSG recording. **Never** add it to toss/turn or scratch timestamps in
  `SSandArousal_1s_tt` — those are already true, device-independent wall-clock times.
- **Do not re-run `intermediate_edf_standardiser.py`** on already-corrected files without
  checking `headers_corrected.txt`; a re-run subtracts another 2 hours, permanently
  desynchronising every header.
- **EEST offset.** Every EMFIT header sits 120 min ahead because EMFIT's servers run on
  Finnish time (EEST = UTC+2); confirmed directly with EMFIT.
- **Statistics.** Non-parametric throughout (Mann–Whitney U for two groups, Kruskal–Wallis
  for three, Spearman for correlations), justified by small groups, right-skewed rate
  distributions, and sensor-outlier robustness. Chi-square vs. Fisher's exact chosen on
  cell-count thresholds.
- **Rates, not counts.** Toss/turn and scratch counts are normalised per hour of *true*
  sleep (seconds where sleep stage ≠ Wake), controlling for differing sleep durations.

---

## Known issues (per-participant)

Handled in the current codebase; documented so future developers know why. IDs are
pseudonymised study identifiers.

| Participant | Issue |
|-------------|-------|
| MS016 / MS022 | Unexplained 180-min header offsets on some nights — flagged. |
| MS026 | >20 days of recordings (valid — do not truncate); Night 0 EDF has **no `BCG-Raw-Low`** → falls back to `BCG-Raw-High` (noisier envelope). |
| MS027 | Nights 1 & 2 swapped (filenames entered in wrong order by study team). |
| MS028 | Metadata year typo → hardcoded correction. |
| MS032 V1 | Bunk-bed signal interference. |
| MS033 | 51-hour EDF; no toss/turn events detected; −39.88 min offset on Night 11. |
| MS034 V2 | No toss/turn events detected. |
| MS041 | October 2024 DST boundary mid-study — dedicated parser path; Night 5 has an unexplained 414-min offset (flagged). |
| MS063 V2 | Metadata year typo → hardcoded correction. |
| MS064 | EMFIT started ~2 months late; flat shift of +1 (first EMFIT night = Night 1). |
| MS071 | KCL suffix requires manual rename. |
| MS073 | Multi-UTC-offset filename. |
| MS035 V1 N1 | EDF manually copied to `intermediate/`. |
| MS04 / MS42 / MS51 | `LOOKUP_OVERRIDES` in `data_audit.py` match the **unsuffixed** `row_id`; if a two-visit `row_id` is generated, group/EASI silently returns `None`. Verify these three after every audit run. |

---

## Roadmap / future work

- **Recover ineligible participants** currently missing a Night 0 EDF or PSG akti file.
- **Use all recording nights** (not just Night 0) to increase sample size — Night 0 was
  restricted to PSG validation.
- **HPC / Nextflow migration** — abstracting the hardcoded Windows/OneDrive paths is the
  prerequisite; target SLURM on the university cluster.
- **Toss/turn classification** — EMFIT's algorithm is a black box; options include
  detecting rhythmic scratch signatures in the EDF waveform or training a neural-network
  toss/turn classifier on manually labelled infrared night footage.

---

## Sensitive data

Raw sleep data lives on OneDrive and is **not** in this repository. All logs (e.g. `emfit_num_log.csv`, which stores EMFIT device serials) are
excluded.

---

## Author & acknowledgements

**Ryad Lachemi** — MSc Applied Bioinformatics, King's College London.

Supervisor: Dr Alessandra Vigilante. With thanks to Xin Yi Ng (actigraphy scratch
detection model and pre-synced SSandArousal files) and the Mind & Skin team at Guy's &
St Thomas'.

## Citation

> Lachemi, R. (2026) *A validated study investigating gross body movement during sleep in
> adolescents with atopic dermatitis.* MSc Dissertation, King's College London.

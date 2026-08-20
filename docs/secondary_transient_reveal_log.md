# 200 W/20 kW PMSM secondary validation reveal log

## Pre-reveal checkpoint

Checkpoint date: 2026-08-21  
Current status: **CODE FROZEN / SIGNAL VALUES NOT YET LOADED**

### Frozen inputs

- Dataset: Zenodo `10.5281/zenodo.15631383`, `OpenData.zip`, CC BY 4.0;
- official bytes: `91,533,036`;
- official MD5: `b9b03b6e31a33ea08f49cd1cbeed12b2`;
- verified SHA-256:
  `1d343cd3636ea28c80cc847f4fb3bc619b41a37db69d0f30adab082724a2c81b`;
- ZIP CRC: all members passed;
- official inventory: 12 records from the 200 W motor and 9 records from the
  20 kW motor.

The metadata-only audit identified seven scalar MATLAB `timeseries` variables in every
record: `ialbt_meas`, `idq_meas`, `if_meas`, `SinCos`, `ualbt`, `udq`, and `we`.
`mat-io 1.0.0` listed all 147 object headers with zero inventory errors. The audit did
not call `loadmat` or `load_from_mat` and did not load, summarize, or plot signal values.

### Frozen commits

- `c9f0029`: statistical protocol, endpoints, onset rule, incompatibility rules and
  feature-observability boundary;
- `e1e2c5d`: official downloader/integrity audit, MCOS whitelist parser, feature build,
  twelve-method evaluation, five-seed sensitivity, paired record bootstrap and tests.

At `e1e2c5d`, repository-wide `ruff check .` passed and the canonical command
`.venv\Scripts\python.exe -m pytest -q` passed all 136 collected tests. All parser and
evaluation tests used synthetic arrays or pre-existing KAIST features, never a signal
value from the new 21-record archive.

### One-time reveal command

The first command permitted to deserialize `ialbt_meas`, `if_meas`, or `we` is:

```powershell
.\.venv\Scripts\python.exe scripts\build_transient_pmsm_features.py
```

It must attempt all 21 official records in one run. Its first compatibility table,
onset diagnostics, feature table, metadata and any exception output are immutable
primary reveal evidence. If at least 80% of each motor's official records satisfy the
frozen 1 s endpoint and every fold has at least 19 record-disjoint calibration windows,
the only permitted primary scoring command is:

```powershell
.\.venv\Scripts\python.exe scripts\run_transient_pmsm_validation.py
```

The first scoring outputs must not be overwritten. Parser repairs, alternative onset
rules, feature diagnostics or reruns after observing scores must be stored separately
and labeled post-reveal sensitivity. A structural incompatibility is a reportable
outcome and is not permission to change the frozen protocol.

## First signal reveal

Status: **PRIMARY REVEAL STOPPED AT PARSER-COMPATIBILITY GATE**

The one-time feature command was run from clean commit `c09cc43` at
`2026-08-20T16:54:35Z` (2026-08-21 local time). It exited with code 0 after attempting
all 21 records and printed:

```text
processed all 21 records; main-compatible=0, feature rows=0
```

Every record produced the same frozen incompatibility reason:

```text
ValueError: timeseries has no 10 kHz monotonic time candidate
```

Thus `records_parser_compatible=0`, `records_main_endpoint_compatible=0`, and the
compatible fraction was 0 for both the 200 W and 20 kW motors. No current feature,
detector score, calibration threshold, alarm, AUROC or method comparison was produced.
The primary scoring command was not run.

Frozen first-reveal SHA-256 values are:

- `record_compatibility.csv`:
  `b2f737ca6d2dfbd20f211b1e083dd7a045954658f21f7a7553bcf8fb93aa219e`;
- empty-header `onset_diagnostics.csv`:
  `7eb70257593da06f682a3ddda54a9d260d4fc514f645237f5ca74b08f8da61a6`;
- `run_metadata.json`:
  `26e17b621f783eea42eb7fee5272a66508c67f1ad33611138a736d042f48ff9b`;
- empty gzip feature-table artifact:
  `ea88f7ed5f6f94fa64dbeee0782787f796befc7a5bc55a044e69af780fa7cb06`.

This is a parser-compatibility failure, not evidence that any detector succeeds or
fails. Any inspection of the now-revealed MCOS property tree or parser repair must be
versioned separately as post-reveal sensitivity and cannot replace these outputs.

## Post-reveal implicit-time sensitivity

Structural diagnosis found that all records store uniform time implicitly in the
`tsdata.timemetadata` object (`Start_=0`, `Increment_=0.0001 s`, `Length=120001`,
`Units=seconds`) while both public and internal `Time_` arrays are empty. Signal arrays
are stored under `Data_`. Commit `df31a5a` added an opt-in parser for exactly this case;
the primary parser default and all primary failure artifacts remain unchanged.

The separate post-reveal builder attempted all 21 records and produced:

```text
POST-REVEAL implicit-time sensitivity: attempted=21, main-compatible=16, feature rows=384
```

- 200 W: `12/12` records satisfied the fixed onset, guard and 1 s endpoint;
- 20 kW: `4/9` satisfied it; the other five were rejected because measured fault
  current crossed the frozen onset rule inside the initial 0.5 s baseline;
- the 20 kW compatible fraction `4/9 = 44.44%` fails the predeclared 80% motor gate;
- therefore the two-motor quantitative validation remains infeasible and no selective
  20 kW time shift or threshold change is allowed.

Post-reveal artifact SHA-256 values are:

- `record_compatibility.csv`:
  `315d0887fc8db78d87f6ac8db3c120bc91977b4ee4b4e42a8b65748a5c7172a0`;
- `onset_diagnostics.csv`:
  `a495a24658fc9769ac3346a8c9a7979d988b0f1a63c280196073922acc1f23ac`;
- `run_metadata.json`:
  `2e8b3e11d49e5a9da02f5340f5e5870cbeab922fd1e47f1a1222454794a0b637`;
- feature table:
  `92fea2691ea737319dd43469130b0275bce596bab1e98f0bc4c391f109899ad1`.

The 296 rows from the twelve compatible 200 W records contain no non-finite numeric
features. A 200 W-only method run is permitted only as a separately labeled
post-reveal single-motor sensitivity; it cannot reinstate the failed two-motor claim.

### 200 W-only score sensitivity

The 12 fully compatible 200 W records were then evaluated with the already frozen
leave-one-record-out scorer. Every held-out record used five or six different records
for target-health fitting and the complementary five records for calibration; each
calibration set contained 67--88 complete 0.2 s windows, well above the 19-window
arithmetic minimum. No held-out record contributed to its fit or threshold.

All twelve methods detected `0/60` first-second fault windows and `0/12` records with
any first-second alarm. Detection also remained zero over all `120` available
post-onset windows through 2 s. This was not caused by an infinite or unresolved
threshold: the post-onset p-values were far above 0.05 (the minimum across covariance
methods ranged from about 0.28 to 0.39). Across 176 held-out pre-fault windows, primary-
seed false alarms ranged from `7/176` to `13/176`.

The original Log-Euclidean detector produced `8/176 = 4.55%` pre-fault alarms,
`0/60` first-second detections, and mean record AUROC 0.541. Target MinCovDet produced
`9/176 = 5.11%`, `0/60`, and mean record AUROC 0.564. All five candidate-minus-target
transfer contrasts were exactly zero on the thresholded detection endpoint, so this
sensitivity does not identify positive or negative transfer. The result instead shows
that cross-record healthy heterogeneity dominated the fault-onset score under this
representation and calibration rule.

Key score-output SHA-256 values are:

- `aggregate_summary.csv`:
  `aa4904f52069c94e3d5ddf885b63fffa54cd35b71671fc5ab85cc9ee1bede41b`;
- `per_record_summary.csv`:
  `b73c1260342d09d1d52546d6fbded7106e352127e80e6dacc67538d556447ad8`;
- `window_predictions.csv.gz`:
  `4c474ac9da88f2b34daff2bb2151939ccc2b77b004ea3e4dfb959fe5da19e3d6`;
- `run_metadata.json`:
  `86651d982f3cde7437c59e874ff277ed4ac2a2181da47ad89fad71323220c249`.

These outputs are a post-reveal, single-physical-motor sensitivity. They do not replace
the primary compatibility failure and are not used to claim a confirmatory third
dataset, a population false-alarm rate, or universal detector failure.

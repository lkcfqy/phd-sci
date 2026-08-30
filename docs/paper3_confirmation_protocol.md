# Frozen independent PMSG confirmation protocol for Paper 3

Frozen before the first MAT signal reveal on 2026-08-21 (Asia/Shanghai).

## Confirmation question

Does the development-selected healthy-only spline residual detector preserve low pre-fault
false-alarm incidence and useful short-circuit detection on an independently collected
permanent-magnet synchronous generator bench, when all PMSG fitting and threshold calibration
remain fault-blind?

This is algorithm-level external confirmation, not zero-shot parameter transfer. The PMSG
detector is fitted anew using only its standalone healthy files. All 225 files come from one
physical 2.5 kVA PMSG, so operating conditions and fault cases are not independent machine
replicates and cannot support a fleet-population claim.

## Dataset and immutable version

- Data article: Tominaga et al., *Data in Brief* 62 (2025) 112040,
  DOI `10.1016/j.dib.2025.112040`.
- Dataset DOI: `10.5281/zenodo.15741561`, CC BY 4.0.
- Repository: `https://github.com/InnovaPower/MitDev-Eletrica`, tag `v1.1.0`.
- Frozen commit: `e02fba475cf82b375412a7382143dc29da5241ef`.
- Frozen tree: `65430929e4886935d463f1e1410b5476d255f4d4`.
- Expected inventory: 225 MAT files: 9 standalone healthy and 216 fault records; 108
  inter-turn and 108 inter-winding records; 24 fault cases repeated at three speeds and three
  torque setting codes.

The article states 20 kHz sampling, three-second recordings, one pre-fault second, a commanded
fault interval during the next 400 ms (including relay delay), then recovery. Repository names
encode speeds 1200/1500/1800 rpm and torque setting codes T52/T64/T80. `T52`, `T64`, and `T80`
are retained as setting codes; they are not relabeled as N m without source evidence.

## Development freeze

- Selected method: `spline_residual` (additive uniform-knot quadratic splines, ridge alpha 1,
  no local heteroscedastic scale, four whole-record cross-fit folds, Ledoit-Wolf residual
  covariance).
- Selected-method JSON SHA-256:
  `1cccd12c8d7b8d4c6ad40b0a96ebd46ec839739b84b30512a8d4b7ca77324bf5`.
- Development protocol JSON SHA-256:
  `a37d38937aee35ae0ed44c5c139a4e0daf54cd85a03f1e105b8cc6ab5f071ec9`.
- Development feature table SHA-256:
  `c3e7e13919a8868580bd3af8c501d8f022600f5a2637460470479ad7faff4743`.

Development fault labels selected the method. Nothing in the PMSG signals may alter its feature
arm, spline form, ridge, covariance, threshold alpha, support rule, or primary time intervals.

## Signal whitelist and filename context

Only MAT variables `t`, `Ia`, `Ib`, and `Ic` may be deserialized. `Ifault`, relay state,
measured/estimated angle or speed, voltage, torque measurements, dq variables, controller
states, and every other MAT variable are forbidden to the detector and feature builder.

The exogenous context is the filename nominal speed in rpm and the filename torque setting
code. Filename fault family and terminals are labels used only after scores and thresholds are
fixed. The detector outcome is the same 26 scale-free current features used in development;
absolute current scale and current-derived `fundamental_hz` are excluded.

## Fixed windows

All windows are non-overlapping 0.2 s windows at 20 kHz.

- Standalone healthy files: `[0.2, 2.8)` s, 13 windows per file.
- Fault-record pre-fault test: `[0.2, 0.8)` s, 3 windows per record.
- Fault-active test: `[1.0, 1.4)` s, 2 windows per record. The first window intentionally
  includes possible relay delay; this tests command-to-alarm behavior.
- Recovery diagnostic only: `[1.6, 2.8)` s, 6 windows per record.

Intervals are half-open and may not be shifted after reveal. Files must contain 60,000 or
60,001 aligned samples with a uniform 20 kHz time base and must cover 0--3 s. An incompatible
file is reported and excluded only under a documented mechanical compatibility rule; no
condition-specific window movement is allowed.

## Healthy-only 4/3/2 partition

- Fit (four corners): S1200/T52, S1200/T80, S1800/T52, S1800/T80; 52 windows and four physical
  records.
- Calibration (middle torque setting): S1200/T64, S1500/T64, S1800/T64; 39 windows and three
  physical records.
- Untouched standalone healthy test: S1500/T52 and S1500/T80; 26 windows and two physical
  records.

The spline mean is cross-fitted by whole fit record. Split-conformal upper-tail p-values use
the 39 calibration window scores at alpha 0.05. The threshold is the rank
`ceil((39 + 1) * 0.95) = 38` order statistic. Windows within a record are dependent, so this is
an operational calibration rule, not a claimed exchangeable finite-sample record guarantee.

Support uses robust-normalized filename context, 1.1 times the maximum calibration-to-fit
nearest distance, and the fit-axis bounding rectangle. A record/window outside support is
reported as abstention; abstention never counts as a normal decision or a detected fault.

## Locked comparisons

The selected `spline_residual` method is the sole confirmatory method. The six remaining
development candidates are mechanically applied as secondary comparators with their frozen
specifications: unconditioned, linear, quadratic, spline with local scale, isolation forest,
and MinCovDet. Comparator ranking cannot replace the selected method or redefine confirmation.

## Primary endpoints and gates

All primary record endpoints use the 216 fault experiment files.

1. Pre-fault session FAR: any actionable alarm among the three `[0.2, 0.8)` windows. Safety
   gate: point FAR no greater than 5% and descriptive 95% Wilson upper bound no greater than
   10%.
2. Fault record detection: any actionable alarm among the two `[1.0, 1.4)` windows. Utility
   gate: point detection at least 75% and descriptive 95% Wilson lower bound at least 65%.
3. Fault-window actionable detection and abstention. Support gate: fault-record abstention no
   greater than 10%.
4. Command-to-alarm delay: 0.2 s if the first fault window alarms, 0.4 s if only the second
   alarms, and right-censored beyond 0.4 s otherwise.

Secondary endpoints are standalone healthy-file FAR, raw score AUROC/AUPRC, recovery alarms,
and stratification by fault family, nominal speed, torque setting code, and terminal-span
percentage. Wilson intervals describe repeated conditions on this one PMSG; they are not
machine-population confidence intervals.

## Reveal and amendment rule

Before this freeze, filenames, Git tree objects, the data paper, and preview source code were
inspected. A Git size query inadvertently fetched some MAT blobs into the object database, but
no MAT signal array was checked out, deserialized, plotted, or summarized.

After freeze, the reveal proceeds once: inventory and hashes, strict parser audit, feature
build, then the locked analysis. If MAT container orientation or numeric dtype differs from the
synthetic tests while retaining the same documented variable semantics, one mechanical parser
compatibility patch is allowed before any score is computed; the patch and affected files must
be logged. Missing variables, nonuniform time, or incompatible frozen intervals are reported,
not repaired by looking at fault outcomes. No scoring, feature, threshold, support, segment,
or endpoint change is permitted after signal reveal.

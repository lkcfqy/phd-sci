# Block-length and aggregation sensitivity

This is a **post-freeze sensitivity analysis**, not model selection. The primary
setting remains 3 s/max because the 3 s nuisance cycle was identified from
healthy autocorrelation before inspecting target-fault performance. All window
scores use the same scale-free Log-Euclidean detector, source/target healthy
reference intervals, and ridge fraction 0.01.

Feasible candidates at alpha=0.05 were 1 s, 2 s, 3 s. They contain at
least 19 non-overlapping, time-ordered calibration macroblocks and one full
candidate macroblock on each side as a guard. Non-overlap does **not** prove
independence or exchangeability.

Skipped candidates:
- 5 s: 12 calibration macroblocks < 19 required for alpha=0.05; 12 s target adaptation is not exactly representable (10 s nearest realization)
- 6 s: 10 calibration macroblocks < 19 required for alpha=0.05

The frozen 3 s/max setting produced pooled descriptive FAR
0.0000, mean motor block detection
0.9571, worst-motor detection
0.9000, and mean motor block AUROC
0.9993.

Important inference limitation: changing macroblock length changes the number
of rows derived from the same underlying 120 s record. These rows are not new
biological/physical repetitions and must not be pooled across block lengths or
treated as independent sample-size gains. The Wilson intervals in the aggregate
CSV are descriptive diagnostics only; the three motors (and ultimately new
recording sessions) are the meaningful replication level. Also, q90 with the
`higher` order-statistic rule equals max for 1 s (5 windows) and 2 s (10 windows),
so those pairs are expected to be numerically identical.

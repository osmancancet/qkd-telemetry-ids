# Reviewer audit log

| # | Objection | Resolution | Outcome |
|---|---|---|---|
| M1 | Proposition 1 is elementary; novelty unclear | Stated explicitly that the result is elementary and that Gerhardt et al. (2011) is an instance; contribution framed as a bound on all telemetry detectors plus the benchmark and finite-key audit (`sec_model.tex`, after the proof) | Fixed |
| M2 | Simulation only; drift assumed | Threats to validity (internal, external) state it; drift scale d and one-factor sensitivity bracket the assumptions; field validation named as future work | Stated as limitation |
| M3 | Strawman ML baselines | Added drift-aware controls: IF-drift (fitted on drifting benign data), RF-DR (domain randomisation as in Mohamed & Al-Kuwari 2026), and thresholds calibrated on drifting data (Table 7) | Fixed |
| M4 | DCS blind spots | Blind-gain and Blind-nodark added as a calibration ladder; DCS misses Blind-nodark (AUC 0.55) and pure loss, reported openly; post-hoc DCS+Y0 evaluated on fresh seeds with its FPR cost | Fixed, negative result reported |
| M5 | Breach criterion heuristic | Stated one-sided: breach proves insecurity; no breach does not prove secrecy (`sec_model.tex`, eq. 5 paragraph) | Fixed |
| M6 | Ten seeds, p-value floor | Floor stated (0.0020; 0.0098 after Holm); effect sizes given as 95% t-intervals | Fixed |
| M7 | Sensitivity | One-factor runs on separate seeds: window 1/10/60 s, σ_I 0.5/1/2%, fibre 25/50/75 km (Table 6) | Fixed |
| M8 | TPR misread under drift | Table 4 caption and first row show benign FPR; text says the TPR on Blind-cal is the false-alarm rate | Fixed |
| m1 | Intensity fluctuation in the proof | Proof uses the realised intensity k | Fixed |
| m2 | Feasibility condition | 2y_n ≤ 1 for all n with Poisson weight > 1e-30 stated | Fixed |
| m3 | Zero FPR on log axis | Caption says QBER rule not shown and why | Fixed |
| m4 | Direction vs QBER rule | Text says the DCS is worse than the QBER rule on FPR | Fixed |
| m5 | IF-drift "holds target" | Reworded with the 0.34% value | Fixed |
| m6 | "learned detectors match" | Replaced with the macro range 0.91–1.00 | Fixed |
| m7 | Table overflow | Column widths set | Fixed |

# Internal referee report (two rounds)

Three internal referees (statistician, novelty gatekeeper, systems/adversarial reviewer), written as a hostile QST review before submission. Every objection below was resolved in the manuscript or is stated as a limitation; see `reviewer_audit_log.md`.

## Round 1: substance

### Major
- **M1 (novelty).** Proposition 1 is a direct consequence of the photon-number structure; the "perfect eavesdropper" of Gerhardt et al. (2011) already shows it in practice. What is new?
- **M2 (simulation only).** No field telemetry; drift amplitudes are assumptions. Conclusions about false-alarm rates may not transfer.
- **M3 (strawman baselines).** ML baselines trained only on stationary data are set up to fail under drift.
- **M4 (DCS blind spots).** The DCS absorbs anything the three-parameter refit can explain. Which attacks does that hide?
- **M5 (breach criterion).** `ell > n_Z - K_E` is heuristic; does `ell <= n_Z - K_E` prove secrecy?
- **M6 (statistics).** Ten seeds; Wilcoxon p-values sit at the floor and say nothing about effect size.
- **M7 (sensitivity).** Window length, intensity noise and distance were fixed; power may hinge on them.
- **M8 (TPR misread).** IF-stat and RF-stat show TPR ≈ 1 on the calibrated attack under drift; a reader may take that as detection.

### Minor
- m1 `sec_model.tex`, Prop. 1 proof: state that Alice-side intensity fluctuations are reproduced automatically.
- m2 `sec_model.tex`, feasibility: condition `2 y_n <= 1` must be stated with the truncation.
- m3 `sec_results.tex`, Fig. 1: QBER rule (FPR 0) cannot appear on a log axis; say so in the caption.
- m4 `sec_results.tex`: the comparison against the QBER rule on FPR goes the other way (QBER never alarms).
- m5 `sec_discussion.tex`: IF-drift at d = 1 (0.34%) is above the 0.1% target, not "holding" it.
- m6 `sec_results.tex`: "learned detectors match at d = 0" is not true for IF-drift on IR f = 0.05 (AUC 0.91).
- m7 Table 2 and Table 1 overflowed the text width.

### Verified consistency checks
- All tables are produced by `code/make_tables.py` from `results/seed_*.json`; every number in the prose is a macro in `manuscript/numbers.tex` produced by the same script (209 macros). No number was typed by hand except design constants (window length, seeds, α, stream lengths).
- Re-derived from JSON: honest blocks 5760, bound violations 0; blinding breach share = share of blocks with ℓ > 0 at every drift scale (min 94.2% at d = 4, where the rest aborted); in-model breaches 0.
- DCS detection delay for Blind-naive and Blind-gain: 0 windows in 40/40 seed×drift runs each.
- Blind-cal AUC across 6 detectors × 4 drift scales: 0.47–0.55.

## Round 2: template and structure
- Numbered sections, theorem/proof environments, equation numbers checked in the PDF.
- Tables fit the text width (remaining overfull box 0.7 pt, title block).
- Captions describe every encoding (overlapping series in Fig. 1, shaded attack window and dashed thresholds in Fig. 2, diverging colour scale in Fig. 3).
- Style audit (grep): no banned words, no em dashes, no Furthermore/Moreover/Additionally/Consequently/Notably/Specifically/In summary openers, no sentence-final participial tails, three-item lists rewritten.
- Author block: Osman Can Çetlenbik, Big Data Analytics Program, Department of Statistics, Manisa Technical Sciences Vocational School, Manisa Celal Bayar University; osman.cetlenbik@cbu.edu.tr; ORCID 0009-0000-6561-1943.
- IOP sections present: Acknowledgements (AI statement left to the author as a LaTeX comment), Data availability statement.

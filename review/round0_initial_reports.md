# round0 initial reports (full text of three independent referee reports)

**Referee 1 report: statistical methodology. Recommendation: major revision**

**Summary.** The manuscript proposes a decoy-consistency statistic (DCS) for detecting attacks on a decoy-state BB84 link from window telemetry. It compares the DCS with five baselines on simulated 24-hour streams at four drift scales and adds a finite-key audit. The pipeline is reproducible: I recomputed every number I spot-checked from `results/*.json` and it matched. The problems are in inference and interpretation, not arithmetic. Seed-level variability is hidden behind means. One stated reading of the Wilcoxon test is false. The drift-calibrated control is degenerate. The key audit is true by construction for exactly the cases it is used to support. Several sentences in the abstract and conclusion go beyond what the intervals show.

---

**Major issues (most severe first)**

**M1. The AUC result for Blind-cal hides very large per-seed spread, and AUC within a stream is confounded with time of day.**
- The abstract and Results (sec_results.tex:30) say every detector scores an AUC between 0.47 and 0.55 on Blind-cal. That range is a range of 10-seed means.
- Per seed, the learned detectors range from 0.23 to 0.85: IF-stat at d=2 spans 0.231–0.714, and RF-DR at d=4 spans 0.279–0.851. The DCS stays within 0.44–0.55.
- Blind-cal is sampled from exactly the honest law (qkdsim.py:195–202). These numbers are therefore the empirical null distribution of AUC. A single 24-hour deployment can show AUC 0.85 with no signal at all.
- The cause is that each attack occupies one contiguous 2-hour block, compared against the other 22 hours of the same drifting stream. Detectors that track drift then score "this block's time of day", not the attack.
- The same confound affects every learned-detector AUC in Figure 3 and Table 5 (e.g. Blind-cal-static: IF-drift 0.75, RF-DR 0.57).
- **Fix:**
  - Report per-seed distributions or intervals for every AUC.
  - Use a paired design: the simulator already draws an honest sample `base` on the same channel trajectory (run_all.py:48). Score the attacked windows against the same windows of `base`.
  - Calibrate significance against the Blind-cal null.

**M2. The stated interpretation of the Wilcoxon test is false, and the Holm family is too small.**
- sec_setup.tex:17 says p-values at the floor of 0.0098 mean the DCS "was better in every seed".
- That is not what happened. At d=1 the DCS had a higher FPR than IF-drift in seed 3 (0.104% vs 0.046%) and than RF-DR in seed 1 (0.069% vs 0.000%).
- The raw p-values were 0.0059 and 0.0039. Holm's step-down monotonicity lifted both to 0.0098, which is why they appear at the floor.
- Holm is applied per drift scale over 5 tests, but the reported maximum (`holmFprMax`, make_tables.py:216) spans 15 tests. Fifty AUC Wilcoxon tests per scale are also computed (make_tables.py:92–95) and never reported.
- **Fix:**
  - Correct the sentence.
  - Define one family and adjust across it.
  - Report paired differences with bootstrap intervals; a rank test adds nothing for 0.08% vs 97%.

**M3. The drift-calibrated control is degenerate, and FPR is reported without the matching TPR.**
- With drift-calibrated thresholds, RF-stat's threshold is 1.0 in every seed I checked. Because scores are tied at 1.0 and the alarm test is the strict `>`, it can never alarm. Its FPR is 0.00 at all scales (Table fpr_dcal) and its TPR is 0.000 on every attack.
- IF-drift at d=1 likewise has TPR 0 on all attacks, Blind-naive included.
- The text presents this table as the ML detectors reaching low FPR "at the price of benign drift data". A detector with 0% FPR and 0% TPR is not a working operating point.
- IF-drift is fitted on drifted data (run_all.py:108) but thresholded on drift-free data (run_all.py:115–116). This handicaps it by construction.
- **Fix:**
  - Report FPR and TPR together, or partial AUC at FPR ≤ 1%.
  - Handle ties (≥ plus randomisation).
  - Threshold each detector on data matching its own training regime.

**M4. The interval method is unsuitable, and the false-alarm claims overstate the data.**
- t-intervals on bounded, skewed proportions fail here. RF-DR at d=1 reads 9.16 ± 12.36, which implies a negative lower bound. The per-seed values are bimodal: median about 1.5%, but 54.3% and 22.8% in two seeds.
- "Every calibrated detector meets its 10⁻³ target at d=0" (sec_results.tex:7) is not supported for IF-stat: 0.131% (pooled 113/86 400, binomial p = 0.006; one-sample t p = 0.038).
- The DCS at d=4 runs at 0.18% (158/86 400, binomial p ≈ 5×10⁻¹²; t p = 0.015), nearly twice the target. The conclusion (sec_conclusion.tex:5) nevertheless says it "held the false-alarm rate near its 10⁻³ target up to fourfold drift".
- Per-window FPR also ignores alarm clustering: the hourly cycle makes alarms autocorrelated.
- **Fix:**
  - Use Wilson or Clopper–Pearson intervals per seed and a seed-level bootstrap.
  - Formally test each FPR against the target.
  - Report alarm episodes per day.

**M5. The finite-key audit is true by construction for the cases it is meant to support.**
- Honest `know` is identically 0 (qkdsim.py:123), so "no honest block breached" says nothing.
- For every blinding attack, κ = 1 (qkdsim.py:182, 187, 194, 202). Breach is therefore identical to ℓ > 0: true in all 4 × 600 blinding blocks.
- The "Eve-known fraction" for honest operation is hard-coded as 0.000 (make_tables.py:149), not computed.
- The 120 blocks per scenario are 12 consecutive blocks from each of 10 seeds, pooled as if independent, with no intervals.
- **Fix:**
  - State that the breach result is deterministic.
  - Report P(ℓ>0) per seed with intervals.
  - Compute the honest column instead of hard-coding it.

**M6. The sensitivity and post-hoc analyses are underpowered and partly duplicated.**
- Each sensitivity row uses 5 seeds, and neither Table 7 nor the text gives an interval.
- The rows "10 s", "σ_I 1%" and "50 km" are the same configuration on the same seeds (sensitivity.py:27–29). They are one run printed three times (0.932, 0.932, 0.932).
- Stream length (8 h) and attack length (n_windows/6, i.e. 80 min) differ from the main run, so the rows are not comparable with Table 2.
- "Little effect" for σ_I rests on 0.930 vs 0.908 with no interval.
- For DCS+Y0, the FPR of 0.27% at d=2 is omitted from the text.
- **Fix:** At least 10 seeds per setting, intervals, and matched stream and attack lengths.

**M7. RF test attacks overlap the training attacks.**
- IR f=0.05, PNS, Blind-naive and Loss +1/+3 dB are in both TRAIN_ATTACKS and TEST_ATTACKS (run_all.py:27–30).
- RF AUCs on these attacks therefore measure in-distribution recognition, but they are pooled with out-of-distribution attacks in Figure 3 and Table 5 and in `aucInModelLearnedMin`.
- **Fix:** Mark which cells are in-distribution, or hold those attacks out of training.

---

**Minor issues**
- sec_method.tex:8 says the fit starts from Ŷ₀ = Q_{μ3}; the code (detectors.py:210) starts from Q₃ − 10⁻³ Q₁.
- run_all.py:147: delay is the first alarm at or after onset with no conditioning. For detectors with 97% FPR it is trivially 0. Use conditional expected delay.
- DCS AUC on Loss is below 0.5 in every seed (mean 0.44, maximum about 0.46). That is a systematic reversed signal, not blindness "by construction" (sec_results.tex:36).
- make_tables.py:84: "known fraction" is a mean of per-block ratios; say so, or use a ratio of sums.
- No intervals in Tables 4, 5 or 6, or in Figure 3. `fpr_outside` is computed (run_all.py:153) but never used.
- sec_setup.tex:14: "all settings were fixed before the test streams were generated" cannot be verified. Give a commit hash or timestamped protocol.
- Threshold variability is not reported: the α = 10⁻³ quantile rests on about 26 exceedances per seed, and the RF-DR threshold ranges from 0.13 to 0.51 across seeds.

---

**Claims I verified as correct** (recomputed from the JSON with `python3 -I`)
- **Table fpr:** means and t-intervals match. IF-stat 97.15 ± 0.20, RF-stat 97.46 ± 0.26, DCS 0.08 ± 0.04 (d=1) and 0.18 ± 0.06 (d=4).
- **Bound check:** 5760 honest blocks, 0 bound violations. The smallest ratio of true single-photon count to s_{Z,1} is 1.039.
- **Breach rate:** `breachBlindMin` = 94.2% (Blind-cal, d=4). All remaining blocks aborted (ℓ = 0).
- **Early detection:** DCS AUC = 1.000 and delay = 0 for Blind-naive and Blind-gain in every seed at every drift scale.
- **IR f=0.05 and in-model attacks:** Eve knows 2.5% of sifted bits with no breach. No in-model attack breached any block. PNS aborted every block.
- **Holm values:** the adjusted p of 0.0098 is numerically correct, though its interpretation is not (M2).
- **Blind-cal range:** the 10-seed-mean AUC range of 0.47–0.55 is correct as stated for means.
- **Runtime:** mean 20.4 s per seed.
- **Sensitivity table and DCS+Y0:** sensitivity values match the macros. The DCS+Y0 FPR of 1.82% vs 0.20% at d=4 matches `exploratory_dcs_y0.json`.

---

**Referee 2 report: physics and novelty**

**(1) Summary**
The paper simulates window telemetry of three-intensity decoy-state BB84 under drift. It states an indistinguishability proposition (Prop. 1), proposes a per-window refit statistic (DCS), benchmarks it against strawman ML detectors, and audits breaches with ground-truth knowledge flags. The finite-key code matches Lim et al. 2014. However:
- the simulator does not model sifting;
- several attack models assign physically impossible error and knowledge values to vacuum clicks;
- Prop. 1 is a tautology, and its supporting physical argument is wrong for asymmetric bases;
- the headline negative results follow by construction.

As it stands this is not at the novelty level of QST. Recommendation: major revision bordering on reject.

**(2) Major issues**

**M1. Bob's basis choice and sifting are missing from the simulator.**
- Evidence: `qkdsim.py:224-226` draws N from Alice's p_Z × p_k only. `qkdsim.py:239` then draws every click from Binomial(N_{b,k}, Q) and counts it as sifted. No Bob basis probability appears anywhere (grep for `p_z` finds only lines 36 and 224).
- Consequence: Bob effectively always measures in Alice's basis. With p_Z = 0.9 for Bob as well, sifted X counts are about 10x too high and Z counts about 11% too high.
- This inflates the key rates (keyrateDZero = 1.41e-3), tightens the phase-error bound, and boosts DCS power on the X-basis residuals. That matters because `sec_method.tex:18` says IR is seen *only* through the decoy and test-basis residuals.
- Fix: model Bob's basis choice (p_Z^A·p_Z^B sifting, as in Lim 2014), rerun everything, and compare the honest rate with Lim's published curve as a sanity check.

**M2. Prop. 1 is trivial, and the supporting construction is argued incorrectly.**
- If two laws are equal, every test has power equal to its size. That is a tautology. The paper itself admits (`sec_model.tex:85`) that Gerhardt 2011 is an instance. It cannot be listed as a contribution (`sec_intro.tex:11`).
- The proof (`sec_model.tex:82`) treats y_n and e_n as basis-independent and the attack as i.i.d. per pulse, without saying so. Coherent or adaptive attacks are excluded by hypothesis.
- The achievability text says a blinded click happens "only when Bob's basis matches hers, which happens with probability 1/2". With p_Z^B = 0.9 that match probability is 0.9 or 0.1, not 1/2.
- The correct construction:
  - Eve picks her basis Z with probability q.
  - She forwards with probability y_n/q in Z and y_n/(1−q) in X.
  - The feasibility condition is y_n ≤ min(q, 1−q), which gives 2y_n ≤ 1 only at q = 1/2.
- Fix: state basis-resolved yields, the i.i.d. assumption and the correct feasibility condition, and drop the "contribution" framing.

**M3. Physically impossible vacuum-click models; "Eve knows every sifted bit" is false.**
- On an empty pulse Eve has no information about Alice's bit. An injected click therefore has error 1/2 against Alice and zero knowledge of Alice's (key-defining) bit.
- `qkdsim.py:202` (blind_cal) sets know = 1 for n = 0.
- `qkdsim.py:186-187` (blind_gain) sets e = 0 *and* know = 1 for n = 0. Error-free clicks on vacuum pulses are unphysical.
- `qkdsim.py:194` (blind_nodark) has the same knowledge issue (negligible there, since y_0 ≈ 0).
- The "Eve-known fraction 1.000" entries in `tables/key_d1.tex`, and the sentence "Eve knows every sifted bit" (`sec_model.tex:85`, `abstract.tex:1`, `sec_results.tex:51`), overclaim. The vacuum share is about 1e-4 of n_Z, so the breach verdicts survive, but the claim of full knowledge does not.
- Fix: set k_0 = 0 and e_0 = 1/2 for all faked-state variants, and restate the claim.

**M4. The headline findings are circular.**
- blind_cal literally calls `honest_yields` (`qkdsim.py:199`). An AUC of 0.47–0.55 therefore tests the RNG, not physics.
- "Every blinding block was fully known" is an input (k_n = 1), not a finding.
- The ML false-alarm collapse is engineered:
  - IF-stat and RF-stat use absolute log-gain and QBER features fitted on d = 0 data and are then tested under drift. Their failure is expected by design.
  - RF-stat is a closed-set classifier, and its "anomaly score" is out-of-distribution by construction.
- Fix: present these results as sanity checks and move the emphasis elsewhere.

**M5. Missing simple physics baselines; the DCS advantage is not shown to need the DCS.**
- Blind-naive and Blind-gain are caught because the QBER is near zero. A *two-sided* QBER band, or a per-window decoy-gain-ratio check, would very likely catch them too. The only physics baseline is the one-sided 11% rule (`detectors.py:23-25`), which by design cannot alarm on low QBER.
- CUSUM is cited (`sec_discussion.tex:19`) but not run.
- Fix: add a two-sided QBER/gain-ratio band and a CUSUM-on-residuals baseline.

**M6. Related work is mischaracterised and key prior work is missing.**
- `sec_background.tex:10` claims the literature does not tie detection to the finite-key output. Mohamed & Al-Kuwari (arXiv:2603.03502) explicitly scale the missed-detection loss by finite-key secret-fraction degradation (decoy-state and EAT bounds). They also apply domain randomisation (η ±1 dB, e_d ±0.4 pp, timing jitter) and test on drifted conditions. I verified this on arXiv. The gap statement must be corrected.
- Isha et al. (2608.04047): the FNR values 0.0198 vs 0.8477 are confirmed. The "24,000 sessions" figure is not in the abstract; please check it against the paper body.
- Al-Kuwari et al. (2509.14282): the cited version is the IET Quantum Commun. one; consistent.
- Missing references on statistical detection of detector control, all verified:
  - G. Gras, D. Rusca, H. Zbinden, F. Bussières, "Countermeasure against quantum hacking using detection statistics", Phys. Rev. Applied 15, 034052 (2021), doi:10.1103/PhysRevApplied.15.034052. A coincidence-statistic test for blinding that bounds Eve's information: exactly the "statistics beyond counts" the paper says only hardware can provide.
  - Y.-J. Qian, D.-Y. He, S. Wang, W. Chen, Z.-Q. Yin, G.-C. Guo, Z.-F. Han, "Robust countermeasure against detector control attack in a practical QKD system", Optica 6, 1178 (2019), doi:10.1364/OPTICA.6.001178. Variable attenuation plus detection/error statistics.
  - T. Ferreira da Silva, G. B. Xavier, G. P. Temporão, J. P. von der Weid, "Real-time monitoring of single-photon detectors against eavesdropping in QKD systems", Opt. Express 20, 18911 (2012), doi:10.1364/OE.20.018911. Inter-detection timing statistics.
  - W.-C. Lee et al., "Countermeasure against blinding attacks on low-noise detectors with a background-noise-cancellation scheme", arXiv:1611.04267 (journal version to be checked).
  - A. Koehler-Sidki et al., "Best-practice criteria for practical security of self-differencing avalanche photodiode detectors in QKD", Phys. Rev. Applied 9, 044027 (2018). The PR Applied reference is from memory; a Cambridge repository copy exists.
- Together these show that richer telemetry (coincidences, timing, afterpulsing) *does* break the Prop. 1 hypothesis. The paper's "telemetry is weak" conclusion depends on restricting telemetry to counts. That scoping must be made explicit in the title and abstract.

**M7. The conclusions overreach for simulation-only evidence.**
- Phrases such as "cannot replace hardware countermeasures" (`abstract.tex:1`), the ">97% of benign windows" result (`sec_conclusion.tex:5`), and "Reporting it as a security gain overstates it" (`sec_discussion.tex:4`) rest on assumed drift amplitudes that were not fitted to any link, and on strawman ML baselines.
- Fix: validate on at least one recorded field telemetry trace, or soften to "in this simulation model".

**(3) Minor issues**
- **`detectors.py:40`:** initialises Ŷ0 = Q3 − 1e-3·Q1, but `sec_method.tex:3` says Ŷ0 = Q_{μ3}.
- **`sec_model.tex:91-94` (breach criterion):**
  - The converse correction for an ε-secret key is O(εℓ) + h(ε) (Fano/continuity), not "order log(1/ε)".
  - The EC leakage only strengthens the test; say so.
- **Intensity noise (σ_I = 1%) violates Lim's exact-intensity assumption** (`finite_key.py` uses nominal μ). The honest blocks are then not strictly "in model". This is mitigated empirically (boundViol = 0), but it should be acknowledged.
- **`finite_key.py` header:** Lim's Hoeffding-based decoy bounds are rigorous only for i.i.d. (collective) attacks. The coherent case needs Azuma/Kato-type bounds. The claim "hold against general attacks" (`sec_background.tex:4`) should be qualified.
- **`finite_key.py:55-59` (gamma):** clips b at 0.5 and c, d at ≥1. This is harmless but should be documented.
- **`finite_key.py:69`:** the ratio fallback of 0.5 when s_X1 = 0 should be documented.
- **`qkdsim.py:155-158` (IR):** one resend yield y_E for all n ≥ 1, with an ideal Eve detector. Fine, but state it. Double clicks from multi-photon resends are ignored.
- **`qkdsim.py:168` (PNS):** assumes Eve knows η_B. State it.
- **Table 2:** "IR, f" uses f ∈ {0.05, 0.2} in tests but {0.05…0.5} in training. List them.
- **`sec_setup.tex:17`:** Wilcoxon over 10 seeds with p at the floor adds little. Report intervals only.

**(4) Verified correct**
- **`finite_key.py:25-27` (Hoeffding):** n^± = e^k/p_k·(n_k ± √(n_b/2·ln(21/ε_sec))) matches Lim Eq. (2), with the deviation taken over the whole basis.
- **`finite_key.py:30-34` (s0):** matches Lim.
- **`finite_key.py:37-45` (s1):** matches Lim, including the denominator μ1(μ2−μ3) − (μ2²−μ3²).
- **`finite_key.py:48-52` (v1):** τ1(m⁺_{μ2} − m⁻_{μ3})/(μ2−μ3) matches.
- **`finite_key.py:55-59` (γ):** formula, ln 2 and 21²/ε² factor match; it is symmetric in c, d.
- **`finite_key.py:73-74` (key length):** s0 + s1(1−h(φ)) − λ_EC − 6 log2(21/ε_sec) − log2(2/ε_cor) matches.
- **Honest model (`qkdsim.py:121-122`):** matches Ma et al. 2005, with Y0 for two detectors.
- **Gain matching:** IR, PNS and blind_naive all match Q_{μ1} (`test_sim.py` verifies this). The PNS c ≈ 0.55 < 1 at 50 km is consistent.
- **2y_n ≤ 1:** holds for all n ≤ 30 (y_30 ≈ 0.26). Only the justification is wrong (M2).
- **Breach audit:** K_E is counted over Z clicks only (`run_all.py:75`), consistent with n_Z.

Sources:
- https://arxiv.org/abs/2608.04047
- https://arxiv.org/abs/2603.03502
- https://arxiv.org/abs/2509.14282
- https://archive-ouverte.unige.ch/unige:151579
- https://arxiv.org/abs/1909.10015v2
- https://arxiv.org/abs/1208.0532v1
- https://arxiv.org/pdf/1611.04267
- https://www.repository.cam.ac.uk/handle/1810/276941

---

## Referee 3 report: systems and adversarial review

**Manuscript:** "What window telemetry can and cannot reveal about quantum hacking" (QST)

### 1. Summary
The manuscript does three things. It formalises the point that a faked-state attacker who reproduces (y_n, e_n) leaves the window telemetry law unchanged (Prop. 1). It proposes the DCS, which refits (eta, Y0, e_d) in every window and tests six binomial residuals. It then benchmarks the DCS against a QBER rule and four forest detectors on simulated 24 h streams. The finite-key audit is a real strength and the code reproduces. My concerns are elsewhere. The headline false-alarm advantage depends on a drift model that leaves out the benign effects most likely to break the DCS. The ML baselines and the QBER baseline are set up to fail. The adversarial analysis leaves out the obvious way to beat the DCS. **Recommendation: major revision.**

### 2. Major issues

**M1. The drift model is missing effects that break the DCS's false-alarm claim, as I show below.**
- `qkdsim.py:100` and `sec_model.tex:16-21`: one scalar e_d drives both bases. `qkdsim.py:101` and `sec_model.tex:22`: intensity noise is i.i.d. per window with no slow component. `sec_discussion.tex:15` admits basis-dependent misalignment is omitted, then assumes the MAD standardisation will absorb it.
- It does not. I used the authors' own code with the authors' calibration at d=0 (5 seeds, d=1, alpha=1e-3; script at /tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/probe.py) and got these benign false-alarm rates:

| Benign effect added | DCS FPR |
|---|---|
| None (control) | 0.09% |
| X-basis misalignment drifting at its own slope (realistic: polarisation drift is a rotation on the Poincaré sphere, and Z and X degrade differently) | 61.7% |
| e_d,X = 1.3 x e_d,Z drift | 68.2% |
| Slow diurnal decoy/signal intensity-ratio drift, 2% | 0.30% |
| Same, 5% (VOA or modulator-bias temperature drift) | 8.2% |
| Afterpulsing-like background (2% of click rate) not in calibration | 0.80% |
| Common-mode laser-power drift (OU, 3%) | 0.09% (absorbed) |

- A single unmodelled benign effect, basis-dependent misalignment, therefore produces the same kind of failure the paper reports for IF-stat and RF-stat. Dead time, detector efficiency mismatch, temperature–dark-count coupling and gate-timing jitter are also absent. Dead time also breaks the per-pulse independence that Prop. 1's proof relies on (`sec_model.tex:82`).
- **Fix:** add these effects to the simulator, or better, validate on recorded field telemetry. Let e_d differ by basis in the refit, and make the 6-residual budget explicit about which degrees of freedom drift.

**M2. The baselines are strawmen.**
- `run_all.py:239` (inside `train_set`): RF-DR's benign class is a single stream with a single drift draw. That is not domain randomisation, and it explains the ±12.4% interval at d=1 (`tables/fpr.tex`).
- `run_all.py:168-169`: "Loss +1/+3/+6 dB" is labelled as an attack in training, yet benign drift alone spans 8.5–11.6 dB at d=2 (numbers.tex). The forests are taught that benign drift is an attack.
- `detectors.py:16-20`: the features are absolute levels only, with no ratios (Q_mu2/Q_mu1), no vacuum-versus-signal QBER contrast and no temporal context.
- The drift-calibrated control (`tables/fpr_dcal.tex`) reports RF-stat at 0.00% FPR at every d. In the seed JSONs that threshold is exactly 1.0, so RF-stat never alarms (TPR_dcal = 0 for every attack). The table hides this degeneracy.
- QBER>11% (`sec_setup.tex`, detector list) is one-sided. Its AUC is 0.00 on Blind-naive, Blind-gain and Blind-cal-static (`tables/auc_d1.tex`). A "QBER/vacuum-QBER too low" rule would therefore match the DCS on the two attacks it catches, and beat it on the static attack.
- **Fix:** add four baselines:
  1. Forests or a one-class model on the DCS residuals (physics features).
  2. RF-DR with many benign drift draws, with loss removed from the attack labels.
  3. A two-sided QBER and vacuum-error rule.
  4. CUSUM/EWMA on the residuals.
  The authors postpone CUSUM to future work (`sec_discussion.tex:19`), but it is the obvious operator baseline. Report TPR at the drift-calibrated thresholds.

**M3. A competent attacker can beat the DCS cheaply; the paper's ladder overstates the attacker's burden.**
- The DCS is blind by construction to any attack that is consistent with *some* honest triple (eta', Y0', e_d'), whether or not it matches the true channel. Blind-cal-static scores 0.50 for exactly this reason (`tables/auc_d1.tex`). Eve does not need to track the channel; she needs only to be self-consistent.
- Prop. 1's discussion (`sec_model.tex:85`, `sec_discussion.tex:10`) calls a photon-number-resolving detector a demanding requirement. It is not. A threshold detector behind an attenuator with efficiency about 2·eta gives y_n ∝ 1-(1-eta')^n, which is the honest form up to O(eta²), about 1e-4 relative here.
- Blind-naive (`qkdsim.py:177-183`) uses constant y_n, i.e. a lossless, perfect detector. That is the least realistic way to build a faked-state attack, and it is the attack behind the "first window" headline in the abstract.
- **Fix:** add a "Blind-thresh" rung (threshold detector, attenuation, injected dark counts and errors) and expect DCS AUC near 0.5.
- Blind-cal (`run_all.py:177`, `qkdsim.py:195-202`) gives Eve oracle knowledge of *Bob-internal* parameters: the detector-efficiency OU process and the temperature-driven dark-count swing. Once Bob's detectors are blinded, those effects no longer appear on their own, so Eve has to synthesise them without seeing Bob's cryostat or TEC. The missing realistic rung is an attacker who tracks the fibre but replays nominal detector parameters.
- That gap points to a defence the paper misses. Correlate fitted Y0 and efficiency with Bob's housekeeping (detector temperature, bias). Or use active challenges: deliberately perturb the polarisation compensator or the gate settings and check that the statistics respond. Both break the premise of Prop. 1, which assumes a passive defender, and should be discussed.

**M4. The Blind-cal-static result is misinterpreted.**
- AUC 0.00 for IF-stat, RF-stat and QBER means the attack is *perfectly separable* in the other direction, not "more normal". `sec_results.tex:34` says "the learned detectors" score it as more normal, yet IF-drift scores 0.75 and RF-DR 0.57 at d=1.
- A flat QBER while the compensation loop expects a sawtooth would be visible to any operator. So would a key rate 16% *above* honest (1.408 vs 1.214, `tables/key_d1.tex`).
- Contrary to `sec_discussion.tex:10`, the result is that the DCS refit *removes* this signature. That is a real cost of the design and belongs in the abstract.
- **Fix:** report two-sided AUC (`auc_flip` is already computed at `run_all.py:294`, then unused), and add a low-variance or "missing drift" test.

**M5. The operational claims are not backed.**
- An FPR of 0.08–0.18% per 10 s window means roughly 7–16 false alarms per day per link. That does not support "without drowning operators" (`abstract.tex`), especially across a network.
- Report mean time between false alarms, an alarm-aggregation policy, and detection delay as a distribution. Delay is recorded (`run_all.py:293`) but only "first window" is quoted. The DCS max delay at d=4 for IR f=0.05 is 3 windows.
- The runtime claim (20 s per seed, `sec_setup.tex:17`) is a whole-benchmark wall time and matches `results/run_log.txt`. There is no per-window latency, no memory figure, and no measurement on an embedded or KMS controller.
- Per-window, per-intensity sifted counts require per-window basis and intensity announcement. Real stacks often reveal these only per block, so the window-level data path needs justifying.

### 3. Minor issues
- `figures/fpr_vs_drift`: the x-axis reads "Drift scale σ" while the text uses d. The RF-DR lower error bars run off the log axis. The QBER rule is omitted rather than shown as a floor marker.
- `figures/auc_heatmap_d1`: no uncertainty is shown. Several AUC < 0.5 cells for RF-stat (Blind-gain 0.22, Blind-nodark 0.29) are never discussed.
- The DCS AUC on loss attacks is 0.44 < 0.5, so its null distribution depends on count level (the intensity-noise term scales with sqrt(counts)). This needs recalibration per operating point; `tables/sens.tex` (FPR 0.04→0.17 from 1 s to 60 s windows) shows the same drift.
- IF-drift is fitted on drifted data but thresholded on drift-free data (`run_all.py:247-256`). This mismatch should be stated.
- Calling the DCS cost "O(1) per window" (`sec_intro.tex:13`) is trivially true and not evidence of deployability.
- Prop. 1 holds for the 12-count vector T only. "Every telemetry detector" should be qualified: per-detector counts, double clicks, timing and photocurrent are telemetry too.

### 4. Verified correct
- The macros agree with the per-seed JSONs: the FPR table, AUC ranges 0.47–0.55, and 0 bound violations in 5,760 honest blocks.
- The Holm floor of 0.0098 is right for n=10.
- Block counts (120 and 1,440) are right.
- Blind-naive is flagged by the DCS in the first window: max delay is 0 across seeds.
- The breach audit logic (`run_all.py:204-219`) matches Eq. (breach).
- The `blind_cal` yields are honest-form and enforce 2y_n ≤ 1.
- The authors are open about the post-hoc DCS+Y0 variant and evaluate it on fresh seeds.
- The runtime figure matches the logs.
- The code reproduces end to end.

---


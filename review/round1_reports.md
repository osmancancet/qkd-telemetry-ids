# round1 reports (full text of three independent referee reports)

REFEREE 1 (STATISTICS) — Revised manuscript "count telemetry / DCS" (QST)

## 1. Summary and recommendation
The revision fixes most of the design problems I raised in round one. AUC is now computed against a time-matched honest copy of the same channel trajectory. Hypothesis tests and the Holm family are gone. Thresholds use randomised tie-breaking. Seeds are the bootstrap unit. Train/test overlap is marked. The sensitivity runs use 10 seeds. The breach audit is described as accounting, not discovery. Every prose number I checked matches numbers.tex, numbers.json and the per-seed JSONs (list in section 4), and the PDF is built from the current macros.

Problems remain:
- Several headline claims in the abstract, introduction and conclusion are contradicted by the authors' own per-seed data:
  - drift-calibrated detectors do not hold their target inside the calibrated range;
  - not every released faked-state key breached;
  - "only a two-sided rule can see them" was never tested;
  - Blind-thresh is statistically distinguishable from honest operation.
- Two statements are factually false: "appendix tables give all three levels", and the 10-minute block withholding claim.

Recommendation: **major revision (narrow)**. Most fixes are rewording. Two small analyses are needed: a two-sided calibrated rule, and an attack-duration test on Blind-thresh.

Status of round-one issues:
- Time-of-day confounding in AUC: fixed (run_all.py:186-197; the honest copy shares the channel state, including the realised intensities and monitor readings).
- "Every seed" wording and Holm family: fixed (removed).
- Degenerate drift-calibrated control with tied RF scores: tie problem fixed (detectors.py:215-228 is correct). A new calibration problem appears instead (M1).
- t-intervals: replaced by a percentile bootstrap. Partly adequate (m1).
- FPR-target claims: still overstated (M1).
- Breach result deterministic by construction: acknowledged in sec_model.tex:105 and sec_discussion.tex:95, but the abstract still sells it and overstates it (M3).
- Too few sensitivity seeds: fixed (10). The table has no intervals (m4).
- Train/test overlap: fixed with $^*$. IR f=0.2 is not marked (m6).

## 2. Major issues

**M1. "Drift-calibrated detectors hold their target inside the calibrated range" is false.**
Locations: abstract.tex:1, sec_results.tex:13, sec_discussion.tex:7, sec_conclusion.tex:4.
- Calibration covers d ∈ {0.5, 1, 2}, yet at d=2 IF-drift is at 0.53% [0.25, 0.84] and RF-DR at 0.96% [0.46, 1.52]. That is 5-10× α, with intervals that exclude 0.1%.
- Per-seed RF-DR FPR at d=2 ranges from 0.12% to 2.28%.
- At d ≤ 1 both detectors give exactly 0 in every seed (one alarm in total for RF-DR). They are far below target, not at it.
- Cause: the threshold is a quantile of the pooled mixture of three 24-h streams. It is set almost entirely by the d=2 stream and is controlled only for the mixture, not at any one drift scale.
- RF-DR thresholds vary from 0.25 to 0.67 across seeds. For drift-sensitive scores the effective calibration sample is three drift trajectories, not 25,920 windows.
- Consequences:
  - The "target" language is wrong.
  - RF-DR's d=1 TPRs, and the claim "with no false alarms … strongest detector inside its calibrated range" (sec_results.tex:40), are at a much more conservative operating point than the DCS.
  - Episodes are 0.1 [0, 0.3] per day, so "no false alarms" is also literally false.
- Fix:
  - State that drift-aware thresholds meet α only on the calibration mixture, give up to 10× α at d=2 and ≈0 at d ≤ 1.
  - Either calibrate per drift scale or report the between-trajectory variance.
  - Compare detectors at matched realised FPR (e.g. partial AUC, or TPR at the empirical benign FPR of each detector).

**M2. "Only a two-sided rule can see them" (abstract.tex:1) and "Read two-sided, these attacks are almost perfectly separable" (sec_results.tex:42) are untested and probably wrong as operational claims.**
- The reverse AUC (0.00-0.01 for IF-stat/QBER/Band on Blind-static) compares attacked windows with the oracle honest copy. The operator does not have that copy.
- IF-stat on honest drifting windows alarms at 95%. The attacked windows look like the drift-free calibration data.
- A lower-tail rule calibrated on drift-free data would therefore fire at about α on Blind-static, which is no detection.
- The only calibrated two-sided detector in the study, Band, has TPR 0.001 on Blind-static and Blind-track at d=1 (tpr_d1.tex).
- A lower-tail rule calibrated on drifting data corresponds to IF-drift. Its AUC is 0.52 on Blind-static and 0.74 on Blind-track, i.e. reversed 0.48 and 0.26: weak.
- RF-stat's 0.18 is not "almost perfect".
- Fix:
  - Implement the two-sided or lower-tail rule with a threshold calibrated on benign data (both calibration sets) and report its TPR at α.
  - Otherwise, rephrase as "the attack changes the score distribution relative to the contemporaneous honest channel; no calibrated rule in this study exploits it".

**M3. "Every key released under faked-state attacks was known to the attacker" (abstract.tex:1) contradicts Results.**
- At d=4, 6 of 92 key-producing Blind-cal blocks and 1 of 104 Blind-thresh blocks did not breach (breach | ℓ>0 = 0.935 and 0.99; the authors' own macro breachGivenPosMin = 93.5, sec_results.tex:61).
- Eve knows 98.95-100% of sifted bits, not all of them.
- The audit is acknowledged as true by construction (sec_model.tex:105), so it should not be a headline result.
- Fix: replace with "Eve knew ≥ 98.95% of sifted bits and ≥ 93.5% of key-producing blocks breached; this follows from the attack construction". Do the same in sec_discussion.tex:4 ("almost every block") and sec_conclusion.tex:3.

**M4. Blind-thresh is not "at chance". The "no detector exploited" claim depends on the operating point chosen.**
Locations: sec_conclusion.tex:3, abstract.tex:1, sec_results.tex:38/61, sec_discussion.tex:13.
- Recomputed from numbers.json: 17 of 40 detector×drift AUC intervals for Blind-thresh exclude 0.5.
- RF-res is [0.531, 0.551] at d=1, and CUSUM is [0.542, 0.587] at d=2. The effect is resolved at every drift scale.
- Contrast with Blind-cal, the true null: 2 of 40 intervals exclude 0.5, as expected at 95% coverage. This diagnostic supports the bootstrap and makes the Blind-thresh signal credible.
- A per-window shift of about 0.14 SD (AUC ≈ 0.54) accumulates to about 3.8 SD over the 720-window attack and about 1.1 SD per 60-window block.
- The CUSUM uses k = 0.5, which is tuned for a ~1-SD shift and is the wrong tool for this effect.
- Fix:
  - Report a pre-specified attack-duration or block-level test, e.g. the mean of the decoy-gain residual r_1 over 60 and 720 windows, or a CUSUM with k matched to 0.1-0.2 SD, with its FPR.
  - Until then, say "not detected at α = 10^-3 per window", not "works at chance" or "passes every detector".

**M5. Post-hoc DCS+F is reported as a result in the introduction and discussion, while the Results section correctly calls it a hypothesis.**
- sec_intro.tex:14 says it "closes two blind spots of the DCS on fresh seeds". sec_discussion.tex:9 says "they recovered both attacks without extra false alarms".
- The fresh seeds (300-309) test only the FPR. The attacks are the same ones that motivated the floors.
- Blind-gain gives ê_d ≈ 0 and Blind-nodark gives Ŷ_0 ≈ 0 by construction, so AUC = 1.00 is close to tautological given floors at 0.5·median(ê_d) and 0.25·median(Ŷ_0) (exploratory.py:57-60).
- An attacker who adds errors at about 0.6 e_mis, or background at about 0.3 Y_0, passes.
- The floors also never fired on benign data: DCS and DCS+F benign FPRs are identical in exploratory_dcs_f.json. So no false-alarm margin was measured.
- Fix:
  - Use the hedged wording of sec_results.tex:72 consistently.
  - Add Blind-gain and Blind-nodark variants placed just above the floors.
  - Report the distance of benign ê_d and Ŷ_0 minima from the floors at d=4.

## 3. Minor issues

- **m1. Bootstrap CIs (make_tables.py:56-63).**
  - A percentile bootstrap with n = 10 undercovers, at roughly 90% for symmetric data and less for skewed data. RF-DR d=4 seed values range from 0.06% to 25%.
  - Use BCa or studentised intervals, or print the seed min-max next to each interval.
  - The intervals depend on the global RNG call order (one `_rng` shared across all boot calls). Seed each call for reproducibility.
- **m2. Appendix α levels.** "The appendix tables give all three levels" (sec_results.tex:15) and "the appendix gives three" (sec_discussion.tex:21) are false. Every appendix table is at α = 0.1%. Add FPR/TPR tables at α = 10^-2 and 10^-4, or delete the sentences.
  - At α = 10^-4 the threshold rests on about 2.6 calibration exceedances. Say so.
- **m3. "These blocks can be withheld before the 10-minute block closes" (sec_results.tex:61).**
  - CUSUM delays on Blind-gain exceed 60 windows in 11 of 40 runs (max 170 = 28 min).
  - Report the share of first blocks released before the first alarm, and withheld blocks per run.
- **m4. Sensitivity table (tables/sens.tex) has no intervals.**
  - "Blind-gain and Blind-nodark are missed in every setting" (sec_results.tex:70) conflicts with TPR 0.11 on Blind-gain at 25 km, which is 100× the FPR.
  - Add bootstrap intervals and rephrase as "low TPR (≤ 0.11)".
- **m5. Bound violations (sec_results.tex:6, sec_intro.tex:14).**
  - "Slow intensity drift of one to a few per cent … sizeable share" does not hold at 1%: d=1 gives 4/1440, coming from 2 of 10 seeds.
  - At 2% and 4% the counts are 128 and 355.
  - Blocks within a seed are autocorrelated (OU τ = 2 h), so report seeds with ≥ 1 violation and per-seed counts.
  - d also scales the loss and misalignment drift. Use the existing int_drift_sd_rel sensitivity runs to isolate the effect of intensity drift.
- **m6. IR f=0.2 not marked.** It lies between the training fractions 0.1 and 0.25 (run_all.py:32) and is effectively in-distribution for RF-stat, RF-DR and RF-res. Mark it, e.g. "interpolated".
- **m7. Key audit not paired (tables/key_d1.tex, sec_results.tex:59-61).** Attack-block rates are compared with a different 24-h honest trajectory. For example, Blind-cal is 7.88 vs honest 7.62, which Proposition 1 says should be equal in distribution; seed-level differences range from -0.6 to +1.0.
  - Run key_audit(B, mask) on the honest copy, which is already in run_all.py:186, and report paired rate differences.
- **m8. Pairing description.** The "paired AUC" is an unpaired Mann-Whitney AUC on time-matched samples. Describe it that way, or also report the matched-pair concordance P(s_att,t > s_hon,t).
- **m9. AUC intervals in appendix tables.** The d=0/d=4 AUC tables have no intervals, and the d=2 table (tables/auc_d2.tex) is generated but not included, though the prose cites d=2 results (sec_results.tex:40, 44). Add both.
- **m10. sec_discussion.tex:23** quotes the range of point estimates (0.49-0.51) as "sampling spread". Quote the CIs instead (aucCalLoMin–aucCalHiMax = 0.47-0.52) and the 2/40 exclusion count.
- **m11. Comparability of CUSUM.** CUSUM TPR and FPR are inflated by persistence and not comparable with per-window detectors in tables/tpr_d1.tex. Footnote this and use episodes and delay for the CUSUM.
- **m12. RF-res calibration claim.** sec_intro.tex:12 and sec_conclusion.tex:4 say refit-based detectors need "drift-free calibration only". RF-res is trained on drift-randomised data, and its default threshold is drift-calibrated. Qualify the claim.
- **m13. "Blind-naive is caught by every detector" at d ≤ 1 (sec_results.tex:40).** This includes IF-stat and RF-stat, whose benign FPR is 95% and 74%. Restrict the claim to detectors that hold their FPR.
- **m14. Stale file.** tables/fpr_dcal.tex is an old ± table that is no longer input. Remove it from the release.

## 4. Verified as correct
Recomputed from seed_00..09.json or read from numbers.json against numbers.tex and the PDF text:
- **FPR at d=1:** Band 97.29%, IF-stat 95.11%, RF-stat 74.20%.
- **Drift-calibrated FPR:** IF-drift 0.53% (d=2) and 33.88% (d=4); RF-DR 0.96% (d=2) and 9.34% (d=4); RF-DR with the drift-free (control) threshold 57.68% (d=4).
- **DCS FPR:** 0.087, 0.073, 0.080, 0.072%, matching "0.07-0.09%".
- **Paired FPR differences at d=4:**
  - DCS − IF-drift: −33.81 pp [−39.79, −26.94]; my bootstrap gives [−39.98, −26.84].
  - DCS − RF-res: [−0.03, 0.01]; mine gives [−0.027, 0.007].
- **Episodes at d=1:** DCS 6.3 (equal to its alarm count, so all alarms are isolated), RF-stat 433.7, IF-stat 233.3. The episode counter (run_all.py:115-118) is correct.
- **AUC at d=1:** DCS Blind-gain 0.62 and Blind-nodark 0.57; CUSUM Blind-gain 0.98; RF-stat Blind-track 0.18; IF-drift Blind-track 0.74; Blind-static QBER 0.01 and IF-stat 0.00. QBER on PNS at d=0: 0.07.
- **TPR at d=1:** CUSUM Blind-gain 0.87; RF-DR Blind-nodark 0.53.
- **Detection and delays:** detNaiveDCS 40/40 with delay 0 in every run; CUSUM on IR f=0.05 40/40, median delay 1; CUSUM on Blind-gain median 33, max 170.
- **Key audit:** Blind-naive rate 23.37×10^-4; IR f=0.05 known fraction 2.50%; bound violations 0/5760 with monitored intensities and 0/4/128/355 with nominal; breach | ℓ>0 minimum 93.5% (Blind-cal, d=4); in-model breach 0.
- **Exploratory DCS+F:** FPR 0.08% (d=1) and 0.11% (d=4); AUC 1.00 on Blind-gain and Blind-nodark at every scale. DCS+P FPR 9.65, 25.36 and 38.70%.
- **Sensitivity table** values against the macros.
- **Code checks:**
  - The randomised threshold (detectors.py:215-228) is correct. With method="higher", the fraction strictly above the threshold is at most α, and g makes the calibration rate exactly α. RF ties are handled (g varies per seed for RF-stat).
  - FPR and TPR use the expected alarm probability; episodes use realised draws from a separate RNG. This is consistent.
  - The paired honest copy shares iscale/imon and the channel state (qkdsim.py:288-333, run_all.py:63-79).
  - Blind-cal null diagnostic: 38/40 AUC intervals cover 0.5, which supports the bootstrap's nominal coverage on a true null.
  - Delays and t0 placement are confined to hours 4-20.

---

REFEREE 2 REPORT (QKD physics and novelty), revised manuscript "What count telemetry can and cannot reveal about detector-control attacks on decoy-state QKD"

(1) SUMMARY AND RECOMMENDATION

The revision is a real improvement. The simulator now has Bob's basis choice and sifting, per-basis misalignment, an afterpulse background, intensity drift and an intensity monitor. Vacuum clicks injected by Eve now have error 1/2 and give her no knowledge. Proposition 1 is honestly labelled as elementary, and its achievability condition is now correct. Physics baselines (two-sided Band, CUSUM) have been added, and the related work is mostly accurate.

I checked finite_key.py line by line against Lim et al. 2014, and it is correct. Three problems remain:
- The two headline "invisible attacker" results, Blind-cal and Blind-thresh, still give Eve oracle access to Bob's internal state in every window.
- The breach/"key known" language overclaims, and the abstract contradicts the paper's own numbers.
- The intensity-drift side result ignores an established literature and replaces one non-rigorous assumption with another.

Novelty for QST is borderline. Prop. 1 is trivial, and the DCS is a per-window decoy-consistency check close to the "decoy residuals" of Mohamed & Al-Kuwari. "Drift-free calibration fails under drift" is expected. The useful contribution is the drift/false-alarm benchmark combined with the ground-truth audit, which reads more as an engineering/benchmark paper.

Recommendation: MAJOR REVISION. If the authors cannot sharpen the novelty claim against Mohamed & Al-Kuwari and the intensity-fluctuation decoy literature, I would lean to reject for QST.

(2) MAJOR ISSUES

M1. The headline "undetectable" attacks assume an oracle Eve. This is the residual circularity from round 1.
- Location: code/qkdsim.py:236-266; code/run_all.py:39-52; sec_model.tex:95; abstract.tex:1.
- What the code does: Blind-cal reproduces honest_yields(eta(t), y0(t), ed(t)) exactly. Blind-thresh fits eta_E per window to the true q1(t) and uses the true y0(t) and ed^b(t). Afterpulses are emulated with the true p_ap(t) (afterpulse=True). So Eve knows, without error or delay, Bob's detector-efficiency OU state, the temperature-driven dark count and afterpulse level, both misalignment ramps, and the exact reset times of Bob's active compensation.
- Why it is a problem: under blinding Eve cannot observe the counterfactual honest channel. She can only extrapolate it from earlier public announcements. Section 4 says she can estimate the loss "from her own measurements of the line", but that covers eta_fibre only, not eta_B, Y0, p_ap or e_d^b. The compensation loop also acts on Bob's physical polariser and would not reset Eve's emulated ramp unless she imitates the reset.
- Consequence: the abstract statement "An attacker with an ordinary attenuated threshold detector scored AUC 0.50-0.56 against every detector" is really "an attacker with a threshold detector and an oracle".
- Fix: add a realistic intermediate attacker, Blind-lag. It estimates (eta, Y0, e_d^b, p_ap) from the public announcements of the previous m windows before the attack and extrapolates them, with or without a model of the compensation resets. Report its AUC/TPR at d = 1, 2, 4. Rephrase the abstract and conclusion (sec_conclusion.tex:3) to state the knowledge assumption explicitly. Blind-static and Blind-track are the two extremes; the realistic case lies between them and is missing.

M2. The breach audit overclaims, and the abstract contradicts the results.
- abstract.tex:1 says "every key released under faked-state attacks was known to the attacker".
- sec_results.tex:61 says "once the bound releases a key under a faked-state attack, that key is known".
- sec_conclusion.tex:3 says "outputs a key the attacker knows".
- But \breachGivenPosMin = 93.5%, and sec_results.tex:61 itself lists Blind-cal/Blind-thresh blocks at d = 4 that released a key and did not breach. So "every" is false.
- Criterion (eq:breach) also only establishes "not epsilon-secret", not "known".
- Fix: say "every key-producing block failed the secrecy audit, except N blocks at d = 4", and drop "known" for the key; Eve knows about 99% of the sifted bits, not the final key.

M3. The breach-criterion derivation (sec_model.tex:101-105) mixes entropy notions and drops a term.
- The text bounds the min-entropy and then invokes "continuity of entropy", which applies to von Neumann/Shannon entropy.
- The correct chain is H(K|E,C) <= H(X_A|E,C) <= n_Z - K_E, using Shannon entropy (K_E bits are deterministic given E). Alicki-Fannes-Winter for an epsilon-secret key gives H(K|E,C) >= (1 - eps)·l - (1 + eps)·h(eps/(1 + eps)).
- So the breach threshold is l > (n_Z - K_E + g(eps))/(1 - eps), not l > n_Z - K_E. The term "O(eps)" is not a derivation.
- Numerically irrelevant here, but a QST proof should be exact. Fix: state the inequality with explicit constants. Also say that the epsilon_sec definition used (Lim's (1 - p_abort)·trace distance) is what enters.

M4. The intensity-drift side result needs prior literature, and its own fix is not rigorous.
- Locations: sec_intro.tex:14, sec_results.tex:6, abstract.tex:1, code/run_all.py:98.
- Decoy-state QKD with intensity fluctuations and errors is well studied, and none of it is cited:
  - Wang, PRA 75, 052301 (2007)
  - Wang, Peng, Ma et al. on source errors (2008)
  - Hu & Wang, PRA (2010)
  - Mizutani et al., NJP 17, 093011 (2015), finite-key analysis with imperfect sources
  - later intensity-interval bounds
- The remedy used here is not proven secure. key_length takes the block mean of the monitored intensities, while the true photon-number law is a mixture of Poissons over windows (1% fast noise plus slow OU drift), and the 0.2% monitor error enters nowhere.
- "0 violations in 5760 blocks" only shows a failure rate below about 5e-4. That is not a 1e-10 security statement.
- The "sizeable share" claim also holds only at d >= 2: \violNomDOne = 4 of 1440 at d = 1, against 128 and 355 at d = 2 and 4. "One to a few per cent ... suffices" (sec_results.tex:6) is therefore inaccurate at 1%.
- Fix: cite this literature. Either implement interval-intensity decoy bounds ([mu_k^L, mu_k^U] from monitor min/max plus the monitor error) or state clearly that the block-mean substitution is heuristic. Rephrase the claim as "at drift >= 2% relative s.d.". Also check the phase-error bound v_X1 against true single-photon X errors, not only s_Z1; the simulator does not record those errors (qkdsim.py:321-322).

M5. Novelty and the positioning against Mohamed & Al-Kuwari are overstated.
- I fetched arXiv:2603.03502. It uses block telemetry with decoy residuals from Poisson-mixture reconstruction, timing moments, per-detector imbalance and double clicks, calibrates detection to a target false-alarm rate, uses domain randomisation, and projects adaptive attacks onto feasible sets that include "decoy-consistency bands".
- That is an attacker tuned to the monitored decoy statistics, and the DCS residuals are conceptually the same object.
- sec_intro.tex:7 ("the cited studies answer neither quantitatively") and sec_background.tex:12 overstate the gap.
- Fix: state precisely what is new relative to that work: per-window rather than per-block evaluation, explicit 24-hour correlated drift, a paired honest copy, and a ground-truth audit. Drop "neither".
- Isha et al. (arXiv:2608.04047, verified: 24,000 balanced sessions, XGBoost, FNR 0.0198 against 0.8477) also report a CUSUM baseline, which the manuscript does not mention. Please mention it.

M6. The afterpulse model dominates the background, and the interpretation needs care.
- Location: qkdsim.py:323-329; Table 1.
- p_ap·Qbar = 3.7e-5 per gate, against Y0 = 1.2e-6. Afterpulses therefore make up about 92% of the vacuum-like gain Q_mu3, and they are what s_Z0 credits as secret vacuum bits.
- Real afterpulses are time-correlated with earlier clicks of the same detector, so their bit value repeats an earlier bit. The model makes them i.i.d. per gate with a random bit. This is (a) why Eve can "emulate" them trivially and (b) why counting them in s_Z0 as Eve-ignorant is questionable.
- Fix: state this explicitly in Sec. 3.2. Report a p_ap = 0 control for the key audit and the Blind-nodark/DCS+F results. Turn "any afterpulse clicks are reproduced" in Prop. 1 (sec_model.tex:85) into a precise hypothesis: the attack induces the same per-gate i.i.d. background law.

(3) MINOR ISSUES

m1. Blind-naive is described inconsistently.
- Table 2 (sec_model.tex:69) says "threshold-detector faked states".
- The code (qkdsim.py:223-227) gives y_n constant for all n >= 1, which is a unit-efficiency detector followed by random discarding, not attenuation. A threshold detector would give 1 - (1 - eta_E)^n.
- Fix: say so in the table.

m2. sec_model.tex:95 says the yields differ "only at order eta for n >= 2". The absolute difference is O(eta^2) and the relative difference O(eta). Please state which. The 0.2% figure is confirmed: decoy gain +0.20%, vacuum gain +0.16%.

m3. sec_method.tex:3 says Y0 "absorbs afterpulses, since they add a nearly constant background". The afterpulse background scales with Qbar, and therefore with eta(t). Say that it is constant across intensities within a window, which is what the refit needs.

m4. sec_background.tex:4. Lim et al. argue that the Hoeffding step applies to the random intensity tags. The i.i.d.-only caveat is defensible, but cite the follow-up works that use Azuma/Kato concentration (e.g. Zhang et al., PRA 95, 012333 (2017)) rather than leaving it unreferenced.

m5. sec_results.tex:38 and sec_discussion.tex:23. An AUC of 0.49-0.51 for Blind-cal is a simulator sanity check, not evidence. Move it to a validation paragraph so readers do not take it as a finding.

m6. No sequential baseline on raw physics quantities exists. The CUSUM runs only on the DCS score. Add a CUSUM on the two-sided Band score, so the "refit vs level" comparison is not confounded with "sequential vs single-window".

m7. sec_setup.tex:9. A QBER rule calibrated to 11% is a straw man. A one-sided QBER rule at the drift-free (1 - alpha) quantile would be the fair physics baseline. Add it, or say why it is omitted.

m8. sec_model.tex:85. "Identical in both of Bob's bases" should read "independent of Bob's basis choice for the click probability", while e_{b,n} may depend on the sifted basis. As written it seems to forbid basis-dependent errors, which the honest model has.

m9. Table 1 and sec_model.tex:21. Monitoring a mu3 = 2e-4 intensity to 0.2% per 10-second window needs justification, e.g. measurement before the final attenuator. Add the sensitivity to sigma_M.

m10. refs.bib has wilcoxon1945 and holm1979 left over. They are harmless but unused; remove them.

(4) ITEMS VERIFIED AS CORRECT

- Round-1 items fixed:
  - Sifting and Bob's basis choice (qkdsim.py:316-317; test_sifting_fraction).
  - Per-basis misalignment.
  - Vacuum injected clicks: e = 1/2, kappa_0 = 0 (qkdsim.py:222-230; test at test_sim.py:51-56).
  - Feasibility condition y_n <= min(q, 1 - q) for Eve's basis bias q. Derivation checked: q·r_Z = y_n with r_Z <= 1.
  - Band and CUSUM baselines added.
  - Gras 2021, Qian 2019, Ferreira da Silva 2012, Lee 2016 and Koehler-Sidki 2018 added and described acceptably.
  - Mohamed & Al-Kuwari's finite-key secret fraction, three-intensity decoy estimators and entropy-accumulation penalties now described correctly (verified on arXiv).
  - Hoeffding i.i.d. caveat stated.
  - The breach test is now explicitly one-sided.
  - DCS initialisation text matches the code (sec_method.tex:7-10 vs detectors.py:43-48; 6 iterations).
- finite_key.py matches Lim et al. 2014:
  - delta = sqrt(n_Z/2·ln(21/eps)); n^± = (e^k/p_k)(n_k ± delta).
  - s_Z0, s_Z1 and v_X1 formulas.
  - gamma(eps, phi, s_Z1, s_X1).
  - l = s0 + s1(1 - h(phi)) - lambda - 6·log2(21/eps_sec) - log2(2/eps_cor).
- Attack models check out:
  - IR yields and errors: (e_d + 1/2)/2 on intercepted clicks; kappa = 1/2.
  - PNS gain matching: c = (q1 - Y0)/(p_{n>=2}·eta_B·(1 - Y0)), feasible at 50 km.
  - Blind-thresh yield formula: y_n = Y0 + (1/2 - Y0)(1 - (1 - eta_E)^n), derived from Eve forwarding on a click plus injecting 2·Y0 when her detector is silent.
  - Honest feasibility y_n <= 1/2: it needs n of about 69, far beyond the NMAX = 30 truncation.
- Results consistency:
  - Key-audit numbers are consistent: K_E/n_Z = 0.025 for IR at f = 0.05 (= f/2), and 0.990 for emulated-afterpulse attacks.
  - Abstract figures match numbers.tex: DCS false-alarm rate 0.07-0.09%; 40/40 detection in the first window; 355/1440 violations.
  - The breach index uses the same n_Z and K_E summed over all intensities, as Lim's key does (run_all.py:95-106).

Sources: [arXiv:2603.03502](https://arxiv.org/html/2603.03502v1), [arXiv:2608.04047](https://arxiv.org/pdf/2608.04047)

---

**Referee 3 report (QKD systems engineering and adversarial evaluation): revised manuscript "What count telemetry can and cannot reveal…"**

## 1. Summary and recommendation
The revision deals with most of the points from the last round. It adds per-basis misalignment fitted per basis, afterpulses, slow intensity drift with a monitor, a two-sided Band, a CUSUM, IF-res and RF-res, RF-DR without loss labels, control thresholds, a threshold-detector rung (Blind-thresh) and a fibre-tracking attacker (Blind-track). It reports alarm episodes per day, adds α=1e-4, and states the indistinguishability argument more modestly.

The central operational claim is still not supported. The claim is that the DCS and its CUSUM hold about 1e-3 per window up to fourfold drift with drift-free calibration only. The drift model moves almost exactly the four parameters (η, Y0, e_d^Z, e_d^X) that the DCS refits per window, and it removes intensity drift through a monitor that is assumed unbiased. Robustness is therefore close to built in.

My probes add one more plausible benign degree of freedom: basis-dependent detection efficiency, polarisation-dependent loss, or monitor ratio bias. Each breaks the DCS, and the CUSUM breaks even faster. The post-hoc DCS+F also fires on ordinary benign operational changes and is beaten by an attacker who stays just above its floors.

**Recommendation: major revision.**

## 2. Major issues

**M1. The DCS false-alarm rate depends on the absence of basis-dependent efficiency drift (sec_model.tex:23; sec_method.tex:24 "Slow drift … moves the estimates, not the residuals"; abstract; sec_conclusion.tex:5).**
- **Where the sensitivity comes from:** residuals 5–7 (Bob's sifting fraction per Alice basis, and Alice's Z share) are tested at binomial precision. There are about 3e6 signal clicks per window, so σ of the sifting fraction is about 1.7e-4.
- **What breaks them:** any drift in the relative efficiency of Bob's two basis paths, or in Alice-basis-dependent transmission, moves these residuals. Examples:
  - passive-basis beam splitter, or four detectors;
  - the X-basis interferometer in time-bin systems;
  - polarisation-dependent loss in polarisation encoding.
- **Probe 1** (/tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3/p1.py):
  - Setup: 5 seeds, d=1, the paper's own drift-free calibration and α=1e-3. Control FPR: DCS 0.10%, CUSUM 0.07%.
  - Bob basis-path relative efficiency, OU with τ=1 h:

    | s.d. | DCS FPR | CUSUM FPR |
    |---|---|---|
    | 0.2% | 2.6% | 72% |
    | 0.5% | 31% | 99.7% |
    | 1% | 54% | ≈100% |
    | 2% | 75% | ≈100% |

    The model already uses 2% OU for the common efficiency.
  - A one-off +1% step in one basis path (re-bias or recalibration of a detector): DCS 88%, CUSUM ≈100% after the step.
  - Alice-basis-dependent transmission, OU with τ=30 min:

    | s.d. | DCS FPR | CUSUM FPR |
    |---|---|---|
    | 0.2% | 2.1% | 90% |
    | 0.5% | 26% | 99.7% |
    | 1% | 57% | 99.9% |

- **Fixes:**
  - Model independent efficiency drift per detector or path, and PDL that tracks the polarisation drift.
  - Either add per-basis efficiency as a fitted parameter, with an explicit cost in power on Blind-gain/nodark-type attacks, or drop residuals 5–7 and report the power lost.
  - State a quantitative stability requirement, e.g. "basis-path efficiency ratio stable to <0.1% per hour".
  - Remove "Detector-efficiency mismatch … not modelled" from the end of the threats-to-validity list (sec_discussion.tex:17) and treat it as a first-order limitation.

  Mismatch between the two detectors within a basis (bit-dependent) cancels at first order in these counts when bits are uniform; I verified this analytically. The basis-dependent mismatch is the one that matters.

**M2. The intensity-monitor requirement is understated (sec_results.tex:6, 70; Table sens).**
- The monitor is modelled as white 0.2% error with no bias.
- **Probe 1, monitor ratio bias** (independent OU per intensity, τ=2 h), d=1:

  | Bias s.d. | DCS FPR | CUSUM FPR |
  |---|---|---|
  | 0.2% | 0.27% | 15% |
  | 0.5% | 4.2% | 88% |
  | 1% | 31% | 99.8% |

- A 2×10⁻⁴ vacuum-like intensity and the decoy/signal ratio set by modulator extinction are exactly where monitors are least accurate.
- **Fix:** add monitor-bias drift to the sensitivity table, and state the monitor specification (relative ratio stability ≲0.2% over hours) as a precondition of every DCS claim.

**M3. The CUSUM is not an operational detector under realistic conditions, and the delay claims are overstated (sec_results.tex:44, 61).**
- **Fragility:** M1 and M2 take the CUSUM from 0.07% to 15–100% with effects that the per-window DCS barely notices. A persistent sub-σ residual shift from any unmodelled effect is exactly what it accumulates. Its Blind-gain "detection" (DCS AUC only 0.62) relies on such a shift, so it cannot be distinguished from benign mis-modelling.
- **"These blocks can be withheld before the 10-minute block closes" is false in a quarter of runs:**
  - From results/seed_*.json, CUSUM delays on Blind-gain are ≥60 windows in 11/40 runs (maximum 170 windows, 28 min).
  - Blind-nodark delays have a median of about 130 windows and a maximum of 573 windows (95 min).
  - Attack onset is not block-aligned in practice either.
- **Fixes:**
  - Report the fraction of PE blocks released before the first alarm, i.e. breached keys that were actually exported.
  - Report CUSUM ARL0 with a reset policy instead of a per-window quantile of an autocorrelated statistic.
  - Restrict the claim.

**M4. DCS+F's floors are crossed by benign events and circumvented by a trivial attacker (sec_results.tex:72; sec_discussion.tex:9; sec_intro.tex:14; sec_conclusion.tex:5).**
- **Ŷ0 is mostly afterpulses.** Per seed, Ŷ0 ≈ 3.7e-5, while the dark-count Y0 is 1.2e-6. The "background floor" is therefore an afterpulse floor, and afterpulses scale with gain. Probes 2–4 (p2.py, p3.py, p4.py):
  - A benign 5× reduction of p_ap (longer hold-off, gating change): DCS+F FPR 91–96%; DCS 0.07–0.12%.
  - A benign +7 dB loss step (fibre re-routing): DCS+F 95–96%. At +5 dB it is still 0.05%, so the cliff is close.
  - A better polarisation compensator, e_d to 0.45%: DCS+F 16.8%; DCS 0.11%.
- **The floors are easy to evade.** An attacker that emulates the honest channel with e_d = 0.6×nominal and Y0 = 0.3×honest stays just above the floors. The paired AUC is DCS 0.50, CUSUM 0.50, DCS+F 0.51, with TPR ≤0.02.

  | | Under this attack | Honest |
  |---|---|---|
  | Key rate (per pulse) | 1.07e-3 | 0.74e-3 |
  | Blocks breached | 100% | – |
  | Sifted key bits known to Eve | 99% | – |

  The gap between the floors and the honest values is a continuum that the attacker controls. The claim that DCS+F "closes two blind spots" (intro:14) should be removed.
- **Fixes:**
  - Present DCS+F as a negative or inconclusive result.
  - Add the "sub-floor" attacker to the attack ladder.
  - Define floors from physics, e.g. a minimum dark-count rate measured with a shutter, not from medians.

**M5. Baseline framing still relies on a deliberately poor calibration choice (abstract; sec_results.tex:11).**
- The headline FPR for Band, IF-stat and RF-stat (74–97%) uses drift-free thresholds.
- With drift-calibrated thresholds (Table fprctrl, and tpr_ctrl in results/seed_*.json), IF-stat at d=1 reaches:

  | Attack | TPR |
  |---|---|
  | Benign windows (FPR) | 0.03% |
  | Blind-naive | 0.52 |
  | Blind-gain | 0.58 |
  | Blind-nodark | 0.52 |

  At d=4 the FPR is 1.65%, against IF-drift's 34%. The DCS catches neither Blind-gain nor Blind-nodark.
- tpr_ctrl is computed but never reported.
- **Fix:** report TPR at both calibrations in the main TPR table, and do not lead the abstract with the drift-free strawman number. Also justify the misalignment sawtooth, +1%/h absolute reset hourly (e_d up to 2.7% at d=1 and 7.1% at d=4). It is what drives the level-based detectors' failure, and it is large compared with the active compensation reported in dixon2010 and dynes2012.

**M6. "Separable in reverse / only a two-sided rule can see them" is not demonstrated (abstract; sec_results.tex:42; sec_discussion.tex:12).**
- The AUC<0.5 for Blind-static and Blind-track is measured against the paired honest copy, an oracle the defender does not have.
- Blind-static windows look like the d=0 calibration data. A lower-tail rule calibrated drift-free would therefore alarm on them at exactly α.
- **Fix:** implement a lower-tail ("too quiet") rule with a drift-calibrated threshold and report its TPR/FPR, or rephrase the claim as "differs from the contemporaneous honest law".

## 3. Minor issues
1. **Attack ladder still incomplete (sec_model.tex:54–75).** Add or discuss:
   - an intermittent or partial-fraction attacker, e.g. Blind-naive on a fraction f of pulses or windows;
   - time-shift and efficiency-mismatch attacks, which partly survive in-basis counts;
   - an attacker that knows the detector and emulates whatever the refit absorbs, i.e. the sub-floor probe in M4.
2. **Dead time and gating (sec_model.tex:23).** At about 4.5e5 clicks/s with µs hold-off, dead time removes a large fraction of clicks. It is rate-dependent and intensity-independent, so I expect the refit to absorb it. Say so explicitly, and model the hold-off/p_ap trade-off, since that trade-off is what drives Ŷ0 (M4).
3. **Monitor dependence (sec_results.tex:70).** "Without the intensity monitor … 31.5% at d=4" should be stated in the abstract as a precondition, not only as a side result.
4. **Operational load (sec_results.tex:15).** 6.3 episodes/day at α=1e-3, and about 1 at 1e-4, assume a perfect model. Under M1/M2-level mis-modelling the CUSUM alarms almost continuously. Give an alarm budget per link per day and per network of N links.
5. **Latency (sec_method.tex:24).** 0.5 µs/window is irrelevant next to the 10 s window plus classical-channel and announcement latency; report end-to-end time to decision. The justification for per-window basis/intensity announcement ("revealed anyway") is acceptable, but note that it requires the post-processing stack to stream announcements per window.
6. **Stale file.** manuscript/tables/fpr_dcal.tex is not \input anywhere, but it contradicts the current numbers (DCS 0.18% at d=4) and uses another detector naming. Remove it.
7. **Blind-nodark is mostly afterpulse-free, not dark-count-free (run_all.py:41, BLINDED).** The missing background is about 97% afterpulses. Rename the attack or describe it accurately.
8. **Abstract claim on RF-DR.** "Catches inside its calibrated range" should state TPR 0.53 on Blind-nodark; that is not a reliable catch.

## 4. Verified as correct
- Basis-dependent misalignment is now fitted per basis. Sensitivity with e_mis = (0.01, 0.02) gives DCS FPR 0.10%. Fixed.
- Afterpulses and slow intensity drift are now modelled (qkdsim.py:146–176, 302–309).
- Blind-naive is flagged by the DCS in the first attacked window in 40/40 runs (delay 0 in every seed and drift scale). Confirmed.
- DCS FPR is 0.07–0.09% across d=0–4, and the CUSUM 0.06–0.13%, under the paper's own model (Table fpr; my control run gave 0.10% and 0.07%).
- Inside the paper's model, the DCS correctly absorbs sudden benign steps:

  | Benign step (Probe 2) | DCS FPR | CUSUM FPR |
  |---|---|---|
  | +3 dB loss | 0.07% | 0.05% |
  | Misalignment glitch +3% for 30 windows (both bases or Z only) | 0% | 0% |
  | Y0 ×3 | 0.12% | 0.05% |
  | p_ap ×3 | 0.10% | 0.23% |
  | Monitored 5% decoy step | 0.12% | 0.05% |

- RF-DR no longer uses loss as an attack label; supervised attacks seen in training are marked with *.
- Blind-thresh and Blind-track are implemented as described (qkdsim.py:244–262; run_all.py:48–57). Afterpulse emulation for the calibrated variants is consistent.
- The key-audit statements check out: blind known fraction 98.95–100%, no in-model breach, and the nominal-intensity bound fails in 4/128/355 of 1440 blocks.
- The randomised tie-breaking threshold is implemented correctly (detectors.py:212–227).

Probe scripts (read-only use of the repository code): /tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3/probe.py, /tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3/p1.py, /tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3/p2.py, /tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3/p3.py, /tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3/p4.py. No repository files were modified.

---


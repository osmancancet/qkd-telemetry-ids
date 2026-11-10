# round2 reports (full text of three independent referee reports)

**Referee 1 report (statistics and methodology): revised manuscript "What count telemetry can and cannot reveal…"**

**Note before the review.** The supplied text `/tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/main_r2.txt` is stale. It describes ten detectors, percentile bootstrap intervals and different numbers (for example DCS FPR 0.07–0.09%). `manuscript/main.pdf` is also older than the `.tex` sources. I rebuilt the current sources in my scratchpad (`/tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/build/cur.txt`) and reviewed that version, which has eleven detectors, BCa intervals and five drift scales. The submission PDF must be rebuilt.

**Summary.** The paper benchmarks count-telemetry detectors against faked-state and in-model attacks under simulated drift, with paired honest copies and a ground-truth key audit. Reproducibility is good. I checked 30+ quantitative claims against `results/numbers.json`, the per-seed JSON files, `sensitivity.json` and the `exploratory_*.json` files, and every one matched. These include the FPR values in Table 3 at all five drift scales; the paired difference −29.05 [−34.12, −23.59]; RF-DR at 42.51% with the drift-free control; 8.1, 2.9 and 2.7 alarm episodes per day; TPR 0.48 at α=1e-4; Blind-cal 2 of 55 intervals and Blind-lag 3 of 55 intervals excluding 0.5; Block TPR 0.43; 50/50 first-window detections; CUSUM median delay 17; the 2/103/325 bound failures; the 98.78% minimum known fraction; the 95.9% minimum breach share among blocks that released a key; +203.9% key length for Blind-naive; the released counts 17/7/5; DCS+P at 8.79/24.69/44.91%; the DCS+F stress results 47.7/19.7/48.1% with margin 1.62; and all Table 7 rows checked. The weaknesses are in inference and design, not arithmetic.

**Recommendation: major revision.**

### MAJOR

1. **The seeds are not fresh across review rounds (verified).** The main benchmark again uses seeds 0–9: `run_all.py` sets rng = 1000+seed, and `results/prev_block/` holds seed_00–09 from the earlier run. The revision's design choices were made after seeing round-1 results on these same seeds: four residuals instead of seven, the Block detector with L=60, and the new attackers. The post-hoc DCS+P and DCS+F were re-run on the same "fresh" seeds 200–209 and 300–309 (the `.old` files differ). Sec 6.3 says settings were "fixed before the final runs", which is true but not confirmatory.
   - *Fix:* rerun the frozen pipeline on held-out seeds (e.g. 10–49). At about 92 s per seed this is under 2 h. Label seeds 0–9 as development data. State the seed history explicitly in Sec 6.3.

2. **The withheld-block analysis does not follow its own policy (Table 6; Secs 7.3, 8.3 "all but 5 of 120"; verified).**
   - (a) `key_audit` counts only alarms from onset onward (`v[t0:b0+60]`). Under the stated rule "stop key release at first alarm", the DCS's first benign false alarm at d=1 comes at windows [1081, 650, 329, 2461, 382, 5, 532, 474, 104, 4645]. That is before the earliest possible onset (window 1440) in 8 of 10 seeds, so key release would already be halted when the attack starts. The implicit reset at onset is not stated.
   - (b) There is no baseline for the cost of withholding. False alarms alone withhold 58/120 Blind-static blocks and 21/120 Blind-cal blocks under the DCS, which tests as null on both (AUC ≈ 0.50).
   - (c) The counts have no uncertainty, and blocks cluster within seeds: DCS released counts per seed on Blind-static are 12, 2, 12, 4, 2, 7, 8, 0, 12, 3.
   - *Fix:* define a policy that can restart (withhold the current block on an alarm, resume at the next block). Apply it to the paired honest copy to measure the cost. Report released minus null-released per seed with seed-bootstrap intervals.

3. **Averaging a signed AUC hides seed-level separability of Blind-lag (abstract, Secs 7.3, 8.3, 9; verified).** "No detector separated…" and "AUC at most 0.55" rest on means over seeds. Per-seed AUC ranges are much wider: QBER and Band at d=1 run 0.09–0.91 and at d=2 run 0.04–0.91; IF-drift at d=4 runs 0.17–0.90. Opposite-signed effects cancel in the mean, because a stale estimate drifts either way.
   - *Fix:* report mean |AUC−0.5| (or max(AUC, 1−AUC)) per seed with an interval. Restate the claim as "no operating-point detection" (oracle TPR ≤ 0.01), which the data do support. Apply the same check to Blind-cal and Blind-thresh.

4. **"Holds the target" is a claim about means; operators face a conditional FPR (Secs 7.2, 8.2, abstract; verified).** One link corresponds to one seed. Per-seed FPR at α=1e-3 ranges as follows: DCS 0.02–0.23%, CUSUM 0–0.58%, Block 0–0.48% at d=4. The Block mean at d=4 is 0.18 [0.09, 0.29], about 2α.
   - *Fix:* report the per-seed distribution (maximum, and the share of seeds above 2α). Quantify the uncertainty of threshold estimation: the 1e-3 quantile comes from about 26 exceedances in serially dependent calibration windows. Soften "near target" for the sequential detectors.

5. **The sequential detectors are evaluated with the wrong metrics (Table 4, Sec 7.3, abstract; verified).** The CUSUM never resets after an alarm (`detectors.py`, class CUSUM), so its per-window "TPR" (0.95 on Blind-gain) measures how long it stays above threshold, not detection. After a Blind-gain attack ends, its alarm rate in the non-attacked windows is 4.8% [4.1, 5.7] (`fpr_outside`). The paper acknowledges that the measures are not comparable but still ranks detectors by TPR.
   - *Fix:* add a reset-after-alarm variant. Report ARL0, the time to first false alarm, which is already in `numbers.json` as `first_fa` but is unused. Compare detection delay at matched ARL0 for all detectors, using the geometric ARL for single-window detectors. Drop per-window TPR for CUSUM and Block from the abstract and from cross-detector comparisons.

6. **Calibration is presented as the only weakness (Sec 8.2; verified).** "Their weakness is calibration, not discrimination" fails at d=4. IF-drift's matched-FPR TPR there is 0.00 on Blind-gain, 0.00 on Blind-sub and 0.01 on IR with f=0.2 (Table 18). In the same paragraph, "no false alarm at d≤1" contradicts RF-DR's 0.06% at d=1. "Several-fold at d=2" does not hold for RF-DR: 0.17% [0.09, 0.26], an interval that includes the target.
   - *Fix:* restrict the claim to d≤1 and correct the two statements.

### MINOR

7. **Blind-cal equivalence (Sec 8.5; judgement).** "2 of 55, as expected under exact equality" treats 55 correlated cells (the same streams feed 11 detectors) as independent, and BCa with n=10 undercovers. Use an equivalence test (TOST with a stated margin) on pooled per-seed AUCs, or simply state that Proposition 1 holds by construction and the check only validates the simulator.

8. **Number of seeds and BCa (Sec 6.4; verified).** With n=10 and mostly-zero data (RF-DR at d=1 has 8 of 10 seeds at zero), the reported interval [0.00, 0.19] is unreliable. The `boot()` function silently falls back to percentile intervals and returns a degenerate interval when all values are equal (10 of 55 FPR cells). Disclose both behaviours and increase the number of seeds; this ties into item 1.

9. **Rationale for not testing (Sec 6.4).** "A rank test cannot go below p=0.002" is not a reason to avoid inference. Either drop the sentence or report paired sign-flip permutation tests with a multiplicity correction alongside the effect sizes.

10. **Oracle threshold (Tables 17–18; verified).** The threshold is estimated in-sample on the same 8640-window benign stream, about 9 exceedances. State this, and note that oracle TPR is one-sided and cannot register reverse separation (Blind-static, Blind-lag).

11. **DCS+F result reported at one drift scale only (Sec 7.5; verified).** On Blind-sub, DCS+F reaches AUC 0.75 at d=4 (`exploratory_dcs_f.json`); only the d=1 value of 0.50 is reported. Give all scales.

12. **One-factor sensitivity design (Table 7; judgement).** One factor at a time misses interactions such as monitor bias × p_ap=0. The CUSUM reaches 0.94% at p_ap=0 with d=4, which is a third precondition missing from the preconditions in Sec 8.4 and Sec 9. Add a small factorial design or a Latin hypercube, and list p_ap as a precondition.

13. **Seed variability in the sensitivity nominal row (verified).** Its IR TPR of 0.73 against 0.69 in the main run, and Block TPR on Blind-thresh of 0.49 against 0.43, show seed-to-seed spread. Give intervals in Table 7.

14. **Fragile abstract range (verified).** The range "\fprDCSDZero–\fprDCSDQuarter" is built from macros chosen by drift scale, not from the minimum and maximum. It happens to be correct now (0.09–0.12); generate it from min/max.

15. **Unit of the IR key change (Sec 7.4).** Write "−50.9%" as a relative change of the per-seed ratio of summed key lengths, averaged over seeds, and give its interval [−51.5, −50.3].

**Files:** results in `/home/user/qkd-telemetry-ids/results/`; code in `/home/user/qkd-telemetry-ids/code/run_all.py` (key_audit, `realised_alarms`), `/home/user/qkd-telemetry-ids/code/detectors.py` (CUSUM, Block, threshold) and `/home/user/qkd-telemetry-ids/code/make_tables.py` (`boot`).

---

**Referee 2 report: "What count telemetry can and cannot reveal about detector-control attacks on decoy-state QKD"**

**Summary.** The paper builds a window-level simulator of three-intensity decoy-state BB84 with drift, afterpulses and an intensity monitor. It benchmarks ten telemetry detectors against three in-model and seven faked-state attacks and audits each finite-key block against the key bits Eve knows. Proposition 1 shows that an attacker who reproduces the yields leaves the count law unchanged. The physics is mostly sound, and the finite-key code matches Lim et al. 2014. The DCS idea of refitting the channel in every window is useful. Four things stop me recommending acceptance:
- the released code and results do not reproduce the PDF;
- the secrecy audit cannot detect a breach under in-model attacks;
- the breach argument is stated loosely;
- the attacker-knowledge and intensity assumptions are under-discussed.

**Recommendation: major revision.**

### MAJOR

**M1. The released code and results do not match the manuscript (verified).**
- main.pdf (23:14) is older than code/*.py, results/seed_*.json and the .tex sources (23:22–23:57).
- The released run has five drift scales (including d=0.25) and 15 attacks: it adds blind_lag, blind_sub and blind_partial, none of which is in Table 2. It also has a DCS-block detector, and qkdsim.Config switches on basis-path and PDL efficiencies (path_eff_sd_rel=0.005, pdl_sd_rel=0.0025). The PDF mentions none of this.
- Recomputed from results/: DCS FPR at d=1 is 0.094% (PDF: 0.07%). Nominal-intensity bound failures at d=1/2/4 are 2/103/325 (PDF: 4/128/355).
- abstract.tex now says "eleven detectors… ten faked-state attacks".
- Fix: deposit a frozen code and results version that regenerates every number in the submitted text, or resubmit the text that matches the release.

**M2. The secrecy audit cannot detect a breach under in-model attacks (verified).**
- Honest ℓ/n_Z is about 0.25 and IR f=0.05 gives ℓ/n_Z of about 0.12. Test (6) can therefore fire only if Eve knows more than about 75–88% of the sifted bits.
- So "no in-model attack produced a breach" (§7.4, §8.1: "splits the attacks cleanly", "as Remark 1 predicts") carries no evidential weight. The paper already admits the faked-state half is pure accounting (l.238–240, 432).
- For IR and PNS, Eve's information is fully specified by construction: she knows a bit exactly or not at all. Fix: compare ℓ with n_Z − K_E − λ_EC, or with the exact H(Z|E) per block, stating the approximation. Otherwise drop the claim that the audit supports Remark 1.
- The released blind_partial (KE/nZ = 0.10, breach 0) shows the same lack of power for model-violating attacks.

**M3. The breach inequality (§4, l.230–236) mixes entropy notions (verified against run_all.breach_threshold).**
- The text says "conditional min-entropy … at most n_Z−K_E" and then invokes "continuity of entropy" with an h(ε) term. Alicki–Fannes–Winter applies to von Neumann (Shannon) entropy.
- The code has the right form: H(K|E) ≥ (1−ε)ℓ − (1+ε)h(ε/(1+ε)).
- Fix:
  - Write the chain H(K|E,C) ≤ H(Z|E) ≤ n_Z − K_E (von Neumann). K is a function of Z and public data, so this holds, but say so.
  - State the AFW constant exactly.
  - Account for Lim's (1−p_abort) factor.
  - ε-secrecy is an ensemble statement, so one block "cannot be ε-secret" is imprecise. The correct claim is that a non-negligible breach frequency contradicts ε-security, which holds here because the frequency is about 1.

**M4. Attacker knowledge and achievability of Proposition 1 (judgement, partly verified).**
- Blind-cal is an oracle: Eve knows η(t), Y0(t), e_d^b(t) and the afterpulse rate in every window. Once Bob's detectors are blinded, she can no longer observe his efficiency or misalignment drift.
- §4 (l.217–218) only says she "can estimate the loss". Fix: give a feasible estimation model in the main text, with its achievable accuracy versus window statistics. The released blind_lag, which estimates the channel from public counts before onset, already does this.
- In the released code, sample() applies Alice-basis-dependent transmission (abas) and Bob path efficiencies to attacked streams as well (verified, qkdsim.py l.319–332). This has two effects:
  - The attacker reproduces an Alice-basis dependence without knowing Alice's basis, which is physically impossible.
  - "Blind-static: no drift at all" and Blind-track still inherit path and PDL drift.
- Whichever version is final, either remove these factors from the attack branch or model what Eve can actually emulate. Then restate Proposition 1, whose hypothesis "identical in both of Bob's bases" is violated by an honest channel with basis-dependent efficiencies.

**M5. Intensity assumptions and the "side result" (judgement).**
- Within a block, intensities fluctuate (1% fast noise plus OU drift), so the photon-number law is a Poisson mixture and τ_n is computed at the block mean. The 0.2% monitor error is not propagated.
- "0 of 5760" is an empirical check, not a guarantee. The paper should say so and cite the decoy-with-intensity-fluctuation literature:
  - Wang et al. NJP 11, 075006 (2009)
  - Hu & Wang PRA 81 (2010)
  - Mizutani et al. Sci. Rep. 5, 8586 (2015)
  - Yoshino et al. npj QI 4, 8 (2018)
  - Zapatero et al. Quantum 5, 602 (2021)
- Remark 1 ("every key it outputs is already secure") silently assumes a trusted monitor and source. Attacks on the mean photon number, which also target the monitor, are directly relevant: Sajeed et al. PRA 91, 032326 (2015) and Huang et al. PRApplied 12, 064043 (2019, laser seeding). Add them to the threat model and Remark 1.
- Present the nominal-intensity bound failure as a quantitative illustration of a known requirement, not as a new finding.

**M6. Novelty relative to [17] is overstated (verified from the arXiv abstract).**
- Mohamed & Al-Kuwari already use an adaptive, hardware-bounded adversary including blinding, block telemetry with decoy residuals, timing moments and detector imbalance, and a defender objective tied to finite-key secret fraction with EAT.
- Line 48 ("the cited studies answer neither quantitatively") and §8.1 should be toned down accordingly.
- I could not confirm "domain randomisation of [17]" from its abstract: give a section number or rephrase.
- The new contributions are the drift-FPR study, the paired AUC and the exact-emulation boundary. Say so.

### MINOR

1. **[5] is not decoy-state BB84 (verified).** l.59 and l.211: Gerhardt et al. attacked an entanglement-based BBM92 system with no decoy states. Calling it "an instance" of Proposition 1 is loose. Say "an analogue in a non-decoy system".
2. **Hoeffding and coherent attacks (judgement).** l.99–101: the remark is correct, but cite the works that fix it: Zhang et al. PRA 95, 012333 (2017), using Kato's inequality, and Yin et al. Sci. Rep. 10, 14312 (2020).
3. **Finite-key code matches Lim et al. (verified).** finite_key.py matches Lim et al. Eqs. for n^±, s0, s1, v1 and γ, with the 21-way ε split. State in Table 1 where the parameters deviate from Lim's example (e_mis, p_ap).
4. **Attack constructions match Table 2 (verified).** I checked IR, PNS, Blind-naive, Blind-gain, Blind-nodark, Blind-thresh (the y_n formula and η_E bisection), Blind-cal, Blind-static and Blind-track. Two additions to Table 2:
   - Blind-gain and Blind-nodark also carry no afterpulses (BLINDED set).
   - PNS assumes a quantum memory, since Eve must measure after the basis announcement.
5. **Faked-state mechanism (judgement).** l.186–191 implicitly assumes no double clicks and perfect detector control. Cite the thermal-blinding and SNSPD controllability results (Lydersen et al. NJP 13, 113042, 2011), and the after-gate attack (Wiechers et al. NJP 13, 013043, 2011).
6. **Photocurrent monitoring [21] (judgement).** It was disputed; cite Lydersen et al., Nature Photon. 4, 801 (2010).
7. **Missing calibration-attack literature (judgement).** Jain et al. PRL 107, 110501 (2011) and Fei et al. Sci. Rep. 8, 2018, on Eve manipulating calibration. These bear on the drift-free calibration a defender relies on.
8. **Missing certification context (judgement).** ETSI GS QKD 016, ISO/IEC 23837, and Makarov et al. PRApplied 22, 044076 (2024).
9. **Misattributed citation (verified, text).** l.139–140: [36] (Tokyo network) is cited for the SwissQuantum duration. Stucki et al. report about 1.5 years, so "close to two years" overstates.
10. **Isha et al. [16] (could not confirm).** The arXiv abstract gives neither the 24,000-session dataset size nor gradient-boosted trees. Check these against the paper body.
11. **Afterpulse model (judgement).** In the released sources, afterpulses make up about 97% of Y0. Their independent per-gate Bernoulli model removes the temporal correlation that a real monitor such as [19] exploits. Say this in §3.2.
12. **Feasibility condition (judgement).** l.213: the condition y_n ≤ min(q, 1−q) requires Eve's forwarding probability to depend on her basis. Say so.
13. **Bound-failure benchmark (judgement).** §7.1: the bound-failure counts should be compared with the expected failure rate of order ε_sec, which makes even 4/1440 decisive. State this explicitly.

---

**Referee 3 report: operational QKD systems, IDS practice, reproducibility**

**Note on what I reviewed.** The PDF text I was given (`main_r2.txt`) and the committed `manuscript/main.pdf` (built 23:14) are out of date. They describe a 7-residual DCS, ten detectors and no Block detector. The current LaTeX describes a 4-residual DCS, eleven detectors, the Block detector, and the Blind-lag, Blind-sub and Blind-partial attacks. `manuscript/build.log` shows the rebuild failed with "latexmk: command not found". I compiled the current sources into the scratchpad (`/tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3r2/tex/`, 32 pp.) and reviewed that version. Line numbers below refer to it.

**Summary.** The paper benchmarks eleven count-telemetry detectors on simulated drifting 24-hour decoy-BB84 streams. It states an indistinguishability boundary and audits key secrecy against a ground-truth count of key bits Eve knows. The revision is honest about post-hoc choices (Block detector, DCS+F reported as a negative result) and much more careful than the first round. The main weaknesses are operational:
- the DCS and its sequential forms use per-window Z-basis error counts, which a real link may not have in real time;
- the key-withholding claim has no benign cost attached;
- the sequential detectors are calibrated per window despite serial dependence;
- the intensity-monitor precondition is more fragile than the paper states.

**Recommendation: major revision.**

---

### MAJOR

**M1. Submitted PDF does not match the sources. (verified)**
- **Where:** `manuscript/main.pdf`, `build.log`.
- **Problem:** Readers and reviewers see a different method (7 residuals, no Block) from the one the code and the numbers implement.
- **Fix:** Rebuild with the README's pdflatex/bibtex sequence and ship the matching PDF. Add a Makefile or CI step that fails when `numbers.tex` or the tables are newer than the PDF.

**M2. Per-window Z-basis error counts are probably not available in real time. (code verified; operational consequence is judgement)**
- **Where:** `detectors.dcs_fit` (ê_d^Z from `T.m[:,0,0]`), `dcs_residuals` (r2, decoy Z QBER), `qber_score`, `Band`.
- **Problem:** In this protocol Z is the key basis. Z errors become known only after error correction of the block, or by sacrificing bits.
- **Claims affected:**
  - "flags naive blinding in the first 10-second window" (abstract; l.484);
  - "withheld before the block closes" (Table 6; l.522–532);
  - Blind-lag's "public counts" (l.215), since `run_all.stream` uses `dcs_fit`, which needs Z errors.
- **Fix:** State the disclosure model explicitly. Evaluate one of:
  - an X-basis-only DCS (fit ê_d^X only, drop the Z-error residuals);
  - a variant that discloses a random Z sample, with the key-rate cost included.

  Report decision latency including error correction.

**M3. The withholding policy has no benign cost. (verified)**
- **Where:** Table 6, l.414–416.
- **Problems:**
  - `key_audit` counts a block as withheld if any alarm occurs between the true onset t0 and the block's end. The operator does not know t0.
  - Blocks start at t0 (`b0 = idx[0]`), not on a fixed grid.
  - `key_paired` is computed without alarms, so no honest-block cost exists anywhere in the results.
- **Size of the missing cost:** in the released seed JSONs, the DCS's first benign false alarm at d=1 comes at a median of about 1.4 h (range 0–12.9 h; 4–15 episodes/day). Under "stop key release at first alarm" an honest link would halt several times a day.
- **Misleading entries:** the Blind-cal, Blind-lag and Blind-sub "withheld" counts are false alarms (the paper admits this, l.528–530), yet they are tabulated as if they were a benefit.
- **Fix:** Define an explicit withhold/resume rule (e.g. withhold any block containing an alarm; resume after k clean windows) on a fixed block grid. Report honest blocks withheld per day and the throughput loss next to breached blocks released, as a curve over α.

**M4. The sequential detectors are calibrated per window despite serial dependence. (verified)**
- **Calibration:**
  - CUSUM and Block thresholds are per-window 1−10⁻³ quantiles of autocorrelated scores. For Block, 25 920 windows give only about 430 independent 10-minute blocks.
  - Thresholds vary 17.4–21.5 across seeds (DCS: 18.0–19.8).
  - Per-seed benign alarm counts range from 0 to 50.
  - Intervals are wide, e.g. Block at d=0 [0.01, 0.15]%, CUSUM at d=4 [0.09, 0.31]%.
- **Implementation:**
  - `CUSUM.score` never resets after an alarm, so an alarm becomes a latched state.
  - Block warm-up (score 0 for the first L−1 windows) is handled correctly.
  - L is fixed at 60 windows whatever the window length. In `sensitivity.py`, 1-second windows therefore average over 1 minute, not 10. This confounds the claim at l.554–555 that Block power "depends on counts per block".
- **Post-hoc status:** Block is post-hoc, but its Blind-thresh result (TPR 0.43) is headlined in the abstract.
- **Fix:**
  - Calibrate to a target in-control average run length (ARL₀) or episodes/day, using ≥30 simulated days or a block bootstrap.
  - Reset after each alarm and scale L with the window length Δ.
  - Report ARL₀ and the conditional detection delay as the primary metrics.
  - Confirm Block on fresh seeds, as was done for DCS+F.

**M5. The intensity-monitor precondition is fragile, and benign events outside the drift model are tested only for DCS+F. (verified by probe; 3 seeds, d=1, own calibration; script at `/tmp/claude-0/-home-user/219e0b5f-c4a5-5811-bbe4-b320546c97fb/scratchpad/ref3r2/probe.py`)**
- **Robust:** DCS, CUSUM and Block all stayed at or below 0.12% FPR under:
  - a ×5 dark-count step;
  - a 30-minute +3% misalignment excursion;
  - white polarisation jitter;
  - a −20% efficiency step;
  - a +2% step in Bob's X path.
- **Not robust:** a single 1% calibration step in the decoy-intensity monitor (second half of the day) caused:
  - DCS FPR of 6.5% (about 485 episodes/day);
  - CUSUM and Block latched in alarm (about 50% of windows, i.e. for the rest of the day).
- **Why it matters:** The main runs set the monitor bias σβ=0, and real photodiode tap monitors drift at about this level. The `exploratory.py` stress test evaluates only DCS and DCS+F.
- **Fix:**
  - Include a realistic monitor bias or step in the nominal model, or qualify the claims in the abstract and conclusion.
  - Run every detector through the stress set, and add to it:
    - detector gate or bias re-tuning;
    - laser re-lock;
    - missing or late windows;
    - compensation triggered by QBER rather than on a fixed period.
  - Propose an operational check of monitor health.

**M6. An obvious operational baseline is missing. (judgement)**
- **Missing baseline:** Level-based features with an adaptive reference, such as EWMA or rolling-median detrending, or a rolling or conformal per-link threshold. Operators already use this kind of rolling reference in practice.
- **Why it matters:** The paper shows IF-drift reaches TPR 1.00 on Blind-gain and Blind-sub at matched FPR (l.597–599), so its weakness is calibration, not discrimination. Without an adaptive baseline, the claim that drift-invariant refit features are what decide drift robustness (§8.2) is overstated.
- **Also:** The fixed 11% QBER rule is a strawman. Use QBER relative to its expected value.
- **Fix:** Add one detrended level detector and one online-recalibrated threshold.

---

### MINOR

1. **Latency (verified).** The "0.5 µs per window" figure (l.327) is a vectorised average over 8 640 windows (`run_all`, `dcs_latency_ms`). Report the streaming per-window cost, including the Python CUSUM loop.
2. **Drift realism (judgement).**
   - The misalignment is a fixed 1-hour sawtooth.
   - The d=0 calibration contains no compensation cycles at all, which commissioning data never achieves.
   - Afterpulses make up 97% of Y0.
   - Check the residuals' overdispersion against published field traces [10, 11].
3. **README (verified).**
   - It lists "14 settings"; the code runs 25.
   - It omits `exploratory.py S` (seeds 400–409).
   - It says one minute per seed; the paper says 92 s.
   - There is no `requirements.txt` with pinned versions.
   - `results/` contains `*.json.old` files and a `prev_block/` folder, which should be removed or documented.
4. **Reproducibility checks (verified).**
   - The 16 unit tests pass, but they are smoke tests that run in 0.08 s. Add tests for threshold calibration, Block warm-up and the withholding logic.
   - In a copy of the repository, `make_tables.py` regenerates `numbers.tex`, `numbers.json` and all 18 tables bit-identically, and `make_figs.py` runs.
   - Re-running seed 0 reproduces `seed_00.json` exactly in the FPRs. Only RF-residuals AUCs differ, at about 1e-7 or less, from multithreaded random forests.
5. **Naming (verified).** The code and JSON use `blind_nodark`; the paper uses "Blind-nobg". Harmonise them.
6. **Monitor-bias scaling (verified).** The monitor bias OU is not scaled by d (`qkdsim._intensities`). State this next to Table 1.
7. **Table 6.** Add a column showing honest blocks withheld in the paired copy, so that detection can be told apart from false alarms.
8. **§8.4.** The "8.1 episodes per day per link" figure should drive a network-level choice of α, expressed as ARL₀ or as per-link alarms per week.
9. **Table 6 (verified).** Its d=1 column has Block withholding all Blind-nobg blocks (0 released) but CUSUM releasing 7. The text says so correctly; also state the d=4 figures (26 and 7 released).

---


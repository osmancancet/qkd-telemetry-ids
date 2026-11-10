"""Aggregate per-seed JSON into numbers.json, LaTeX tables and prose macros.

Uncertainty: every mean over seeds carries a 95% BCa bootstrap interval over
seeds (B = 10000, the seed being the independent unit). Differences between detectors
are paired by seed and bootstrapped the same way. No hypothesis tests are reported.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES, TAB = ROOT / "results", ROOT / "manuscript" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

DETS = ["QBER-11%", "Band", "DCS", "DCS-CUSUM", "DCS-block", "IsoForest", "IsoForest-drift",
        "IsoForest-residuals", "RF-stationary", "RF-drift-rand", "RF-residuals", "DCS-X", "Band-roll"]
DLAB = {"QBER-11%": "QBER", "Band": "Band", "DCS": "DCS", "DCS-CUSUM": "CUSUM",
        "DCS-block": "Block",
        "IsoForest": "IF-stat", "IsoForest-drift": "IF-drift$^\\dagger$",
        "IsoForest-residuals": "IF-res", "RF-stationary": "RF-stat",
        "RF-drift-rand": "RF-DR$^\\dagger$", "RF-residuals": "RF-res$^\\dagger$",
        "DCS-X": "DCS-X", "Band-roll": "Band-roll$^\\dagger$"}
TAG = {"QBER-11%": "QBER", "Band": "Band", "DCS": "DCS", "DCS-CUSUM": "CUSUM",
       "DCS-block": "Block",
       "IsoForest": "IFstat", "IsoForest-drift": "IFdrift", "IsoForest-residuals": "IFres",
       "RF-stationary": "RFstat", "RF-drift-rand": "RFDR", "RF-residuals": "RFres",
       "DCS-X": "DCSX", "Band-roll": "Bandroll"}
SUPERVISED = ("RF-stationary", "RF-drift-rand", "RF-residuals")
ATT = ["ir:0.05", "ir:0.2", "pns:0.0", "blind_naive:0.0", "blind_gain:0.0", "blind_nodark:0.0",
       "blind_thresh:0.0", "blind_cal:0.0", "blind_cal_static:0.0", "blind_track:0.0", "blind_lag:0.0",
       "blind_sub:0.0", "blind_partial:0.1", "loss:1.0", "loss:3.0"]
INTERP = ("ir:0.2",)
IN_TRAIN = ("ir:0.05", "pns:0.0", "blind_naive:0.0")
ALAB = {"ir:0.05": "IR, $f=0.05$", "ir:0.2": "IR, $f=0.2$", "pns:0.0": "PNS",
        "blind_naive:0.0": "Blind-naive", "blind_gain:0.0": "Blind-gain",
        "blind_nodark:0.0": "Blind-nobg", "blind_thresh:0.0": "Blind-thresh",
        "blind_lag:0.0": "Blind-lag", "blind_sub:0.0": "Blind-sub",
        "blind_partial:0.1": "Blind-partial",
        "blind_cal:0.0": "Blind-cal",
        "blind_cal_static:0.0": "Blind-static", "blind_track:0.0": "Blind-track",
        "loss:1.0": "Loss +1 dB", "loss:3.0": "Loss +3 dB"}
ATAG = {"ir:0.05": "IrFive", "ir:0.2": "IrTwenty", "pns:0.0": "Pns", "blind_naive:0.0": "Naive",
        "blind_gain:0.0": "Gain", "blind_nodark:0.0": "Nodark", "blind_thresh:0.0": "Thresh",
        "blind_lag:0.0": "Lag", "blind_sub:0.0": "Sub", "blind_partial:0.1": "Partial",
        "blind_cal:0.0": "Cal",
        "blind_cal_static:0.0": "Static", "blind_track:0.0": "Track", "loss:1.0": "LossOne",
        "loss:3.0": "LossThree"}
DRIFTS = ["0.0", "0.25", "1.0", "2.0", "4.0"]
SENS_TAG = {"int_mon_sd_rel=0.005": "MonHalf", "int_mon_sd_rel=0.01": "MonOne",
            "int_mon_bias_sd_rel=0.002": "BiasTwo", "int_mon_bias_sd_rel=0.005": "BiasFive",
            "int_mon_bias_sd_rel=0.01": "BiasTen", "path_eff_sd_rel=0.0": "PathZero",
            "path_eff_sd_rel=0.01": "PathOne", "path_eff_sd_rel=0.02": "PathTwo",
            "pdl_sd_rel=0.0": "PdlZero", "pdl_sd_rel=0.005": "PdlHalf",
            "mis_rate_per_h=0.0025": "MisSlow", "nominal": "Nom", "window_s=1.0": "WinOne", "window_s=60.0": "WinSixty",
            "int_sd_rel=0.005": "SigHalf", "int_sd_rel=0.02": "SigTwo",
            "length_km=25.0": "LenTwentyFive", "length_km=75.0": "LenSeventyFive",
            "p_ap=0.0": "ApZero", "p_ap=0.05": "ApFive", "e_mis=(0.01, 0.01)": "MisEqual",
            "e_mis=(0.01, 0.02)": "MisWide", "int_drift_sd_rel=0.005": "IdHalf",
            "int_drift_sd_rel=0.02": "IdTwo", "int_monitor=False": "NoMon"}
STRESS_EV = (("afterpulse_x0.2_step", "Ap"), ("better_compensator", "Comp"), ("loss_step_7dB", "Loss"),
             ("dark_x5_step", "Dark"), ("efficiency_step_-20pct", "Eff"), ("laser_relock_+3pct", "Relock"),
             ("monitor_step_1pct_decoy", "Mon"))
STRESS_LAB = {"Ap": "Afterpulse probability $\\times0.2$", "Comp": "Better compensator ($e_d\\times0.45$)",
              "Loss": "Loss step +7\\,dB", "Dark": "Dark counts $\\times5$", "Eff": "Detector efficiency $-20\\%$",
              "Relock": "Laser re-lock, intensities +3\\% (monitored)", "Mon": "Decoy monitor calibration step +1\\%"}
DN = {"0.0": "DZero", "0.25": "DQuarter", "1.0": "DOne", "2.0": "DTwo", "4.0": "DFour"}
A = "0.001"
B = 10000


def boot(x):
    """Mean and 95% BCa bootstrap interval over seeds (fixed generator per call, so the
    interval does not depend on the order of calls)."""
    from scipy.stats import bootstrap
    x = np.asarray(x, float)
    if np.allclose(x, x[0]):
        return [float(x.mean()), float(x[0]), float(x[0])]
    r = bootstrap((x,), np.mean, n_resamples=B, method="BCa",
                  random_state=np.random.default_rng(12345))
    lo, hi = r.confidence_interval
    if not np.isfinite(lo) or not np.isfinite(hi):
        r = bootstrap((x,), np.mean, n_resamples=B, method="percentile",
                      random_state=np.random.default_rng(12345))
        lo, hi = r.confidence_interval
    return [float(x.mean()), float(lo), float(hi)]


def main():
    R = [json.load(open(f)) for f in sorted(glob.glob(str(RES / "seed_*.json")))]
    S = len(R)
    N = {"n_seeds": S, "runtime_s_mean": float(np.mean([r["runtime_s"] for r in R])),
         "dcs_latency_ms": float(np.mean([r["dcs_latency_ms"] for r in R])),
         "fpr": {}, "fpr_ctrl": {}, "episodes": {}, "auc": {}, "auc_stream": {}, "tpr": {},
         "tpr_ctrl": {}, "fpr_paired": {}, "delay": {}, "key": {}, "honest_key": {},
         "diff_fpr": {}, "ranges": {}, "thr_spread": {}}
    for d in DRIFTS:
        N["ranges"][d] = {
            k: [float(np.min([r["test"][d]["benign"][f"{k}_range"][0] for r in R])),
                float(np.max([r["test"][d]["benign"][f"{k}_range"][1] for r in R]))]
            for k in ("loss_db", "ed")}
        b = lambda dn, k: [r["test"][d]["benign"][dn][k][A] for r in R]
        N["fpr"][d] = {dn: boot(b(dn, "fpr")) for dn in DETS}
        N["fpr_ctrl"][d] = {dn: boot(b(dn, "fpr_ctrl")) for dn in DETS}
        N.setdefault("fpr_e4", {})[d] = {dn: boot([r["test"][d]["benign"][dn]["fpr"]["0.0001"] for r in R]) for dn in DETS}
        N.setdefault("tpr_e4", {})[d] = {a: {dn: boot([r["test"][d][a][dn]["tpr"]["0.0001"] for r in R]) for dn in DETS} for a in ATT}
        N["episodes"][d] = {dn: boot([r["test"][d]["benign"][dn]["episodes"] for r in R]) for dn in DETS}
        N["diff_fpr"][d] = {dn: boot(np.array(b("DCS", "fpr")) - np.array(b(dn, "fpr")))
                            for dn in DETS if dn != "DCS"}
        hk = [x for r in R for x in r["test"][d]["benign"]["key"]]
        N["honest_key"][d] = {
            "rate": boot([np.mean([x["rate"] for x in r["test"][d]["benign"]["key"]]) for r in R]),
            "frac_pos": float(np.mean([x["ell"] > 0 for x in hk])),
            "breach": int(sum(x["breach"] for x in hk)),
            "known_frac": float(sum(x["KE"] for x in hk) / sum(x["nZ"] for x in hk)),
            "bound_violations": int(sum(x["sZ1"] > x["sZ1_true"] for x in hk)),
            "bound_violations_nominal": int(sum(x["sZ1_nom"] > x["sZ1_true"] for x in hk)),
            "EZ": float(np.mean([x["EZ"] for x in hk])), "n_blocks": len(hk)}
        for k in ("auc", "auc_stream", "tpr", "tpr_ctrl", "fpr_paired", "delay"):
            N[k][d] = {}
        N["key"][d] = {}
        for a in ATT:
            g = lambda dn, k: [r["test"][d][a][dn][k] for r in R]
            N["auc"][d][a] = {dn: boot(g(dn, "auc")) for dn in DETS}
            N["auc_stream"][d][a] = {dn: boot(g(dn, "auc_stream")) for dn in DETS}
            N["tpr"][d][a] = {dn: boot([v[A] for v in g(dn, "tpr")]) for dn in DETS}
            N["tpr_ctrl"][d][a] = {dn: boot([v[A] for v in g(dn, "tpr_ctrl")]) for dn in DETS}
            N["fpr_paired"][d][a] = {dn: boot([v[A] for v in g(dn, "fpr_paired")]) for dn in DETS}
            N["delay"][d][a] = {dn: g(dn, "delay") for dn in DETS}
            kb = [x for r in R for x in r["test"][d][a]["key"]]
            pos = [x for x in kb if x["ell"] > 0]
            N["key"][d][a] = {
                "frac_pos": boot([np.mean([x["ell"] > 0 for x in r["test"][d][a]["key"]]) for r in R]),
                "breach": float(np.mean([x["breach"] for x in kb])),
                "breach_given_pos": float(np.mean([x["breach"] for x in pos])) if pos else float("nan"),
                "rate": float(np.mean([x["rate"] for x in kb])),
                "known_frac": float(sum(x["KE"] for x in kb) / sum(x["nZ"] for x in kb)),
                "n_blocks": len(kb), "n_pos": len(pos)}
    # additional quantities requested in review round 1
    N["fpr_alpha"] = {al: {d: {dn: boot([r["test"][d]["benign"][dn]["fpr"][al] for r in R]) for dn in DETS}
                           for d in DRIFTS} for al in ("0.01", "0.001", "0.0001")}
    N["tpr_oracle"] = {d: {a: {dn: boot([r["test"][d][a][dn]["tpr_oracle"] for r in R])
        for dn in DETS} for a in ATT} for d in DRIFTS}
    N["fpr_outside"] = {d: {a: {dn: boot([r["test"][d][a][dn]["fpr_outside"] for r in R])
                                for dn in ("DCS", "DCS-CUSUM", "DCS-block")} for a in ATT} for d in DRIFTS}
    N["auc_seed_range"] = {d: {a: {dn: [float(min(r["test"][d][a][dn]["auc"] for r in R)),
                                        float(max(r["test"][d][a][dn]["auc"] for r in R))]
                                   for dn in DETS} for a in ATT} for d in DRIFTS}
    N["first_fa"] = {d: {dn: [r["test"][d]["benign"][dn]["first_fa_window"] for r in R]
                         for dn in DETS} for d in DRIFTS}
    N["viol_per_seed"] = {d: {"nominal": [int(sum(x["sZ1_nom"] > x["sZ1_true"] for x in r["test"][d]["benign"]["key"])) for r in R],
                              "monitored": [int(sum(x["sZ1"] > x["sZ1_true"] for x in r["test"][d]["benign"]["key"])) for r in R],
                              "sX1": [int(sum(x["sX1"] > x["sX1_true"] for x in r["test"][d]["benign"]["key"])) for r in R],
                              "vX1": [int(sum(x["vX1"] < x["vX1_true"] for x in r["test"][d]["benign"]["key"])) for r in R]}
                          for d in DRIFTS}
    W = ("DCS", "DCS-CUSUM", "DCS-block", "RF-drift-rand", "DCS-X", "Band-roll")
    N["released"] = {}
    N["honest_withheld"] = {}
    # per-seed FPR spread, |AUC-0.5|, time to first false alarm
    N["fpr_seed"] = {d: {dn: {"max": float(max(r["test"][d]["benign"][dn]["fpr"][A] for r in R)),
                              "share_gt_2a": float(np.mean([r["test"][d]["benign"][dn]["fpr"][A] > 2 * float(A) for r in R]))}
                         for dn in DETS} for d in DRIFTS}
    N["auc_abs"] = {d: {a: {dn: boot([abs(r["test"][d][a][dn]["auc"] - 0.5) for r in R]) for dn in DETS}
                        for a in ATT} for d in DRIFTS}
    N["paired_key"] = {}
    for d in DRIFTS:
        N["released"][d], N["paired_key"][d] = {}, {}
        for a in ATT:
            kb = [x for r in R for x in r["test"][d][a]["key"]]
            br = [x for x in kb if x["breach"]]
            N["released"][d][a] = {"n_breach": len(br), **{
                dn: int(sum(not x["withheld"][dn] for x in br)) for dn in W}}
            hb = [y for r in R for y in r["test"][d][a]["key_paired"]]
            N["honest_withheld"].setdefault(d, {})[a] = {dn: float(np.mean([y["withheld"][dn] for y in hb])) for dn in W}
            # per-seed released share of breached blocks minus the null (honest-copy) release share
            per = []
            for r in R:
                kb_ = r["test"][d][a]["key"]; kp_ = r["test"][d][a]["key_paired"]
                if any(x["breach"] for x in kb_):
                    per.append({dn: np.mean([not x["withheld"][dn] for x in kb_ if x["breach"]])
                                - np.mean([not y["withheld"][dn] for y in kp_]) for dn in W})
            N["released"][d][a]["excess_withheld"] = ({dn: boot([-p[dn] for p in per]) for dn in W} if per else None)
            kp = [(x, y) for r in R for x, y in zip(r["test"][d][a]["key"], r["test"][d][a]["key_paired"])]
            N["paired_key"][d][a] = {
                "dell_rel": boot([sum(x["ell"] - y["ell"] for x, y in zip(r["test"][d][a]["key"], r["test"][d][a]["key_paired"]))
                              / max(sum(y["ell"] for y in r["test"][d][a]["key_paired"]), 1) for r in R]),
                "breach_paired": int(sum(y["breach"] for _, y in kp))}
    for dn in DETS:
        ts = [r["thresholds"][r["default_cal"][dn]][dn][A][0] for r in R]
        N["thr_spread"][dn] = [float(np.min(ts)), float(np.max(ts))]
    for name in ("sensitivity.json", "exploratory_dcs_p.json", "exploratory_dcs_f.json",
                 "exploratory_stress.json"):
        p = RES / name
        if p.exists():
            N[name.split(".")[0]] = json.load(open(p))
    (RES / "numbers.json").write_text(json.dumps(N, indent=1))
    write_tables(N)
    write_macros(N)


def pct(v, ci=True):
    s = f"{100*v[0]:.2f}"
    return s + (f" [{100*v[1]:.2f}, {100*v[2]:.2f}]" if ci else "")


def _hdr(cols, first="Detector"):
    return ["\\begin{tabular}{l" + "r" * len(cols) + "}", "\\hline",
            first + " & " + " & ".join(cols) + "\\\\", "\\hline"]


def write_tables(N):
    dcols = [f"$d={float(d):g}$" for d in DRIFTS]
    for key, fn in (("fpr", "fpr"), ("fpr_ctrl", "fpr_ctrl")):
        L = _hdr(dcols)
        for dn in DETS:
            L.append(DLAB[dn] + " & " + " & ".join(pct(N[key][d][dn]) for d in DRIFTS) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / f"{fn}.tex").write_text("\n".join(L))
    L = _hdr(dcols)
    for dn in DETS:
        L.append(DLAB[dn] + " & " + " & ".join(
            f"{N['episodes'][d][dn][0]:.1f} [{N['episodes'][d][dn][1]:.1f}, {N['episodes'][d][dn][2]:.1f}]"
            for d in DRIFTS) + "\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "episodes.tex").write_text("\n".join(L))

    def cell(d, a, x, k="auc"):
        v = N[k][d][a][x][0]
        s = f"{v:.2f}"
        if x in SUPERVISED and a in IN_TRAIN:
            s += "$^*$"
        return s

    def hw(d, a, x):
        v = N["auc"][d][a][x]
        return f"{v[0]:.2f}$_{{{max(v[0]-v[1], v[2]-v[0]):.2f}}}$".replace("_{0.", "_{.") + (
            "$^*$" if x in SUPERVISED and a in IN_TRAIN else "")

    for d in DRIFTS:
        L = ["\\begin{tabular}{l" + "c" * len(DETS) + "}", "\\hline",
             "Attack & " + " & ".join(DLAB[x] for x in DETS) + "\\\\", "\\hline"]
        for a in ATT:
            lab = ALAB[a] + ("$^\\ddagger$" if a in INTERP else "")
            L.append(lab + " & " + " & ".join(hw(d, a, x) for x in DETS) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / f"auc_d{d[0] if d != '0.25' else 'q'}.tex").write_text("\n".join(L))
    for d in ("1.0", "4.0"):
        L = ["\\begin{tabular}{l" + "c" * len(DETS) + "}", "\\hline",
             "Attack & " + " & ".join(DLAB[x] for x in DETS) + "\\\\", "\\hline",
             "\\emph{benign FPR} & " + " & ".join(f"{N['fpr'][d][x][0]:.3f}" for x in DETS) + "\\\\"]
        for a in ATT:
            L.append(ALAB[a] + " & " + " & ".join(cell(d, a, x, "tpr").replace(f"{N['tpr'][d][a][x][0]:.2f}", f"{N['tpr'][d][a][x][0]:.3f}") for x in DETS) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / f"tpr_d{d[0]}.tex").write_text("\n".join(L))
    d = "1.0"
    L = ["\\begin{tabular}{lrrrrr}", "\\hline",
         "Scenario & $P(\\ell>0)$ & Rate ($\\times10^{-4}$) & $K_E/n_Z$ & Breach & Breach $\\mid \\ell>0$ \\\\", "\\hline"]
    hk = N["honest_key"][d]
    L.append(f"Honest (24 h) & {hk['frac_pos']:.3f} & {1e4*hk['rate'][0]:.2f} & {hk['known_frac']:.3f} & {hk['breach']/hk['n_blocks']:.3f} & {hk['breach']/hk['n_blocks']:.3f}\\\\")
    for a in ATT:
        k = N["key"][d][a]
        bg = "--" if np.isnan(k["breach_given_pos"]) else f"{k['breach_given_pos']:.3f}"
        L.append(f"{ALAB[a]} & {k['frac_pos'][0]:.3f} & {1e4*k['rate']:.2f} & {k['known_frac']:.3f} & {k['breach']:.3f} & {bg}\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "key_d1.tex").write_text("\n".join(L))
    for al, nm in (("0.01", "a2"), ("0.0001", "a4")):
        L = _hdr(dcols)
        for dn in DETS:
            L.append(DLAB[dn] + " & " + " & ".join(pct(N["fpr_alpha"][al][d][dn]) for d in DRIFTS) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / f"fpr_{nm}.tex").write_text("\n".join(L))
    for d in ("1.0", "4.0"):
        L = ["\\begin{tabular}{l" + "c" * len(DETS) + "}", "\\hline",
             "Attack & " + " & ".join(DLAB[x] for x in DETS) + "\\\\", "\\hline"]
        for a in ATT:
            L.append(ALAB[a] + " & " + " & ".join(f"{N['tpr_oracle'][d][a][x][0]:.2f}" for x in DETS) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / f"tpr_oracle_d{d[0]}.tex").write_text("\n".join(L))
    # released breached blocks (block-wise withhold/resume policy), with the null cost
    W = ("DCS", "DCS-CUSUM", "DCS-block", "DCS-X", "RF-drift-rand")
    L = ["\\begin{tabular}{lr" + "r" * len(W) * 2 + "}", "\\hline",
         "& & \\multicolumn{%d}{c}{Breached blocks released} & \\multicolumn{%d}{c}{Honest blocks withheld (\\%%)}\\\\" % (len(W), len(W)),
         "Attack & Breached & " + " & ".join(DLAB[x].replace("$^\\dagger$", "") for x in W) * 1 + " & "
         + " & ".join(DLAB[x].replace("$^\\dagger$", "") for x in W) + "\\\\", "\\hline"]
    d = "1.0"
    for a in ATT:
        rr = N["released"][d][a]
        if not rr["n_breach"]:
            continue
        hw = N["honest_withheld"][d][a]
        L.append(ALAB[a] + f" & {rr['n_breach']} & " + " & ".join(str(rr[x]) for x in W) + " & "
                 + " & ".join(f"{100*hw[x]:.0f}" for x in W) + "\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "released.tex").write_text("\n".join(L))
    L = ["\\begin{tabular}{l" + "r" * len(DRIFTS) + "}", "\\hline",
         "Attack & " + " & ".join(dcols) + "\\\\", "\\hline"]
    for a in ATT:
        L.append(ALAB[a] + " & " + " & ".join(
            f"{100*N['paired_key'][d][a]['dell_rel'][0]:+.1f}" for d in DRIFTS) + "\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "paired_key.tex").write_text("\n".join(L))
    if "exploratory_stress" in N:
        St = N["exploratory_stress"]; ss = list(St)
        SD = ("DCS", "DCS-CUSUM", "DCS-block", "DCS-X", "DCS+F")
        L = ["\\begin{tabular}{lrrrrr}", "\\hline",
             "Event (second half of a 24-h stream, $d=1$) & DCS & CUSUM & Block & DCS-X & DCS+F\\\\", "\\hline"]
        for ev, tg in STRESS_EV:
            L.append(STRESS_LAB[tg] + " & " + " & ".join(f"{100*np.mean([St[s_][ev][n] for s_ in ss]):.2f}" for n in SD) + "\\\\")
        L.append("\\hline")
        L.append("Blind-sub, AUC & " + " & ".join(f"{np.mean([St[s_]['blind_sub'][n]['auc'] for s_ in ss]):.2f}" for n in SD) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / "stress.tex").write_text("\n".join(L))
    if "sensitivity" in N:
        Sx = N["sensitivity"]
        L = ["\\begin{tabular}{lrrrrrrrrrrrrrr}", "\\hline",
             "& \\multicolumn{4}{c}{FPR (\\%), $d=1$} & \\multicolumn{4}{c}{FPR (\\%), $d=4$} & "
             "\\multicolumn{4}{c}{DCS TPR, $d=1$} & Block TPR & Viol.\\\\",
             "Setting & DCS & CUSUM & Block & DCS-7 & DCS & CUSUM & Block & DCS-X & IR & Naive & Gain & Nobg & Thresh & nom.\\\\",
             "\\hline"]
        names = {"nominal": "Nominal", "window_s": "Window", "int_sd_rel": "$\\sigma_I$",
                 "length_km": "Fibre", "p_ap": "$p_{\\rm ap}$", "e_mis": "$(e_{\\rm mis}^Z, e_{\\rm mis}^X)$",
                 "int_drift_sd_rel": "Int. drift", "int_monitor": "Int. monitor",
                 "int_mon_sd_rel": "$\\sigma_M$", "int_mon_bias_sd_rel": "Monitor bias",
                 "path_eff_sd_rel": "Path eff.", "pdl_sd_rel": "PDL", "mis_rate_per_h": "Mis. rate"}
        for k, v in Sx.items():
            if k == "nominal":
                lab = names[k]
            else:
                f, val = k.split("=", 1)
                if f in ("int_sd_rel", "int_drift_sd_rel", "p_ap", "int_mon_sd_rel",
                         "int_mon_bias_sd_rel", "path_eff_sd_rel", "pdl_sd_rel"):
                    val = f"{100*float(val):g}\\%"
                elif f == "window_s":
                    val = f"{float(val):g} s"
                elif f == "length_km":
                    val = f"{float(val):g} km"
                elif f == "e_mis":
                    val = val.replace(" ", "")
                elif f == "int_monitor":
                    val = "off"
                elif f == "mis_rate_per_h":
                    val = f"{100*float(val):g}\\%/h"
                lab = f"{names[f]} {val}"
            fr = lambda dd, n: f"{100*np.mean([x[dd]['fpr'][n] for x in v]):.2f}"
            t = [np.mean([x["1.0"][a]["DCS"]["tpr"] for x in v]) for a in
                 ("ir:0.05", "blind_naive:0.0", "blind_gain:0.0", "blind_nodark:0.0")]
            tb = np.mean([x["1.0"]["blind_thresh:0.0"]["DCS-block"]["tpr"] for x in v])
            vn = sum(x["1.0"]["key"]["viol_nom"] for x in v)
            L.append(f"{lab} & " + " & ".join(fr("1.0", n) for n in ("DCS", "DCS-CUSUM", "DCS-block", "DCS-7"))
                     + " & " + " & ".join(fr("4.0", n) for n in ("DCS", "DCS-CUSUM", "DCS-block", "DCS-X"))
                     + " & " + " & ".join(f"{x:.2f}" for x in t) + f" & {tb:.2f} & {vn}\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / "sens.tex").write_text("\n".join(L))


def write_macros(N):
    """LaTeX macros for every number quoted in the prose (\\input{numbers.tex})."""
    M = {}
    for d in DRIFTS:
        D_ = DN[d]
        for x in DETS:
            t = TAG[x]
            v = N["fpr"][d][x]
            M[f"fpr{t}{D_}"], M[f"fprlo{t}{D_}"], M[f"fprhi{t}{D_}"] = (f"{100*z:.2f}" for z in v)
            M[f"fprctrl{t}{D_}"] = f"{100*N['fpr_ctrl'][d][x][0]:.2f}"
            M[f"epi{t}{D_}"] = f"{N['episodes'][d][x][0]:.1f}"
            M[f"alarmsEfour{t}{D_}"] = f"{8640*N['fpr_e4'][d][x][0]:.1f}"
            for a in ATT:
                M[f"tprEfour{ATAG[a]}{t}{D_}"] = f"{N['tpr_e4'][d][a][x][0]:.2f}"
            if x != "DCS":
                dv = N["diff_fpr"][d][x]
                M[f"dfpr{t}{D_}"] = f"{100*dv[0]:.2f}"
                M[f"dfprlo{t}{D_}"] = f"{100*dv[1]:.2f}"
                M[f"dfprhi{t}{D_}"] = f"{100*dv[2]:.2f}"
            for a in ATT:
                M[f"auc{ATAG[a]}{t}{D_}"] = f"{N['auc'][d][a][x][0]:.2f}"
                M[f"auclo{ATAG[a]}{t}{D_}"] = f"{N['auc'][d][a][x][1]:.2f}"
                M[f"auchi{ATAG[a]}{t}{D_}"] = f"{N['auc'][d][a][x][2]:.2f}"
                M[f"tpr{ATAG[a]}{t}{D_}"] = f"{N['tpr'][d][a][x][0]:.2f}"
        hk = N["honest_key"][d]
        M[f"keyrate{D_}"] = f"{1e4*hk['rate'][0]:.2f}"
        M[f"keypos{D_}"] = f"{100*hk['frac_pos']:.1f}"
        M[f"EZ{D_}"] = f"{100*hk['EZ']:.2f}"
        M[f"violNom{D_}"] = str(hk["bound_violations_nominal"])
        M[f"nBlocksHonest{D_}"] = f"{hk['n_blocks']:,}".replace(",", "\\,")
        M[f"lossmin{D_}"] = f"{N['ranges'][d]['loss_db'][0]:.1f}"
        M[f"lossmax{D_}"] = f"{N['ranges'][d]['loss_db'][1]:.1f}"
        M[f"edmax{D_}"] = f"{100*N['ranges'][d]['ed'][1]:.1f}"
        for a in ATT:
            k = N["key"][d][a]
            M[f"keypos{ATAG[a]}{D_}"] = f"{100*k['frac_pos'][0]:.1f}"
            M[f"breach{ATAG[a]}{D_}"] = f"{100*k['breach']:.1f}"
            M[f"known{ATAG[a]}{D_}"] = f"{100*k['known_frac']:.2f}"
            M[f"rate{ATAG[a]}{D_}"] = f"{1e4*k['rate']:.2f}"
    hk_all = [N["honest_key"][d] for d in DRIFTS]
    M["nBlocksHonest"] = str(sum(h["n_blocks"] for h in hk_all))
    M["boundViol"] = str(sum(h["bound_violations"] for h in hk_all))
    M["boundViolNom"] = str(sum(h["bound_violations_nominal"] for h in hk_all))
    M["honestKnownMax"] = f"{100*max(h['known_frac'] for h in hk_all):.2f}"
    M["nSeeds"] = str(N["n_seeds"])
    v = [N["fpr"][d]["DCS"][0] for d in DRIFTS]
    M["fprDCSMin"], M["fprDCSMax"] = f"{100*min(v):.2f}", f"{100*max(v):.2f}"
    v = [N["fpr"][d][x][0] for d in DRIFTS for x in ("DCS-CUSUM", "DCS-block")]
    M["fprSeqMin"], M["fprSeqMax"] = f"{100*min(v):.2f}", f"{100*max(v):.2f}"
    v = [N["fpr"][d][x][0] for d in DRIFTS for x in ("IsoForest-residuals", "RF-residuals", "DCS-X")]
    M["fprResMin"], M["fprResMax"] = f"{100*min(v):.2f}", f"{100*max(v):.2f}"
    for a, t_ in (("blind_lag:0.0", "Lag"), ("blind_cal:0.0", "Cal"), ("blind_sub:0.0", "Sub")):
        M[f"tprOrMax{t_}"] = f"{max(N['tpr_oracle'][d][a][x][0] for d in DRIFTS for x in DETS):.2f}"
        M[f"aucAbsMax{t_}"] = f"{max(N['auc_abs'][d][a][x][0] for d in DRIFTS for x in DETS):.2f}"
    M["runtime"] = f"{N['runtime_s_mean']:.0f}"
    M["dcsLatencyUs"] = f"{1e3*N['dcs_latency_ms']:.1f}"
    blind = [a for a in ATT if a.startswith("blind") and a != "blind_partial:0.1"]
    bg = [N["key"][d][a]["breach_given_pos"] for d in DRIFTS for a in blind
          if not np.isnan(N["key"][d][a]["breach_given_pos"])]
    M["breachGivenPosMin"] = f"{100*min(bg):.1f}"
    inm = [N["key"][d][a]["breach"] for d in DRIFTS for a in ATT if not a.startswith("blind")]
    M["breachInModelMax"] = f"{100*max(inm):.1f}"
    kn = [N["key"][d][a]["known_frac"] for d in DRIFTS for a in blind]
    M["blindKnownMin"], M["blindKnownMax"] = f"{100*min(kn):.2f}", f"{100*max(kn):.2f}"
    cal = [N["auc"][d]["blind_cal:0.0"][x][0] for d in DRIFTS for x in DETS]
    M["aucCalMin"], M["aucCalMax"] = f"{min(cal):.2f}", f"{max(cal):.2f}"
    th_ = [N["auc"][d]["blind_thresh:0.0"][x][0] for d in DRIFTS for x in DETS if x != "DCS-block"]
    M["aucThreshMin"], M["aucThreshMax"] = f"{min(th_):.2f}", f"{max(th_):.2f}"
    for a, t_ in (("blind_lag:0.0", "Lag"), ("blind_sub:0.0", "Sub")):
        v = [N["auc"][d][a][x][0] for d in DRIFTS for x in DETS]
        M[f"auc{t_}Min"], M[f"auc{t_}Max"] = f"{min(v):.2f}", f"{max(v):.2f}"
    calci = [N["auc"][d]["blind_cal:0.0"][x][1:] for d in DRIFTS for x in DETS]
    M["aucCalLoMin"] = f"{min(c[0] for c in calci):.2f}"
    M["aucCalHiMax"] = f"{max(c[1] for c in calci):.2f}"
    for a in ("blind_naive:0.0", "ir:0.05", "ir:0.2", "pns:0.0", "blind_gain:0.0"):
        for x in ("DCS", "DCS-CUSUM", "Band", "RF-drift-rand"):
            dl = [v for d in DRIFTS for v in N["delay"][d][a][x]]
            hit = [v for v in dl if v >= 0]
            M[f"delay{ATAG[a]}{TAG[x]}Max"] = str(max(hit)) if hit else "--"
            M[f"delay{ATAG[a]}{TAG[x]}Med"] = f"{np.median(hit):g}" if hit else "--"
            M[f"det{ATAG[a]}{TAG[x]}"] = f"{len(hit)}/{len(dl)}"
    for x in DETS:
        lo, hi = N["thr_spread"][x]
        M[f"thrlo{TAG[x]}"], M[f"thrhi{TAG[x]}"] = f"{lo:.3g}", f"{hi:.3g}"
    Sx = N.get("sensitivity")
    if Sx:
        for k, v in Sx.items():
            kk = SENS_TAG[k]
            M[f"sens{kk}FprOne"] = f"{100*np.mean([x['1.0']['fpr']['DCS'] for x in v]):.2f}"
            M[f"sens{kk}FprFour"] = f"{100*np.mean([x['4.0']['fpr']['DCS'] for x in v]):.2f}"
            M[f"sens{kk}CusumFprFour"] = f"{100*np.mean([x['4.0']['fpr']['DCS-CUSUM'] for x in v]):.2f}"
            for a in ("ir:0.05", "blind_naive:0.0", "blind_gain:0.0", "blind_nodark:0.0"):
                M[f"sens{kk}{ATAG[a]}"] = f"{np.mean([x['1.0'][a]['DCS']['tpr'] for x in v]):.2f}"
    for key, var, t in (("exploratory_dcs_p", "DCS+P", "P"), ("exploratory_dcs_f", "DCS+F", "F")):
        E = N.get(key)
        if not E:
            continue
        for d in DRIFTS:
            for n_, tt in (("DCS", "DCS"), (var, "Var")):
                M[f"ex{t}Fpr{tt}{DN[d]}"] = f"{100*np.mean([E[s][d]['benign'][n_] for s in E]):.2f}"
                for a in ATT:
                    M[f"ex{t}{ATAG[a]}{tt}{DN[d]}"] = f"{np.mean([E[s][d][a][n_]['auc'] for s in E]):.2f}"
                    M[f"ex{t}tpr{ATAG[a]}{tt}{DN[d]}"] = f"{np.mean([E[s][d][a][n_]['tpr'] for s in E]):.2f}"
    for d in DRIFTS:
        for x in DETS:
            for al, nm in (("0.01", "Etwo"), ("0.0001", "Efour")):
                M[f"fpr{nm}{TAG[x]}{DN[d]}"] = f"{100*N['fpr_alpha'][al][d][x][0]:.3f}"
            for a in ATT:
                M[f"tprOr{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{N['tpr_oracle'][d][a][x][0]:.2f}"
                lo, hi = N["auc_seed_range"][d][a][x]
                M[f"aucSmin{ATAG[a]}{TAG[x]}{DN[d]}"], M[f"aucSmax{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{lo:.2f}", f"{hi:.2f}"
                M[f"tprctrl{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{N['tpr_ctrl'][d][a][x][0]:.2f}"
        for a in ATT:
            M[f"dell{ATAG[a]}{DN[d]}"] = f"{100*N['paired_key'][d][a]['dell_rel'][0]:.1f}"
            rr = N["released"][d][a]
            M[f"nbreach{ATAG[a]}{DN[d]}"] = str(rr["n_breach"])
            for x in ("DCS", "DCS-CUSUM", "DCS-block", "RF-drift-rand", "DCS-X", "Band-roll"):
                M[f"rel{ATAG[a]}{TAG[x]}{DN[d]}"] = str(rr[x])
                M[f"hw{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{100*N['honest_withheld'][d][a][x]:.0f}"
                ex = rr.get("excess_withheld")
                if ex:
                    M[f"exw{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{100*ex[x][0]:.0f}"
                    M[f"exwlo{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{100*ex[x][1]:.0f}"
                    M[f"exwhi{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{100*ex[x][2]:.0f}"
            for x in ("DCS", "DCS-CUSUM", "DCS-block"):
                M[f"fprOut{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{100*N['fpr_outside'][d][a][x][0]:.2f}"
        vp = N["viol_per_seed"][d]
        M[f"violNomSeedMin{DN[d]}"], M[f"violNomSeedMax{DN[d]}"] = str(min(vp["nominal"])), str(max(vp["nominal"]))
        M[f"violSX{DN[d]}"], M[f"violVX{DN[d]}"] = str(sum(vp["sX1"])), str(sum(vp["vX1"]))
        for x in DETS:
            fs = N["fpr_seed"][d][x]
            M[f"fprSeedMax{TAG[x]}{DN[d]}"] = f"{100*fs['max']:.2f}"
            M[f"fprShareTwoA{TAG[x]}{DN[d]}"] = f"{100*fs['share_gt_2a']:.0f}"
            for a in ATT:
                M[f"aucAbs{ATAG[a]}{TAG[x]}{DN[d]}"] = f"{N['auc_abs'][d][a][x][0]:.2f}"
        for x in DETS:
            ff = N["first_fa"][d][x]
            M[f"nofa{TAG[x]}{DN[d]}"] = str(sum(v < 0 for v in ff))
            hit = [v for v in ff if v >= 0]
            M[f"firstfa{TAG[x]}{DN[d]}"] = f"{np.median(hit)/360:.1f}" if hit else "--"
    # number of (detector, drift) cells whose 95% interval excludes 0.5
    for a in ("blind_cal:0.0", "blind_thresh:0.0", "blind_lag:0.0"):
        cells = [N["auc"][d][a][x] for d in DRIFTS for x in DETS]
        M[f"nExcl{ATAG[a]}"] = str(sum(c[1] > 0.5 or c[2] < 0.5 for c in cells))
        M[f"nCells{ATAG[a]}"] = str(len(cells))
    for a in ("blind_thresh:0.0", "blind_gain:0.0", "blind_nodark:0.0", "blind_lag:0.0"):
        for x in ("DCS-block", "DCS-CUSUM"):
            dl = [v for d in DRIFTS for v in N["delay"][d][a][x]]
            hit = [v for v in dl if v >= 0]
            M[f"delay{ATAG[a]}{TAG[x]}Med"] = f"{np.median(hit):g}" if hit else "--"
            M[f"det{ATAG[a]}{TAG[x]}"] = f"{len(hit)}/{len(dl)}"
    for x in ("DCS", "DCS-CUSUM", "DCS-block"):
        dl = [v for d in DRIFTS for a in ATT for v in N["delay"][d][a][x] if v >= 60]
        M[f"nLate{TAG[x]}"] = str(len(dl))
    Sx = N.get("sensitivity")
    if Sx:
        for k, v in Sx.items():
            kk = SENS_TAG[k]
            for n_, t_ in (("DCS-block", "Block"), ("DCS-7", "Seven"), ("DCS-X", "DCSX")):
                M[f"sens{kk}{t_}FprOne"] = f"{100*np.mean([x['1.0']['fpr'][n_] for x in v]):.2f}"
                M[f"sens{kk}{t_}FprFour"] = f"{100*np.mean([x['4.0']['fpr'][n_] for x in v]):.2f}"
            M[f"sens{kk}CusumFprOne"] = f"{100*np.mean([x['1.0']['fpr']['DCS-CUSUM'] for x in v]):.2f}"
            M[f"sens{kk}ViolNom"] = str(sum(x["1.0"]["key"]["viol_nom"] for x in v))
            M[f"sens{kk}Viol"] = str(sum(x["1.0"]["key"]["viol"] for x in v))
            M[f"sens{kk}ViolPh"] = str(sum(x["1.0"]["key"]["viol_ph"] for x in v))
            M[f"sens{kk}BlockThresh"] = f"{np.mean([x['1.0']['blind_thresh:0.0']['DCS-block']['tpr'] for x in v]):.2f}"
            M[f"sens{kk}Thresh"] = f"{np.mean([x['1.0']['blind_thresh:0.0']['DCS']['tpr'] for x in v]):.2f}"
            M[f"sensNblocks"] = str(sum(x["1.0"]["key"]["n"] for x in v))
    St = N.get("exploratory_stress")
    if St:
        ss = list(St)
        SD = (("DCS", "DCS"), ("DCS-CUSUM", "CUSUM"), ("DCS-block", "Block"), ("DCS-X", "DCSX"), ("DCS+F", "F"))
        for ev, tg in STRESS_EV:
            for n_, t_ in SD:
                M[f"stress{tg}{t_}"] = f"{100*np.mean([St[s_][ev][n_] for s_ in ss]):.1f}"
        for n_, t_ in SD:
            M[f"stressSubAuc{t_}"] = f"{np.mean([St[s_]['blind_sub'][n_]['auc'] for s_ in ss]):.2f}"
            M[f"stressSubTpr{t_}"] = f"{np.mean([St[s_]['blind_sub'][n_]['tpr'] for s_ in ss]):.2f}"
        M["stressMarginYzero"] = f"{min(St[s_]['margin_d4']['y0_min_over_floor'] for s_ in ss):.2f}"
        M["stressMarginEd"] = f"{min(St[s_]['margin_d4']['ed_min_over_floor'] for s_ in ss):.2f}"
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in M.items()]
    (ROOT / "manuscript" / "numbers.tex").write_text("\n".join(lines) + "\n")
    return M


if __name__ == "__main__":
    main()

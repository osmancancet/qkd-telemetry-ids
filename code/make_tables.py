"""Aggregate per-seed JSON into numbers.json and LaTeX tables (manuscript/tables)."""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RES, TAB = ROOT / "results", ROOT / "manuscript" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

DETS = ["QBER-11%", "DCS", "IsoForest", "IsoForest-drift", "RF-stationary", "RF-drift-rand"]
DLAB = {"QBER-11%": "QBER$>$11\\%", "DCS": "DCS (ours)", "IsoForest": "IF-stat",
        "IsoForest-drift": "IF-drift", "RF-stationary": "RF-stat", "RF-drift-rand": "RF-DR"}
ATT = ["ir:0.05", "ir:0.2", "pns:0.0", "blind_naive:0.0", "blind_gain:0.0", "blind_nodark:0.0",
       "blind_cal:0.0", "blind_cal_static:0.0", "loss:1.0", "loss:3.0"]
ALAB = {"ir:0.05": "IR, $f=0.05$", "ir:0.2": "IR, $f=0.2$", "pns:0.0": "PNS",
        "blind_naive:0.0": "Blind-naive", "blind_gain:0.0": "Blind-gain",
        "blind_nodark:0.0": "Blind-nodark", "blind_cal:0.0": "Blind-cal",
        "blind_cal_static:0.0": "Blind-cal-static", "loss:1.0": "Loss +1 dB",
        "loss:3.0": "Loss +3 dB"}
DRIFTS = ["0.0", "1.0", "2.0", "4.0"]
A = "0.001"


def ci(x):
    x = np.asarray(x, float)
    m = x.mean()
    if len(x) < 2 or np.allclose(x, m):
        return m, 0.0
    return m, stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def holm(p):
    p = np.asarray(p); o = np.argsort(p); adj = np.empty_like(p); run = 0
    for i, j in enumerate(o):
        run = max(run, (len(p) - i) * p[j]); adj[j] = min(run, 1.0)
    return adj


def wilcoxon(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if np.allclose(a - b, 0):
        return 1.0
    return float(stats.wilcoxon(a, b, zero_method="zsplit", alternative="two-sided").pvalue)


def main():
    R = [json.load(open(f)) for f in sorted(glob.glob(str(RES / "seed_*.json")))]
    S = len(R)
    N = {"n_seeds": S, "runtime_s_mean": float(np.mean([r["runtime_s"] for r in R])),
         "fpr": {}, "fpr_dcal": {}, "auc": {}, "tpr": {}, "tpr_dcal": {}, "auc_flip": {},
         "delay": {}, "key": {}, "honest_key": {}, "wilcoxon": {}, "ranges": {}}
    for d in DRIFTS:
        N["ranges"][d] = {
            "loss_db": [float(np.min([r["test"][d]["benign"]["loss_db_range"][0] for r in R])),
                        float(np.max([r["test"][d]["benign"]["loss_db_range"][1] for r in R]))],
            "ed": [float(np.min([r["test"][d]["benign"]["ed_range"][0] for r in R])),
                   float(np.max([r["test"][d]["benign"]["ed_range"][1] for r in R]))]}
        for k in ("fpr", "fpr_dcal"):
            N[k][d] = {dn: ci([r["test"][d]["benign"][dn][k][A] for r in R]) for dn in DETS}
        hk = [b for r in R for b in r["test"][d]["benign"]["key"]]
        N["honest_key"][d] = {"rate_mean": float(np.mean([b["rate"] for b in hk])),
                              "frac_pos": float(np.mean([b["ell"] > 0 for b in hk])),
                              "breach": int(sum(b["breach"] for b in hk)),
                              "bound_violations": int(sum(b["sZ1"] > b["sZ1_true"] for b in hk)),
                              "n_blocks": len(hk)}
        for k in ("auc", "tpr", "tpr_dcal", "auc_flip", "delay"):
            N[k][d] = {}
        N["key"][d] = {}
        for a in ATT:
            for k in ("auc", "auc_flip"):
                N[k][d][a] = {dn: ci([r["test"][d][a][dn][k] for r in R]) for dn in DETS}
            for k in ("tpr", "tpr_dcal"):
                N[k][d][a] = {dn: ci([r["test"][d][a][dn][k][A] for r in R]) for dn in DETS}
            N["delay"][d][a] = {dn: [r["test"][d][a][dn]["delay"] for r in R] for dn in DETS}
            kb = [b for r in R for b in r["test"][d][a]["key"]]
            N["key"][d][a] = {"frac_pos": float(np.mean([b["ell"] > 0 for b in kb])),
                              "breach": float(np.mean([b["breach"] for b in kb])),
                              "rate_mean": float(np.mean([b["rate"] for b in kb])),
                              "known_frac": float(np.mean([b["KE"] / b["nZ"] for b in kb])),
                              "n_blocks": len(kb)}
        # paired tests DCS vs each other detector: benign FPR and AUC per attack
        W = {}
        others = [x for x in DETS if x != "DCS"]
        p = [wilcoxon([r["test"][d]["benign"]["DCS"]["fpr"][A] for r in R],
                      [r["test"][d]["benign"][o]["fpr"][A] for r in R]) for o in others]
        W["fpr"] = dict(zip(others, holm(p).tolist()))
        for a in ATT:
            p = [wilcoxon([r["test"][d][a]["DCS"]["auc"] for r in R],
                          [r["test"][d][a][o]["auc"] for r in R]) for o in others]
            W[a] = dict(zip(others, holm(p).tolist()))
        N["wilcoxon"][d] = W
    sens = RES / "sensitivity.json"
    if sens.exists():
        Sx = json.load(open(sens))
        N["sensitivity"] = {k: {"fpr": ci([r["fpr"] for r in v]),
                                **{a: ci([r[a]["tpr"] for r in v]) for a in v[0] if a != "fpr"},
                                **{a + "_auc": ci([r[a]["auc"] for r in v]) for a in v[0] if a != "fpr"}}
                            for k, v in Sx.items()}
    (RES / "numbers.json").write_text(json.dumps(N, indent=1))
    write_tables(N)


def f3(m, c=None, pct=False):
    if pct:
        return f"{100*m:.2f}" + (f"$\\pm${100*c:.2f}" if c else "")
    return f"{m:.3f}" + (f"$\\pm${c:.3f}" if c else "")


def write_tables(N):
    # Table: benign FPR (%) per drift scale
    L = ["\\begin{tabular}{l" + "r" * len(DRIFTS) + "}", "\\hline",
         "Detector & " + " & ".join(f"$d={float(d):g}$" for d in DRIFTS) + "\\\\", "\\hline"]
    for dn in DETS:
        L.append(DLAB[dn] + " & " + " & ".join(f3(*N["fpr"][d][dn], pct=True) for d in DRIFTS) + "\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "fpr.tex").write_text("\n".join(L))
    L = ["\\begin{tabular}{l" + "r" * len(DRIFTS) + "}", "\\hline",
         "Detector & " + " & ".join(f"$d={float(d):g}$" for d in DRIFTS) + "\\\\", "\\hline"]
    for dn in DETS:
        L.append(DLAB[dn] + " & " + " & ".join(f3(*N["fpr_dcal"][d][dn], pct=True) for d in DRIFTS) + "\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "fpr_dcal.tex").write_text("\n".join(L))
    # Table: AUC at drift 0 and 1
    for d in ("0.0", "1.0"):
        L = ["\\begin{tabular}{l" + "c" * len(DETS) + "}", "\\hline",
             "Attack & " + " & ".join(DLAB[x] for x in DETS) + "\\\\", "\\hline"]
        for a in ATT:
            L.append(ALAB[a] + " & " + " & ".join(f"{N['auc'][d][a][x][0]:.2f}" for x in DETS) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / f"auc_d{d[0]}.tex").write_text("\n".join(L))
    # Table: TPR at alpha with realised FPR (drift 1)
    d = "1.0"
    L = ["\\begin{tabular}{l" + "c" * len(DETS) + "}", "\\hline",
         "Attack & " + " & ".join(DLAB[x] for x in DETS) + "\\\\", "\\hline",
         "\\emph{benign FPR} & " + " & ".join(f"{N['fpr'][d][x][0]:.3f}" for x in DETS) + "\\\\"]
    for a in ATT:
        L.append(ALAB[a] + " & " + " & ".join(f"{N['tpr'][d][a][x][0]:.3f}" for x in DETS) + "\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "tpr_d1.tex").write_text("\n".join(L))
    # Table: key audit at drift 1
    L = ["\\begin{tabular}{lrrrr}", "\\hline",
         "Scenario & $P(\\ell>0)$ & Rate ($\\times10^{-3}$) & Eve-known fraction & Breach \\\\", "\\hline"]
    hk = N["honest_key"][d]
    L.append(f"Honest (24 h) & {hk['frac_pos']:.3f} & {1e3*hk['rate_mean']:.3f} & 0.000 & {hk['breach']/hk['n_blocks']:.3f}\\\\")
    for a in ATT:
        k = N["key"][d][a]
        L.append(f"{ALAB[a]} & {k['frac_pos']:.3f} & {1e3*k['rate_mean']:.3f} & {k['known_frac']:.3f} & {k['breach']:.3f}\\\\")
    L += ["\\hline", "\\end{tabular}"]
    (TAB / "key_d1.tex").write_text("\n".join(L))
    if "sensitivity" in N:
        Sx = N["sensitivity"]
        L = ["\\begin{tabular}{lccccc}", "\\hline",
             "Setting & FPR (\\%) & IR $f{=}0.05$ & Blind-naive & Blind-gain & Blind-nodark \\\\", "\\hline"]
        names = {"window_s": "Window", "int_sd_rel": "$\\sigma_I$", "length_km": "Fibre"}
        units = {"window_s": " s", "int_sd_rel": "", "length_km": " km"}
        for k, v in Sx.items():
            f, val = k.split("=")
            vv = f"{float(val):g}" if f != "int_sd_rel" else f"{100*float(val):g}\\%"
            L.append(f"{names[f]} {vv}{units[f]} & {100*v['fpr'][0]:.2f} & " +
                     " & ".join(f"{v[a][0]:.3f}" for a in ["ir:0.05", "blind_naive:0.0", "blind_gain:0.0", "blind_nodark:0.0"]) + "\\\\")
        L += ["\\hline", "\\end{tabular}"]
        (TAB / "sens.tex").write_text("\n".join(L))


if __name__ == "__main__":
    main()


def write_macros():
    """LaTeX macros for every number quoted in the prose (\\input{numbers.tex})."""
    N = json.loads((RES / "numbers.json").read_text())
    E = json.loads((RES / "exploratory_dcs_y0.json").read_text())
    tag = {"QBER-11%": "QBER", "DCS": "DCS", "IsoForest": "IFstat", "IsoForest-drift": "IFdrift",
           "RF-stationary": "RFstat", "RF-drift-rand": "RFDR"}
    dn = {"0.0": "Zero", "1.0": "One", "2.0": "Two", "4.0": "Four"}
    M = {}
    for d in DRIFTS:
        for x in DETS:
            M[f"fpr{tag[x]}D{dn[d]}"] = f"{100*N['fpr'][d][x][0]:.2f}"
            M[f"fprci{tag[x]}D{dn[d]}"] = f"{100*N['fpr'][d][x][1]:.2f}"
            M[f"fprdcal{tag[x]}D{dn[d]}"] = f"{100*N['fpr_dcal'][d][x][0]:.2f}"
        hk = N["honest_key"][d]
        M[f"keyrateD{dn[d]}"] = f"{1e3*hk['rate_mean']:.2f}"
        M[f"keyposD{dn[d]}"] = f"{100*hk['frac_pos']:.1f}"
        M[f"lossminD{dn[d]}"] = f"{N['ranges'][d]['loss_db'][0]:.1f}"
        M[f"lossmaxD{dn[d]}"] = f"{N['ranges'][d]['loss_db'][1]:.1f}"
        M[f"edmaxD{dn[d]}"] = f"{100*N['ranges'][d]['ed'][1]:.1f}"
    cal = [N["auc"][d]["blind_cal:0.0"][x][0] for d in DRIFTS for x in DETS]
    M["aucCalMin"], M["aucCalMax"] = f"{min(cal):.2f}", f"{max(cal):.2f}"
    M["nBlocksHonest"] = str(sum(N["honest_key"][d]["n_blocks"] for d in DRIFTS))
    M["boundViol"] = str(sum(N["honest_key"][d]["bound_violations"] for d in DRIFTS))
    M["nSeeds"] = str(N["n_seeds"])
    M["runtime"] = f"{N['runtime_s_mean']:.0f}"
    br = [N["key"][d][a]["breach"] for d in DRIFTS for a in ATT if a.startswith("blind")]
    M["breachBlindMin"] = f"{100*min(br):.1f}"
    inm = [N["key"][d][a]["breach"] for d in DRIFTS for a in ATT if not a.startswith("blind")]
    M["breachInModelMax"] = f"{100*max(inm):.1f}"
    M["irFiveKnown"] = f"{100*N['key']['1.0']['ir:0.05']['known_frac']:.1f}"
    M["irFiveRate"] = f"{1e3*N['key']['1.0']['ir:0.05']['rate_mean']:.2f}"
    M["blindNaiveRate"] = f"{1e3*N['key']['1.0']['blind_naive:0.0']['rate_mean']:.2f}"
    dl = [v for d in DRIFTS for v in N["delay"][d]["blind_naive:0.0"]["DCS"]]
    M["delayBlindNaiveMax"] = str(max(dl))
    dl = [v for v in N["delay"]["4.0"]["ir:0.05"]["DCS"]]
    M["delayIrFourMax"] = str(max(dl))
    for d in DRIFTS:
        M[f"tprDCSirFiveD{dn[d]}"] = f"{N['tpr'][d]['ir:0.05']['DCS'][0]:.2f}"
        for a, t in [("blind_nodark:0.0", "Nodark"), ("blind_cal_static:0.0", "Static")]:
            for x in DETS:
                M[f"auc{t}{tag[x]}D{dn[d]}"] = f"{N['auc'][d][a][x][0]:.2f}"
    M["aucInModelLearnedMin"] = f"{min(N['auc']['0.0'][a][x][0] for a in ('ir:0.05', 'ir:0.2', 'pns:0.0') for x in DETS[2:]):.2f}"
    pmax = max(max(N["wilcoxon"][d]["fpr"].values()) for d in ("1.0", "2.0", "4.0"))
    M["holmFprMax"] = f"{pmax:.4f}"
    Sx = N.get("sensitivity", {})
    for k, v in Sx.items():
        f, val = k.split("=")
        key = {"window_s": "win", "int_sd_rel": "sig", "length_km": "len"}[f] + \
            {"1.0": "One", "10.0": "Ten", "60.0": "Sixty", "0.005": "Half", "0.01": "Onep",
             "0.02": "Two", "25.0": "TwentyFive", "50.0": "Fifty", "75.0": "SeventyFive"}[val]
        M[f"sens{key}Fpr"] = f"{100*v['fpr'][0]:.2f}"
        M[f"sens{key}Ir"] = f"{v['ir:0.05'][0]:.2f}"
        M[f"sens{key}Gain"] = f"{v['blind_gain:0.0'][0]:.2f}"
    for d in DRIFTS:
        for n_, t in (("DCS", "DCS"), ("DCS+Y0", "DCSY")):
            M[f"exFpr{t}D{dn[d]}"] = f"{100*np.mean([E[s][d]['benign'][n_] for s in E]):.2f}"
            M[f"exNodark{t}D{dn[d]}"] = f"{np.mean([E[s][d]['blind_nodark:0.0'][n_]['auc'] for s in E]):.2f}"
            M[f"exIr{t}D{dn[d]}"] = f"{np.mean([E[s][d]['ir:0.05'][n_]['tpr'] for s in E]):.2f}"
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in M.items()]
    (ROOT / "manuscript" / "numbers.tex").write_text("\n".join(lines) + "\n")
    return M


if __name__ == "__main__":
    write_macros()

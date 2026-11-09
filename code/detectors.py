"""Window-level detectors on QKD telemetry.

All detectors map a Telemetry object to one score per window (higher = more
anomalous). Thresholds are set on benign calibration windows only, at the
(1 - alpha) empirical quantile, so every detector targets the same per-window
false-alarm rate under the calibration distribution.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest

from qkdsim import Telemetry


def features(T: Telemetry) -> np.ndarray:
    """9 features: log pooled gain per intensity, QBER per basis and intensity."""
    Q = T.n.sum(1) / T.N.sum(1)                          # (W,3)
    E = T.m / np.maximum(T.n, 1)                          # (W,2,3)
    return np.hstack([np.log(np.maximum(Q, 1e-12)), E.reshape(len(Q), 6)])


def qber_score(T: Telemetry) -> np.ndarray:
    """Key-basis (Z) QBER of the signal intensity."""
    return T.m[:, 0, 0] / np.maximum(T.n[:, 0, 0], 1)


def dcs_residuals(T: Telemetry, mu, e0=0.5, iters=4, with_y0=False) -> np.ndarray:
    """Decoy-consistency residuals.

    Plug-in estimates of (eta, Y0, e_d) per window come from the signal gain, the
    vacuum-like gain and the signal QBER. The residuals compare the remaining
    observations with what the honest channel model predicts for these estimates;
    slow drift in eta, Y0 or e_d is absorbed by the per-window fit.
    Returns (W, 6) residuals in units of their binomial standard deviation.
    """
    m1, m2, m3 = mu
    Np = T.N.sum(1); n = T.n.sum(1); mm = T.m.sum(1)
    Q = n / Np
    y0 = np.maximum(Q[:, 2] - 1e-3 * Q[:, 0], 1e-12)
    for _ in range(iters):
        eta = -np.log((1 - Q[:, 0]) / (1 - y0)) / m1
        y0 = np.clip((Q[:, 2] - (1 - np.exp(-eta * m3))) / np.exp(-eta * m3), 1e-12, None)
    E1Q1 = mm[:, 0] / Np[:, 0]
    ed = np.clip((E1Q1 - e0 * y0) / np.maximum(Q[:, 0] - y0, 1e-15), 0, 0.5)

    def gain(k):
        return 1 - (1 - y0) * np.exp(-eta * k)

    def errp(k):
        g = gain(k)
        return (e0 * y0 + ed * (g - y0)) / g

    r = []
    # decoy gain (pooled bases)
    p2 = gain(m2)
    r.append((n[:, 1] - Np[:, 1] * p2) / np.sqrt(Np[:, 1] * p2 * (1 - p2)))
    # decoy errors per basis, vacuum errors pooled, signal X-basis errors
    for b in (0, 1):
        pe = errp(m2)
        r.append((T.m[:, b, 1] - T.n[:, b, 1] * pe) / np.sqrt(np.maximum(T.n[:, b, 1] * pe * (1 - pe), 1e-9)))
    pe3 = errp(m3)
    r.append((mm[:, 2] - n[:, 2] * pe3) / np.sqrt(np.maximum(n[:, 2] * pe3 * (1 - pe3), 1e-9)))
    pe1 = errp(m1)
    r.append((T.m[:, 1, 0] - T.n[:, 1, 0] * pe1) / np.sqrt(np.maximum(T.n[:, 1, 0] * pe1 * (1 - pe1), 1e-9)))
    # signal Z/X detection balance (basis-dependent clicks)
    pz = T.N[:, 0, 0] / Np[:, 0]
    r.append((T.n[:, 0, 0] - n[:, 0] * pz) / np.sqrt(n[:, 0] * pz * (1 - pz)))
    if with_y0:
        # background-yield level itself (post-hoc variant DCS+Y0): blinded detectors
        # produce no dark counts, which the per-window refit would otherwise absorb
        r.append(y0)
    return np.column_stack(r)


class DCS:
    """Decoy-consistency statistic with empirical-null standardisation."""

    def __init__(self, mu, with_y0=False):
        self.mu = mu
        self.with_y0 = with_y0
        self.name = "DCS+Y0" if with_y0 else "DCS"

    def fit(self, T_cal: Telemetry):
        R = dcs_residuals(T_cal, self.mu, with_y0=self.with_y0)
        self.loc = np.median(R, 0)
        self.scale = 1.4826 * np.median(np.abs(R - self.loc), 0)
        return self

    def score(self, T: Telemetry):
        Z = (dcs_residuals(T, self.mu, with_y0=self.with_y0) - self.loc) / self.scale
        return np.sum(Z ** 2, 1)


class QBERThreshold:
    name = "QBER-11%"

    def fit(self, T_cal):
        return self

    def score(self, T):
        return qber_score(T)


class RF:
    """Supervised random forest on telemetry features (binary: attack or not)."""

    def __init__(self, name="RF", seed=0):
        self.name = name
        self.clf = RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                                          n_jobs=4, random_state=seed)

    def fit(self, X, y):
        self.clf.fit(X, y)
        return self

    def score(self, T):
        return self.clf.predict_proba(features(T))[:, 1]


class IF:
    """Isolation forest trained on benign windows only."""
    name = "IsoForest"

    def __init__(self, seed=0):
        self.clf = IsolationForest(n_estimators=200, random_state=seed, n_jobs=4)

    def fit(self, T_cal):
        X = features(T_cal)
        self.mu_, self.sd_ = X.mean(0), X.std(0) + 1e-12
        self.clf.fit((X - self.mu_) / self.sd_)
        return self

    def score(self, T):
        return -self.clf.score_samples((features(T) - self.mu_) / self.sd_)


def threshold(scores_cal: np.ndarray, alpha: float) -> float:
    return float(np.quantile(scores_cal, 1 - alpha, method="higher"))

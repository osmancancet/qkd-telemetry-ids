"""Window-level detectors on QKD telemetry.

All detectors map a Telemetry object to one score per window (higher = more
anomalous). Thresholds are set on benign calibration windows only, at the (1 - alpha)
quantile with randomised tie-breaking, so every detector targets the same per-window
false-alarm rate under its calibration distribution even when scores are discrete.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest

from qkdsim import Telemetry


def gains(T: Telemetry) -> np.ndarray:
    """Gain per intensity from all announced clicks, pooled over Alice's bases."""
    return T.n_all.sum(1) / T.N.sum(1)


def features(T: Telemetry) -> np.ndarray:
    """9 features: log gain per intensity, sifted QBER per basis and intensity."""
    Q = gains(T)
    E = T.m / np.maximum(T.n, 1)
    return np.hstack([np.log(np.maximum(Q, 1e-12)), E.reshape(len(Q), 6)])


def qber_score(T: Telemetry) -> np.ndarray:
    """Key-basis (Z) QBER of the signal intensity."""
    return T.m[:, 0, 0] / np.maximum(T.n[:, 0, 0], 1)


def _z(x, p, n):
    return (x - n * p) / np.sqrt(np.maximum(n * p * (1 - p), 1e-9))


def dcs_fit(T: Telemetry, e0=0.5, iters=6):
    """Per-window plug-in estimates of (eta, Y0, e_d^Z, e_d^X) from the signal gain, the
    vacuum-like gain and the signal QBER in each basis, using the monitored intensities.
    Y0 absorbs dark counts and afterpulses."""
    mu = T.mu_mon
    Q = gains(T)
    y0 = np.clip(Q[:, 2] - mu[:, 2] / mu[:, 0] * Q[:, 0], 1e-12, None)     # start: linear approx.
    for _ in range(iters):
        eta = -np.log((1 - Q[:, 0]) / (1 - y0)) / mu[:, 0]
        a = np.exp(-eta * mu[:, 2])
        y0 = np.clip((Q[:, 2] - (1 - a)) / a, 1e-12, None)
    eta = -np.log((1 - Q[:, 0]) / (1 - y0)) / mu[:, 0]
    E = T.m[:, :, 0] / np.maximum(T.n[:, :, 0], 1)                         # (W,2)
    ed = np.clip((E * Q[:, :1] - e0 * y0[:, None]) / np.maximum(Q[:, :1] - y0[:, None], 1e-15), 0, 0.5)
    return eta, y0, ed


def dcs_residuals(T: Telemetry, e0=0.5, with_y0=False, full=False,
                  p_bob=(0.9, 0.1), xonly=False) -> np.ndarray:
    """Decoy-consistency residuals, in units of their binomial standard deviation.

    After the per-window refit (eta, Y0, e_d per basis), the residuals compare the
    observations not used in the fit with the honest-model prediction:
      1 decoy gain; 2-3 decoy QBER in Z and X; 4 vacuum-like QBER (bases pooled).
    full=True adds three basis-balance residuals (ablation only; they assume that the
    efficiencies of Bob's basis paths and the transmission of Alice's bases are equal
    and stable): 5-6 sifting fraction of signal clicks in Z and X, 7 share of signal
    clicks on Alice's Z pulses.
    """
    eta, y0, ed = dcs_fit(T, e0)
    mu = T.mu_mon
    N = T.N.sum(1); na = T.n_all.sum(1)

    def gain(k):
        return 1 - (1 - y0) * np.exp(-eta * mu[:, k])

    def errp(k, b):
        g = gain(k)
        e = ed[:, b] if b is not None else ed.mean(1)
        return (e0 * y0 + e * (g - y0)) / g

    r = [_z(na[:, 1], gain(1), N[:, 1])]
    if xonly:   # only test-basis (X) errors, which are disclosed in real time
        r.append(_z(T.m[:, 1, 1], errp(1, 1), T.n[:, 1, 1]))
        r.append(_z(T.m[:, 1, 2], errp(2, 1), T.n[:, 1, 2]))
        return np.column_stack(r)
    for b in (0, 1):
        r.append(_z(T.m[:, b, 1], errp(1, b), T.n[:, b, 1]))
    r.append(_z(T.m[:, :, 2].sum(1), errp(2, None), T.n[:, :, 2].sum(1)))
    if full:
        for b, pb in ((0, p_bob[0]), (1, p_bob[1])):
            r.append(_z(T.n[:, b, 0], pb, T.n_all[:, b, 0]))
        pa = T.N[:, 0, 0] / N[:, 0]
        r.append(_z(T.n_all[:, 0, 0], pa, na[:, 0]))
    if with_y0:
        r.append(y0)
    return np.column_stack(r)


class _Robust:
    def _standardise_fit(self, R):
        self.loc = np.median(R, 0)
        self.scale = 1.4826 * np.median(np.abs(R - self.loc), 0)

    def _standardise(self, R):
        return (R - self.loc) / self.scale


class DCS(_Robust):
    """Decoy-consistency statistic with empirical-null (median/MAD) standardisation."""

    def __init__(self, with_y0=False, full=False, xonly=False):
        self.with_y0, self.full, self.xonly = with_y0, full, xonly
        self.name = ("DCS-7" if full else ("DCS+Y0" if with_y0 else ("DCS-X" if xonly else "DCS")))

    def _r(self, T):
        return dcs_residuals(T, with_y0=self.with_y0, full=self.full, xonly=self.xonly)

    def fit(self, T_cal: Telemetry):
        self._standardise_fit(self._r(T_cal))
        return self

    def z(self, T):
        return self._standardise(self._r(T))

    def score(self, T: Telemetry):
        return np.sum(self.z(T) ** 2, 1)


class CUSUM:
    """One-sided CUSUM on the standardised DCS score (Page 1954), k = 0.5."""
    name = "DCS-CUSUM"

    def __init__(self, k=0.5):
        self.k = k

    def fit(self, T_cal):
        self.dcs = DCS().fit(T_cal)
        s = self.dcs.score(T_cal)
        self.m, self.s = np.mean(s), np.std(s)
        return self

    def score(self, T):
        u = (self.dcs.score(T) - self.m) / self.s - self.k
        S = np.empty_like(u)
        acc = 0.0
        for i, v in enumerate(u):
            acc = max(0.0, acc + v)
            S[i] = acc
        return S


def _rolling_mean(Z, L):
    c = np.cumsum(np.vstack([np.zeros((1, Z.shape[1])), Z]), 0)
    idx = np.arange(1, len(Z) + 1)
    lo = np.maximum(idx - L, 0)
    return (c[idx] - c[lo]) / (idx - lo)[:, None]


class Block(_Robust):
    """Block-level DCS: mean of each standardised residual over the trailing L windows
    (one post-processing block), standardised again with median/MAD of the same block
    means on calibration data (which absorbs autocorrelation); score = sum of squares."""

    def __init__(self, L=60):
        self.L = L
        self.name = "DCS-block"

    def fit(self, T_cal):
        self.dcs = DCS().fit(T_cal)
        M = _rolling_mean(self.dcs.z(T_cal), self.L)[self.L:]
        self._standardise_fit(M)
        return self

    def score(self, T):
        s = np.sum(self._standardise(_rolling_mean(self.dcs.z(T), self.L)) ** 2, 1)
        s[:self.L - 1] = 0.0          # warm-up: no decision until one full block is seen
        return s


class Band(_Robust):
    """Two-sided physics band: signal Z QBER and decoy/signal gain ratio (per unit
    monitored intensity), each standardised on calibration data; score = max |z|."""
    name = "Band"

    @staticmethod
    def _x(T):
        Q = gains(T)
        r = (Q[:, 1] / T.mu_mon[:, 1]) / (Q[:, 0] / T.mu_mon[:, 0])
        return np.column_stack([qber_score(T), r])

    def fit(self, T_cal):
        self._standardise_fit(self._x(T_cal))
        return self

    def score(self, T):
        return np.max(np.abs(self._standardise(self._x(T))), 1)


class BandRoll(_Robust):
    """Band features with an adaptive reference: each feature minus its causal rolling
    median over the previous R windows (1 h), standardised on calibration data;
    score = max |z|. No decision during the first R windows."""
    name = "Band-roll"

    def __init__(self, R=360):
        self.R = R

    def _x(self, T):
        import pandas as pd
        X = pd.DataFrame(Band._x(T))
        ref = X.shift(1).rolling(self.R, min_periods=self.R).median()
        return (X - ref).to_numpy()

    def fit(self, T_cal):
        self._standardise_fit(self._x(T_cal)[self.R:])
        return self

    def score(self, T):
        s = np.max(np.abs(self._standardise(self._x(T))), 1)
        return np.nan_to_num(s, nan=0.0)


class QBERThreshold:
    name = "QBER-11%"

    def fit(self, T_cal):
        return self

    def score(self, T):
        return qber_score(T)


class RF:
    """Supervised random forest (binary: attack or not) on telemetry features or on
    standardised DCS residuals."""

    def __init__(self, name="RF", seed=0, on_residuals=False):
        self.name = name
        self.on_res = on_residuals
        self.clf = RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                                          n_jobs=4, random_state=seed)

    def X(self, T):
        return self.dcs.z(T) if self.on_res else features(T)

    def fit(self, T_train, T_benign_cal=None):
        if self.on_res:
            self.dcs = DCS().fit(T_benign_cal)
        self.clf.fit(self.X(T_train), T_train.label)
        return self

    def score(self, T):
        return self.clf.predict_proba(self.X(T))[:, 1]


class IF:
    """Isolation forest trained on benign windows only (features or DCS residuals)."""

    def __init__(self, name="IsoForest", seed=0, on_residuals=False):
        self.name = name
        self.on_res = on_residuals
        self.clf = IsolationForest(n_estimators=200, random_state=seed, n_jobs=4)

    def X(self, T):
        return self.dcs.z(T) if self.on_res else (features(T) - self.mu_) / self.sd_

    def fit(self, T_cal):
        if self.on_res:
            self.dcs = DCS().fit(T_cal)
        else:
            X = features(T_cal)
            self.mu_, self.sd_ = X.mean(0), X.std(0) + 1e-12
        self.clf.fit(self.X(T_cal))
        return self

    def score(self, T):
        return -self.clf.score_samples(self.X(T))


def threshold(scores_cal: np.ndarray, alpha: float):
    """Randomised level-alpha threshold (t, g): alarm if s > t, and with probability g
    if s == t, so that the calibration alarm rate equals alpha exactly."""
    s = np.asarray(scores_cal)
    t = float(np.quantile(s, 1 - alpha, method="higher"))
    above, at = np.mean(s > t), np.mean(s == t)
    g = float(np.clip((alpha - above) / at, 0, 1)) if at > 0 else 0.0
    return t, g


def alarm_prob(scores: np.ndarray, thr) -> np.ndarray:
    """Per-window alarm probability under a randomised threshold."""
    t, g = thr
    return (scores > t) + g * (scores == t)

"""Window-level telemetry simulator for three-intensity decoy-state BB84.

Each monitoring window carries, for every intensity k and basis b, the number of
pulses sent N_{b,k}, the number of detections n_{b,k} and the number of bit errors
m_{b,k}. Detections are sampled per photon-number component (n = 0, 1, >=2) so
that the true single-photon counts and Eve's knowledge are available for audit.

A scenario is fully described by three functions of photon number n:
  y_n  : probability that an n-photon pulse produces a click at Bob,
  e_n  : bit-error probability of such a click (after sifting),
  k_n  : fraction of such clicks whose sifted bit Eve knows exactly.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field

NMAX = 30  # photon-number truncation; Poisson tail beyond 30 is < 1e-30 for mu <= 0.6
_LOGFACT = np.cumsum(np.log(np.maximum(np.arange(NMAX + 1), 1)))


def poisson_pmf(mu: np.ndarray) -> np.ndarray:
    """P(n | mu) for n = 0..NMAX; mu broadcast over leading axes."""
    mu = np.asarray(mu, dtype=float)[..., None]
    n = np.arange(NMAX + 1)
    return np.exp(-mu + n * np.log(np.maximum(mu, 1e-300)) - _LOGFACT)


@dataclass
class Config:
    # source / protocol
    rate_hz: float = 1e8                # pulse rate
    window_s: float = 10.0              # monitoring window
    mu: tuple = (0.5, 0.1, 2e-4)        # signal, decoy, vacuum-like (Lim et al. 2014 conditions)
    p_mu: tuple = (0.7, 0.2, 0.1)
    p_z: float = 0.9                    # key basis Z, test basis X
    # channel and detectors (nominal)
    length_km: float = 50.0
    alpha_db_km: float = 0.2
    eta_bob: float = 0.10
    p_dc: float = 6e-7                  # per detector per gate
    e_mis: float = 0.01
    e0: float = 0.5
    # benign slow drift (scaled by `drift`); int_sd_rel is fast noise, always on
    drift: float = 1.0
    loss_diurnal_db: float = 0.3        # peak amplitude of 24 h loss cycle
    loss_ou_sd_db: float = 0.15         # stationary s.d. of OU loss component
    loss_ou_tau_s: float = 1800.0
    mis_rate_per_h: float = 0.01        # polarisation drift: misalignment growth per hour (absolute)
    mis_reset_h: float = 1.0            # active compensation period
    dc_diurnal_rel: float = 0.10        # relative dark-count swing (temperature)
    eff_ou_sd_rel: float = 0.02         # detector-efficiency OU s.d. (relative)
    int_sd_rel: float = 0.01            # per-window source-intensity fluctuation (relative)
    # stream
    n_windows: int = 8640               # 24 h of 10 s windows

    @property
    def n_pulses(self) -> float:
        return self.rate_hz * self.window_s

    @property
    def eta_nominal(self) -> float:
        return self.eta_bob * 10 ** (-self.alpha_db_km * self.length_km / 10)

    @property
    def y0_nominal(self) -> float:
        return 1 - (1 - self.p_dc) ** 2


def _ou(rng, n, dt, tau, sd):
    a = np.exp(-dt / tau)
    x = np.empty(n)
    x[0] = rng.normal(0, sd)
    eps = rng.normal(0, sd * np.sqrt(1 - a * a), n)
    for i in range(1, n):
        x[i] = a * x[i - 1] + eps[i]
    return x


def channel_state(cfg: Config, rng: np.random.Generator, t0_phase: float | None = None):
    """Per-window true channel parameters under benign drift.

    Returns dict of arrays (length n_windows): eta, y0, ed, intensity scale (3 cols).
    """
    n, dt, d = cfg.n_windows, cfg.window_s, cfg.drift
    t = np.arange(n) * dt
    phase = rng.uniform(0, 2 * np.pi) if t0_phase is None else t0_phase
    day = 2 * np.pi * t / 86400.0 + phase
    loss_db = (cfg.alpha_db_km * cfg.length_km
               + d * cfg.loss_diurnal_db * np.sin(day)
               + d * _ou(rng, n, dt, cfg.loss_ou_tau_s, cfg.loss_ou_sd_db))
    eff = cfg.eta_bob * (1 + d * _ou(rng, n, dt, 3600.0, cfg.eff_ou_sd_rel))
    eta = eff * 10 ** (-loss_db / 10)
    pdc = cfg.p_dc * (1 + d * cfg.dc_diurnal_rel * np.sin(day - 0.5))
    y0 = 1 - (1 - pdc) ** 2
    # polarisation drift: linear growth with random slope, reset by compensation
    hours = t / 3600.0
    k_reset = np.floor(hours / cfg.mis_reset_h).astype(int)
    slopes = rng.uniform(0.5, 1.5, k_reset.max() + 1) * cfg.mis_rate_per_h
    ed = cfg.e_mis + d * slopes[k_reset] * (hours - k_reset * cfg.mis_reset_h)
    iscale = 1 + rng.normal(0, cfg.int_sd_rel, (n, 3))   # fast i.i.d. noise, not scaled by drift
    return dict(eta=eta, y0=y0, ed=ed, iscale=iscale, loss_db=loss_db)


def static_state(cfg: Config, rng: np.random.Generator | None = None):
    """Nominal channel; per-window intensity noise is kept when rng is given."""
    n = cfg.n_windows
    isc = np.ones((n, 3)) if rng is None else 1 + rng.normal(0, cfg.int_sd_rel, (n, 3))
    return dict(eta=np.full(n, cfg.eta_nominal), y0=np.full(n, cfg.y0_nominal),
                ed=np.full(n, cfg.e_mis), iscale=isc,
                loss_db=np.full(n, cfg.alpha_db_km * cfg.length_km))


# ----------------------------------------------------------------------------
# Scenario yields. Each returns (y, e, know) arrays of shape (W, NMAX+1) given
# per-window channel parameters eta, y0, ed (shape (W,)).
# ----------------------------------------------------------------------------
def honest_yields(eta, y0, ed, e0=0.5):
    n = np.arange(NMAX + 1)
    eta, y0, ed = (np.asarray(v, float)[:, None] for v in (eta, y0, ed))
    y = 1 - (1 - y0) * (1 - eta) ** n
    err = (e0 * y0 + ed * (y - y0)) / y
    know = np.zeros_like(y)
    return y, err, know


def signal_gain(y, mu):
    """Expected gain for intensity mu (scalar or (W,)) given yields y (W, NMAX+1)."""
    return np.sum(poisson_pmf(mu) * y, axis=-1)


def attack_yields(kind: str, eta, y0, ed, cfg: Config, strength: float = 0.0,
                  eta_eve=None, y0_eve=None, ed_eve=None):
    """Yields for attack `kind`. Gains are matched to the honest signal gain where the
    attacker is assumed to do so (as in the cited attack descriptions).

    kinds: 'ir' (intercept-resend on fraction `strength`), 'pns' (photon-number
    splitting with lossless channel), 'blind_naive' (faked-state attack with threshold
    detector, no dark-count or error emulation), 'blind_cal' (faked-state attack with
    photon-number-resolving detector, calibrated to the honest yields of
    (eta_eve, y0_eve, ed_eve)), 'loss' (extra loss of `strength` dB, honest otherwise).
    """
    mu1 = cfg.mu[0]
    W = len(eta)
    n = np.arange(NMAX + 1)
    yh, eh, kh = honest_yields(eta, y0, ed, cfg.e0)
    q1 = signal_gain(yh, mu1)                      # honest signal gain per window
    y0c, edc = np.asarray(y0)[:, None], np.asarray(ed)[:, None]
    p0 = np.exp(-mu1)
    if kind == "loss":
        return honest_yields(np.asarray(eta) * 10 ** (-strength / 10), y0, ed, cfg.e0)
    if kind == "ir":
        f = strength
        # resend yield chosen so that the signal gain stays matched
        yE = ((q1 - p0 * y0c[:, 0]) / (1 - p0))[:, None]
        yE = np.broadcast_to(yE, (W, NMAX + 1))
        # error of an intercepted click: dark part random; signal part 1/4 + misalignment
        eE = (cfg.e0 * y0c + (yE - y0c) * (0.5 * edc + 0.5 * 0.5)) / yE
        kE = 0.5 * (yE - y0c) / yE                 # Eve knows the bit when her basis matched
        mask = (n >= 1)[None, :]
        y = np.where(mask, (1 - f) * yh + f * yE, yh)
        # click-weighted mixtures of error and knowledge
        e = np.where(mask, ((1 - f) * yh * eh + f * yE * eE) / y, eh)
        k = np.where(mask, (f * yE * kE) / y, 0.0)
        return y, e, k
    if kind == "pns":
        pm = 1 - p0 - mu1 * p0
        c = ((q1 - y0c[:, 0]) / (pm * cfg.eta_bob * (1 - y0c[:, 0])))[:, None]
        # where exact gain matching is infeasible (low loss), Eve forwards every
        # multi-photon pulse (c = 1) and the signal gain falls below the honest value
        c = np.minimum(c, 1.0)
        ymulti = y0c + (1 - y0c) * c * cfg.eta_bob
        y = np.where(n[None, :] >= 2, ymulti, y0c)
        e = (cfg.e0 * y0c + edc * (y - y0c)) / y
        k = (y - y0c) / y
        return y, e, k
    if kind == "blind_naive":
        s = (2 * q1 / (1 - p0))[:, None]
        y = np.where(n[None, :] >= 1, 0.5 * s, 0.0)
        y = np.maximum(y, 1e-300)
        e = np.zeros_like(y)
        k = np.where(n[None, :] >= 1, 1.0, 0.0)
        return y, e, k
    if kind == "blind_gain":
        # faked-state attack that reproduces every gain (PNR detector) but adds no errors
        y = yh.copy()
        return y, np.zeros_like(y), np.ones_like(y)
    if kind == "blind_nodark":
        # reproduces signal-photon yields and misalignment errors but, with blinded
        # detectors, emits no dark-count clicks (y_0 -> 0)
        y = np.maximum(yh - y0c * (1 - np.asarray(eta)[:, None]) ** n, 1e-300)
        y[:, 0] = 1e-300
        e = np.where(n[None, :] >= 1, edc, 0.0) * np.ones_like(y)
        return y, e, np.ones_like(y)
    if kind == "blind_cal":
        eta_e = eta if eta_eve is None else eta_eve
        y0_e = y0 if y0_eve is None else y0_eve
        ed_e = ed if ed_eve is None else ed_eve
        y, e, _ = honest_yields(eta_e, y0_e, ed_e, cfg.e0)
        if np.any(2 * y > 1):
            raise ValueError("calibrated blinding needs 2*y_n <= 1")
        return y, e, np.ones_like(y)
    raise ValueError(kind)


# ----------------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------------
@dataclass
class Telemetry:
    N: np.ndarray        # (W, 2, 3) pulses sent per basis (Z, X) and intensity
    n: np.ndarray        # detections
    m: np.ndarray        # errors
    n1: np.ndarray       # true single-photon detections (audit only)
    known: np.ndarray    # detections whose bit Eve knows (audit only)
    label: np.ndarray    # (W,) 1 if the window is under attack


def sample(cfg: Config, rng: np.random.Generator, state: dict, y, e, k,
           label=None) -> Telemetry:
    """Draw window counts. y, e, k have shape (W, NMAX+1)."""
    W = len(state["eta"])
    Np = cfg.n_pulses
    pb = np.array([cfg.p_z, 1 - cfg.p_z])
    pk = np.array(cfg.p_mu)
    N = rng.multinomial(int(Np), np.outer(pb, pk).ravel(), size=W).reshape(W, 2, 3).astype(float)
    mu_true = np.array(cfg.mu)[None, :] * state["iscale"]          # (W, 3)
    P = poisson_pmf(mu_true)                                       # (W, 3, NMAX+1)
    comp = [slice(0, 1), slice(1, 2), slice(2, None)]
    n = np.zeros((W, 2, 3)); m = np.zeros((W, 2, 3))
    n1 = np.zeros((W, 2, 3)); kn = np.zeros((W, 2, 3))
    for c in comp:
        Pc = P[:, :, c]                                            # (W,3,nc)
        pc = Pc.sum(-1)
        yc = np.einsum("wkn,wn->wk", Pc, y[:, c]) / np.maximum(pc, 1e-300)
        ec = np.einsum("wkn,wn->wk", Pc, (y * e)[:, c]) / np.maximum(pc * yc, 1e-300)
        kc = np.einsum("wkn,wn->wk", Pc, (y * k)[:, c]) / np.maximum(pc * yc, 1e-300)
        prob = np.clip(pc * yc, 0, 1)[:, None, :]                  # (W,1,3)
        det = rng.binomial(N.astype(np.int64), np.broadcast_to(prob, N.shape)).astype(float)
        err = rng.binomial(det.astype(np.int64), np.broadcast_to(np.clip(ec, 0, 1)[:, None, :], N.shape))
        kno = rng.binomial(det.astype(np.int64), np.broadcast_to(np.clip(kc, 0, 1)[:, None, :], N.shape))
        n += det; m += err; kn += kno
        if c == comp[1]:
            n1 += det
    lab = np.zeros(W, int) if label is None else np.asarray(label, int)
    return Telemetry(N=N, n=n, m=m, n1=n1, known=kn, label=lab)


def splice(base: Telemetry, att: Telemetry, mask: np.ndarray) -> Telemetry:
    """Windows where mask is True come from `att`."""
    mk = mask[:, None, None]
    return Telemetry(N=np.where(mk, att.N, base.N), n=np.where(mk, att.n, base.n),
                     m=np.where(mk, att.m, base.m), n1=np.where(mk, att.n1, base.n1),
                     known=np.where(mk, att.known, base.known), label=mask.astype(int))

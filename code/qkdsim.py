"""Window-level telemetry simulator for three-intensity decoy-state BB84.

Each monitoring window carries, for every intensity k and basis b, the number of
pulses sent N_{b,k}, the number of detections n_{b,k} and the number of bit errors
m_{b,k}. Detections are sampled per photon-number component (n = 0, 1, >=2) so
that the true single-photon counts and Eve's knowledge are available for audit.

Alice picks basis Z with probability p_z and Bob independently with probability
p_z_bob; a click is sifted when the bases agree. Bob announces every click, so the
window also carries the number of all clicks per intensity and Alice basis.

A scenario is described by three functions of photon number n, assumed i.i.d. over
pulses and identical in both of Bob's bases:
  y_n    : probability that an n-photon pulse produces a click at Bob,
  e_{b,n}: bit-error probability of a sifted click in basis b,
  k_n    : fraction of such sifted clicks whose key bit Eve knows exactly.
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
    p_z: float = 0.9                    # Alice: key basis Z, test basis X
    p_z_bob: float = 0.9                # Bob's basis choice (sifting factor p_z * p_z_bob for Z)
    # channel and detectors (nominal)
    length_km: float = 50.0
    alpha_db_km: float = 0.2
    eta_bob: float = 0.10
    p_dc: float = 6e-7                  # per detector per gate
    e_mis: tuple = (0.010, 0.012)       # misalignment error in Z and X (basis-dependent)
    e0: float = 0.5
    p_ap: float = 0.01                  # afterpulse probability per click (spread over later gates)
    # benign slow drift (scaled by `drift`); int_sd_rel is fast noise, always on
    drift: float = 1.0
    loss_diurnal_db: float = 0.3        # peak amplitude of 24 h loss cycle
    loss_ou_sd_db: float = 0.15         # stationary s.d. of OU loss component
    loss_ou_tau_s: float = 1800.0
    mis_rate_per_h: float = 0.01        # polarisation drift: misalignment growth per hour (absolute)
    mis_reset_h: float = 1.0            # active compensation period
    dc_diurnal_rel: float = 0.10        # relative dark-count and afterpulse swing (temperature)
    eff_ou_sd_rel: float = 0.02         # detector-efficiency OU s.d. (relative)
    int_drift_sd_rel: float = 0.01      # slow OU drift of each intensity (relative), tau 2 h
    int_sd_rel: float = 0.01            # per-window source-intensity fluctuation (relative)
    int_mon_sd_rel: float = 0.002       # relative error of Alice's per-window intensity monitor
    int_monitor: bool = True            # detectors see monitored intensities (else nominal)
    int_mon_bias_sd_rel: float = 0.0    # slow OU bias of the monitor per intensity (relative), tau 2 h
    path_eff_sd_rel: float = 0.005      # Bob: relative efficiency of each basis path, OU tau 1 h
    pdl_sd_rel: float = 0.0025          # Alice-basis-dependent transmission (PDL), OU tau 30 min
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

    @property
    def p_bob(self) -> np.ndarray:
        return np.array([self.p_z_bob, 1 - self.p_z_bob])


def _ou(rng, n, dt, tau, sd):
    a = np.exp(-dt / tau)
    x = np.empty(n)
    x[0] = rng.normal(0, sd)
    eps = rng.normal(0, sd * np.sqrt(1 - a * a), n)
    for i in range(1, n):
        x[i] = a * x[i - 1] + eps[i]
    return x


def _intensities(cfg, rng, n, d):
    slow = np.column_stack([d * _ou(rng, n, cfg.window_s, 7200.0, cfg.int_drift_sd_rel)
                            for _ in range(3)])
    iscale = (1 + slow) * (1 + rng.normal(0, cfg.int_sd_rel, (n, 3)))
    bias = np.column_stack([_ou(rng, n, cfg.window_s, 7200.0, cfg.int_mon_bias_sd_rel)
                            for _ in range(3)]) if cfg.int_mon_bias_sd_rel > 0 else 0.0
    imon = iscale * (1 + bias) * (1 + rng.normal(0, cfg.int_mon_sd_rel, (n, 3)))
    return iscale, imon


def channel_state(cfg: Config, rng: np.random.Generator, t0_phase: float | None = None):
    """Per-window true channel parameters under benign drift.

    Returns dict of arrays (length n_windows): eta, y0, ed (W,2), iscale and imon (W,3),
    pap (afterpulse probability), fibre loss in dB.
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
    temp = 1 + d * cfg.dc_diurnal_rel * np.sin(day - 0.5)
    y0 = 1 - (1 - cfg.p_dc * temp) ** 2
    pap = cfg.p_ap * temp
    # polarisation drift: linear growth with a random slope per basis, reset by compensation
    hours = t / 3600.0
    k_reset = np.floor(hours / cfg.mis_reset_h).astype(int)
    ed = np.empty((n, 2))
    for b in range(2):
        slopes = rng.uniform(0.5, 1.5, k_reset.max() + 1) * cfg.mis_rate_per_h
        ed[:, b] = cfg.e_mis[b] + d * slopes[k_reset] * (hours - k_reset * cfg.mis_reset_h)
    iscale, imon = _intensities(cfg, rng, n, d)
    # basis-dependent efficiencies: Bob's two basis paths, and Alice-basis transmission
    path = 1 + d * np.column_stack([_ou(rng, n, dt, 3600.0, cfg.path_eff_sd_rel) for _ in range(2)])
    abas = 1 + d * np.column_stack([_ou(rng, n, dt, 1800.0, cfg.pdl_sd_rel) for _ in range(2)])
    return dict(eta=eta, y0=y0, ed=ed, iscale=iscale, imon=imon, pap=pap, loss_db=loss_db,
                path=path, abas=abas)


def static_state(cfg: Config, rng: np.random.Generator | None = None):
    """Nominal channel; per-window intensity noise is kept when rng is given."""
    n = cfg.n_windows
    if rng is None:
        isc = imon = np.ones((n, 3))
    else:
        isc, imon = _intensities(cfg, rng, n, 0.0)
    return dict(eta=np.full(n, cfg.eta_nominal), y0=np.full(n, cfg.y0_nominal),
                ed=np.tile(np.array(cfg.e_mis, float), (n, 1)), iscale=isc, imon=imon,
                pap=np.full(n, cfg.p_ap), loss_db=np.full(n, cfg.alpha_db_km * cfg.length_km),
                path=np.ones((n, 2)), abas=np.ones((n, 2)))


# ----------------------------------------------------------------------------
# Scenario yields. Each returns (y, e, know): y and know of shape (W, NMAX+1), e of
# shape (W, 2, NMAX+1), given per-window eta, y0 (W,) and ed (W, 2).
# ----------------------------------------------------------------------------
def honest_yields(eta, y0, ed, e0=0.5):
    n = np.arange(NMAX + 1)
    eta, y0 = (np.asarray(v, float)[:, None] for v in (eta, y0))
    ed = np.asarray(ed, float)
    if ed.ndim == 1:
        ed = np.column_stack([ed, ed])
    y = 1 - (1 - y0) * (1 - eta) ** n
    err = (e0 * y0[:, None] + ed[:, :, None] * (y - y0)[:, None, :]) / y[:, None, :]
    know = np.zeros_like(y)
    return y, err, know


def signal_gain(y, mu):
    """Expected gain for intensity mu (scalar or (W,)) given yields y (W, NMAX+1)."""
    return np.sum(poisson_pmf(mu) * y, axis=-1)


TINY = 1e-300


def attack_yields(kind: str, eta, y0, ed, cfg: Config, strength: float = 0.0,
                  eta_eve=None, y0_eve=None, ed_eve=None):
    """Yields for attack `kind`. Gains are matched to the honest signal gain where the
    attacker is assumed to do so (as in the cited attack descriptions).

    kinds: 'ir' (intercept-resend on fraction `strength`, ideal detector at Eve, one
    resend yield for all n >= 1), 'pns' (photon-number splitting over a lossless channel;
    Eve knows eta_bob), 'blind_naive' (faked states from a threshold detector, no dark
    count or error emulation), 'blind_gain' (faked states that reproduce every yield but
    add no errors), 'blind_nodark' (reproduces yields and errors of n >= 1 but injects no
    dark clicks), 'blind_thresh' (faked states from Eve's own threshold detector behind
    an attenuator, see below), 'blind_cal' (faked states calibrated to the honest yields and errors of
    (eta_eve, y0_eve, ed_eve)), 'loss' (extra loss of `strength` dB, honest otherwise).

    Faked-state attacks: Eve measures in Z or X with probability 1/2 and resends with a
    probability chosen so that Bob's click probability in either basis is y_n; this needs
    y_n <= 1/2. A click she injects on a vacuum pulse carries no information on Alice's
    bit: its error probability is 1/2 and Eve's knowledge of the key bit is 0.
    """
    mu1 = cfg.mu[0]
    W = len(eta)
    n = np.arange(NMAX + 1)
    ed = np.asarray(ed, float)
    if ed.ndim == 1:
        ed = np.column_stack([ed, ed])
    yh, eh, kh = honest_yields(eta, y0, ed, cfg.e0)
    q1 = signal_gain(yh, mu1)                      # honest signal gain per window
    y0c = np.asarray(y0)[:, None]
    edb = ed[:, :, None]                           # (W,2,1)
    p0 = np.exp(-mu1)
    vac = (n == 0)[None, :]
    if kind == "loss":
        return honest_yields(np.asarray(eta) * 10 ** (-strength / 10), y0, ed, cfg.e0)
    if kind == "ir":
        f = strength
        yE = np.broadcast_to(((q1 - p0 * y0c[:, 0]) / (1 - p0))[:, None], (W, NMAX + 1))
        # error of an intercepted click: dark part random; signal part 1/4 + misalignment/2
        eE = (cfg.e0 * y0c[:, None, :] + (yE - y0c)[:, None, :] * (0.5 * edb + 0.25)) / yE[:, None, :]
        kE = 0.5 * (yE - y0c) / yE                 # Eve knows the bit when her basis matched
        y = np.where(vac, yh, (1 - f) * yh + f * yE)
        e = np.where(vac[:, None, :], eh, ((1 - f) * (yh * eh.transpose(1, 0, 2)) +
                                          f * (yE * eE.transpose(1, 0, 2))).transpose(1, 0, 2) / y[:, None, :])
        k = np.where(vac, 0.0, f * yE * kE / y)
        return y, e, k
    if kind == "pns":
        pm = 1 - p0 - mu1 * p0
        c = ((q1 - y0c[:, 0]) / (pm * cfg.eta_bob * (1 - y0c[:, 0])))[:, None]
        # where exact gain matching is infeasible (low loss), Eve forwards every
        # multi-photon pulse (c = 1) and the signal gain falls below the honest value
        c = np.minimum(c, 1.0)
        ymulti = y0c + (1 - y0c) * c * cfg.eta_bob
        y = np.where(n[None, :] >= 2, ymulti, y0c)
        e = (cfg.e0 * y0c[:, None, :] + edb * (y - y0c)[:, None, :]) / y[:, None, :]
        k = (y - y0c) / y
        return y, e, k
    know = np.where(vac, 0.0, 1.0) * np.ones((W, 1))
    if kind == "blind_naive":
        s = (2 * q1 / (1 - p0))[:, None]
        y = np.where(vac, TINY, 0.5 * s)
        e = np.zeros((W, 2, NMAX + 1))
        return y, e, know
    if kind == "blind_gain":
        e = np.where(vac[:, None, :], 0.5, 0.0) * np.ones((W, 2, 1))
        return yh.copy(), e, know
    if kind == "blind_nodark":
        y = np.maximum(yh - y0c * (1 - np.asarray(eta)[:, None]) ** n, TINY)
        y[:, 0] = TINY
        e = np.where(vac[:, None, :], 0.5, edb)
        return y, e, know
    if kind == "blind_thresh":
        # faked states driven by Eve's own threshold detector (efficiency eta_E, random
        # basis): she forwards every click, and on pulses where her detector stays silent
        # injects a random-bit click with probability 2*Y0. Bob's yield in either basis is
        # y_n = Y0 + (1/2 - Y0) * (1 - (1 - eta_E)^n); eta_E is set to match the signal gain.
        # Forwarded clicks carry the misalignment error and are known to Eve.
        y0v = np.asarray(y0, float)
        lo, hi = np.full(W, 1e-6), np.full(W, 0.5)
        for _ in range(60):                         # bisection on eta_E per window
            mid = 0.5 * (lo + hi)
            ym = y0v[:, None] + (0.5 - y0v[:, None]) * (1 - (1 - mid[:, None]) ** n)
            g = signal_gain(ym, mu1)
            lo = np.where(g < q1, mid, lo); hi = np.where(g >= q1, mid, hi)
        etaE = 0.5 * (lo + hi)[:, None]
        fwd = 0.5 * (1 - (1 - etaE) ** n)           # forwarded (known) part
        y = y0c + (0.5 - y0c) * (1 - (1 - etaE) ** n)
        inj = y - fwd
        e = (edb * fwd[:, None, :] + 0.5 * inj[:, None, :]) / y[:, None, :]
        return y, e, fwd / y
    if kind == "blind_cal":
        eta_e = eta if eta_eve is None else eta_eve
        y0_e = y0 if y0_eve is None else y0_eve
        ed_e = ed if ed_eve is None else ed_eve
        y, e, _ = honest_yields(eta_e, y0_e, ed_e, cfg.e0)
        # feasibility y_n <= 1/2 is needed only where the photon number has weight;
        # beyond that (Poisson weight < 1e-30 at 1.2 * mu_1) the yield is capped at 1/2
        relevant = poisson_pmf(np.array(1.2 * mu1)) > 1e-30
        if np.any(2 * y[:, relevant] > 1):
            raise ValueError("calibrated blinding needs y_n <= 1/2")
        y = np.minimum(y, 0.5)
        return y, e, know
    raise ValueError(kind)


# ----------------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------------
@dataclass
class Telemetry:
    N: np.ndarray        # (W, 2, 3) pulses sent per Alice basis (Z, X) and intensity
    n_all: np.ndarray    # all clicks announced by Bob, per Alice basis and intensity
    n: np.ndarray        # sifted detections (Bob's basis = Alice's basis)
    m: np.ndarray        # sifted errors
    mu_mon: np.ndarray   # (W, 3) intensities seen by the monitor (nominal if none)
    n1: np.ndarray       # true single-photon sifted detections (audit only)
    m1: np.ndarray       # errors among them (audit only)
    known: np.ndarray    # sifted detections whose key bit Eve knows (audit only)
    label: np.ndarray    # (W,) 1 if the window is under attack


FIELDS = ("N", "n_all", "n", "m", "mu_mon", "n1", "m1", "known", "label")


def sample(cfg: Config, rng: np.random.Generator, state: dict, y, e, k,
           label=None, afterpulse: bool | np.ndarray = True) -> Telemetry:
    """Draw window counts. y, k have shape (W, NMAX+1), e (W, 2, NMAX+1).

    afterpulse: True uses the state's afterpulse probability, False none, or an array
    (W,) of afterpulse probabilities emulated by an attacker.
    """
    W = len(state["eta"])
    Np = cfg.n_pulses
    pa = np.array([cfg.p_z, 1 - cfg.p_z])
    pk = np.array(cfg.p_mu)
    pb = cfg.p_bob
    N = rng.multinomial(int(Np), np.outer(pa, pk).ravel(), size=W).reshape(W, 2, 3)
    mu_true = np.array(cfg.mu)[None, :] * state["iscale"]          # (W, 3)
    P = poisson_pmf(mu_true)                                       # (W, 3, NMAX+1)
    comp = [slice(0, 1), slice(1, 2), slice(2, None)]
    z = lambda: np.zeros((W, 2, 3))
    n_all, n, m, n1, m1, kn = z(), z(), z(), z(), z(), z()
    # basis-dependent efficiencies: click probability on Alice-basis-a pulses scales with
    # abas_a * sum_b p_b path_b; a click is sifted with probability p_a path_a / sum_b p_b path_b
    path, abas = state.get("path", np.ones((W, 2))), state.get("abas", np.ones((W, 2)))
    wsum = path @ pb                                                # (W,)
    fac = (abas * wsum[:, None])[:, :, None]                       # (W,2,1)
    pb_ = np.broadcast_to((pb[None, :] * path / wsum[:, None])[:, :, None], (W, 2, 3))
    gain_tot = np.zeros(W)
    for c in comp:
        Pc = P[:, :, c]                                            # (W,3,nc)
        pc = Pc.sum(-1)
        yc = np.einsum("wkn,wn->wk", Pc, y[:, c]) / np.maximum(pc, TINY)
        ec = np.einsum("wkn,wbn->wbk", Pc, (y[:, None, :] * e)[:, :, c]) / np.maximum(pc * yc, TINY)[:, None, :]
        kc = np.einsum("wkn,wn->wk", Pc, (y * k)[:, c]) / np.maximum(pc * yc, TINY)
        prob = np.clip(pc * yc, 0, 1)                              # (W,3)
        gain_tot += np.sum(prob * pk, 1)
        det = rng.binomial(N, np.clip(prob[:, None, :] * fac, 0, 1))
        sif = rng.binomial(det, pb_)
        err = rng.binomial(sif, np.clip(ec, 0, 1))
        kno = rng.binomial(sif, np.broadcast_to(np.clip(kc, 0, 1)[:, None, :], N.shape))
        n_all += det; n += sif; m += err; kn += kno
        if c == comp[1]:
            n1 += sif; m1 += err
    if afterpulse is not False:
        pap = state["pap"] if afterpulse is True else np.asarray(afterpulse)
        a = np.clip(pap * gain_tot, 0, 1)[:, None, None]           # extra click probability per gate
        det = rng.binomial(N, np.clip(a * fac, 0, 1))
        sif = rng.binomial(det, pb_)
        err = rng.binomial(sif, 0.5)
        n_all += det; n += sif; m += err
    mon = state["imon"] if cfg.int_monitor else np.ones_like(state["imon"])
    lab = np.zeros(W, int) if label is None else np.asarray(label, int)
    return Telemetry(N=N.astype(float), n_all=n_all, n=n, m=m,
                     mu_mon=np.array(cfg.mu)[None, :] * mon, n1=n1, m1=m1, known=kn, label=lab)


def splice(base: Telemetry, att: Telemetry, mask: np.ndarray) -> Telemetry:
    """Windows where mask is True come from `att`."""
    out = {}
    for f in FIELDS[:-1]:
        a, b = getattr(base, f), getattr(att, f)
        mk = mask.reshape((-1,) + (1,) * (a.ndim - 1))
        out[f] = np.where(mk, b, a)
    return Telemetry(**out, label=mask.astype(int))

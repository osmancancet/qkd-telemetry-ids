"""Unit tests: physics identities, bound validity and the indistinguishability claim."""
import numpy as np
import pytest

import qkdsim as q
import finite_key as fk


def _key(T, cfg):
    return fk.key_length(T.n[:, 0].sum(0), T.n[:, 1].sum(0), T.m[:, 0].sum(0),
                         T.m[:, 1].sum(0), cfg.mu, cfg.p_mu)


def test_poisson_normalised():
    P = q.poisson_pmf(np.array([0.5, 0.1, 2e-4]))
    assert np.allclose(P.sum(-1), 1, atol=1e-12)


def test_honest_gain_closed_form():
    cfg = q.Config(n_windows=3)
    st = q.static_state(cfg)
    y, e, k = q.honest_yields(st["eta"], st["y0"], st["ed"])
    for mu in cfg.mu:
        g = q.signal_gain(y, mu)
        assert np.allclose(g, 1 - (1 - st["y0"]) * np.exp(-st["eta"] * mu), rtol=1e-10)


def test_sifting_fraction():
    """Sifted clicks are a p_z_bob (Z) and 1 - p_z_bob (X) share of all clicks."""
    cfg = q.Config(n_windows=200)
    rng = np.random.default_rng(4)
    st = q.static_state(cfg, rng)
    T = q.sample(cfg, rng, st, *q.honest_yields(st["eta"], st["y0"], st["ed"]))
    frac = T.n.sum((0, 2)) / T.n_all.sum((0, 2))
    assert np.allclose(frac, cfg.p_bob, atol=2e-3)


@pytest.mark.parametrize("kind,s", [("ir", 0.1), ("ir", 0.5), ("pns", 0), ("blind_naive", 0),
                                    ("blind_gain", 0), ("blind_nodark", 0),
                                    ("blind_thresh", 0)])
def test_attacks_match_signal_gain(kind, s):
    cfg = q.Config(n_windows=3)
    st = q.static_state(cfg)
    yh, _, _ = q.honest_yields(st["eta"], st["y0"], st["ed"])
    y, e, k = q.attack_yields(kind, st["eta"], st["y0"], st["ed"], cfg, s)
    rtol = 1e-3 if kind == "blind_nodark" else 1e-9   # nodark drops the dark-count share
    assert np.allclose(q.signal_gain(y, cfg.mu[0]), q.signal_gain(yh, cfg.mu[0]), rtol=rtol)
    assert np.all((e >= 0) & (e <= 1)) and np.all((k >= 0) & (k <= 1))


def test_faked_state_vacuum_clicks_carry_no_information():
    cfg = q.Config(n_windows=3)
    st = q.static_state(cfg)
    for kind in ("blind_gain", "blind_cal"):
        y, e, k = q.attack_yields(kind, st["eta"], st["y0"], st["ed"], cfg)
        assert np.all(k[:, 0] == 0) and np.allclose(e[:, :, 0], 0.5) and np.all(k[:, 1:] == 1)


def test_calibrated_blinding_identical_yields():
    """Proposition 1: the calibrated attack reproduces y_n and e_{b,n} exactly."""
    cfg = q.Config(n_windows=5)
    rng = np.random.default_rng(0)
    st = q.channel_state(cfg, rng)
    yh, eh, _ = q.honest_yields(st["eta"], st["y0"], st["ed"])
    y, e, k = q.attack_yields("blind_cal", st["eta"], st["y0"], st["ed"], cfg)
    assert np.array_equal(y, yh) and np.array_equal(e, eh) and np.all(2 * y <= 1)


def test_s1_bound_is_lower_bound_honest():
    cfg = q.Config(n_windows=60)
    rng = np.random.default_rng(3)
    st = q.static_state(cfg, rng)
    viol = 0
    for _ in range(20):
        T = q.sample(cfg, rng, st, *q.honest_yields(st["eta"], st["y0"], st["ed"]))
        viol += _key(T, cfg)["sZ1"] > T.n1[:, 0].sum()
    assert viol == 0


def test_finite_key_approaches_asymptotic_rate():
    """With expected counts and a very large block, the finite-key rate approaches
    (from below) the asymptotic rate computed from the true single-photon yield."""
    cfg = q.Config(n_windows=1, p_ap=0.0)
    st = q.static_state(cfg)
    y, e, _ = q.honest_yields(st["eta"], st["y0"], st["ed"])
    N = 1e16
    pa, pb, pk = np.array([cfg.p_z, 1 - cfg.p_z]), cfg.p_bob, np.array(cfg.p_mu)
    Q = np.array([q.signal_gain(y, m)[0] for m in cfg.mu])
    P = q.poisson_pmf(np.array(cfg.mu))
    E = np.array([[np.sum(P[k] * y[0] * e[0, b]) / Q[k] for k in range(3)] for b in range(2)])
    n = N * (pa * pb)[:, None] * pk[None, :] * Q[None, :]
    m = n * E
    r = fk.key_length(n[0], n[1], m[0], m[1], cfg.mu, cfg.p_mu)
    s0 = N * pa[0] * pb[0] * np.sum(pk * P[:, 0]) * y[0, 0]
    s1 = N * pa[0] * pb[0] * np.sum(pk * P[:, 1]) * y[0, 1]
    e1 = e[0, 1, 1]                      # phase error = X-basis single-photon error
    ell_inf = s0 + s1 * (1 - fk.h2(e1)) - 1.16 * n[0].sum() * fk.h2(m[0].sum() / n[0].sum())
    assert 0.85 * ell_inf < r["ell"] <= ell_inf


def test_key_rate_positive_and_decreasing_with_distance():
    rates = []
    for L in (25, 50, 75):
        cfg = q.Config(n_windows=60, length_km=L)
        rng = np.random.default_rng(1)
        st = q.static_state(cfg)
        T = q.sample(cfg, rng, st, *q.honest_yields(st["eta"], st["y0"], st["ed"]))
        rates.append(_key(T, cfg)["ell"])
    assert rates[0] > rates[1] > rates[2] > 0


def test_pns_aborts():
    cfg = q.Config(n_windows=60)
    rng = np.random.default_rng(2)
    st = q.static_state(cfg)
    T = q.sample(cfg, rng, st, *q.attack_yields("pns", st["eta"], st["y0"], st["ed"], cfg))
    assert _key(T, cfg)["ell"] == 0


def test_threshold_hits_alpha_exactly_with_ties():
    import detectors as D
    rng = np.random.default_rng(0)
    s = np.r_[np.zeros(9000), rng.random(1000)]          # heavy ties at zero
    for a in (1e-2, 1e-3):
        thr = D.threshold(s, a)
        assert abs(np.mean(D.alarm_prob(s, thr)) - a) < 1e-9
    s2 = np.zeros(5000)                                    # all tied: randomised alarm prob = alpha
    assert abs(np.mean(D.alarm_prob(s2, D.threshold(s2, 1e-3))) - 1e-3) < 1e-9


def test_block_warmup_and_dcsx_shape():
    import detectors as D
    from run_all import stream
    rng = np.random.default_rng(1)
    cfg = q.Config(n_windows=400)
    T = stream(cfg, rng, 0.0)[0]
    b = D.Block(L=60).fit(T)
    sc = b.score(T)
    assert np.all(sc[:59] == 0) and np.all(sc[59:] > 0)
    assert D.dcs_residuals(T, xonly=True).shape == (400, 3)


def test_withhold_policy_is_blockwise():
    from run_all import key_audit, stream, PE_BLOCK
    rng = np.random.default_rng(2)
    cfg = q.Config(n_windows=600)
    T = stream(cfg, rng, 0.0)[0]
    mask = np.zeros(600, bool); mask[130:600] = True       # first full grid block starts at 180
    al = np.zeros(600, bool); al[200] = True               # one alarm inside the block [180, 240)
    out = key_audit(T, mask, cfg, {"X": al}, 130)
    assert [o["withheld"]["X"] for o in out] == [True, False, False, False, False, False, False]
    assert len(out) == (600 - 180) // PE_BLOCK

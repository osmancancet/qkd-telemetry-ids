"""Unit tests: physics identities, bound validity and the indistinguishability claim."""
import numpy as np
import pytest

import qkdsim as q
import finite_key as fk


def _state(cfg):
    return q.static_state(cfg)


def test_poisson_normalised():
    P = q.poisson_pmf(np.array([0.5, 0.1, 2e-4]))
    assert np.allclose(P.sum(-1), 1, atol=1e-12)


def test_honest_gain_closed_form():
    cfg = q.Config(n_windows=3)
    st = _state(cfg)
    y, e, k = q.honest_yields(st["eta"], st["y0"], st["ed"])
    for mu in cfg.mu:
        g = q.signal_gain(y, mu)
        assert np.allclose(g, 1 - (1 - st["y0"]) * np.exp(-st["eta"] * mu), rtol=1e-10)


@pytest.mark.parametrize("kind,s", [("ir", 0.1), ("ir", 0.5), ("pns", 0), ("blind_naive", 0)])
def test_attacks_match_signal_gain(kind, s):
    cfg = q.Config(n_windows=3)
    st = _state(cfg)
    yh, _, _ = q.honest_yields(st["eta"], st["y0"], st["ed"])
    y, e, k = q.attack_yields(kind, st["eta"], st["y0"], st["ed"], cfg, s)
    assert np.allclose(q.signal_gain(y, cfg.mu[0]), q.signal_gain(yh, cfg.mu[0]), rtol=1e-9)
    assert np.all((e >= 0) & (e <= 1)) and np.all((k >= 0) & (k <= 1))


def test_calibrated_blinding_identical_yields():
    """Proposition 1: the calibrated attack reproduces y_n and e_n exactly."""
    cfg = q.Config(n_windows=5)
    rng = np.random.default_rng(0)
    st = q.channel_state(cfg, rng)
    yh, eh, _ = q.honest_yields(st["eta"], st["y0"], st["ed"])
    y, e, k = q.attack_yields("blind_cal", st["eta"], st["y0"], st["ed"], cfg)
    assert np.array_equal(y, yh) and np.array_equal(e, eh) and np.all(k == 1)


def test_s1_bound_is_lower_bound_honest():
    cfg = q.Config(n_windows=60)
    rng = np.random.default_rng(3)
    st = q.static_state(cfg, rng)
    viol = 0
    for _ in range(20):
        T = q.sample(cfg, rng, st, *q.honest_yields(st["eta"], st["y0"], st["ed"]))
        r = fk.key_length(T.n[:, 0].sum(0), T.n[:, 1].sum(0), T.m[:, 0].sum(0),
                          T.m[:, 1].sum(0), cfg.mu, cfg.p_mu)
        viol += r["sZ1"] > T.n1[:, 0].sum()
    assert viol == 0


def test_key_rate_positive_and_decreasing_with_distance():
    rates = []
    for L in (25, 50, 75):
        cfg = q.Config(n_windows=60, length_km=L)
        rng = np.random.default_rng(1)
        st = q.static_state(cfg)
        T = q.sample(cfg, rng, st, *q.honest_yields(st["eta"], st["y0"], st["ed"]))
        r = fk.key_length(T.n[:, 0].sum(0), T.n[:, 1].sum(0), T.m[:, 0].sum(0),
                          T.m[:, 1].sum(0), cfg.mu, cfg.p_mu)
        rates.append(r["ell"])
    assert rates[0] > rates[1] > rates[2] > 0


def test_pns_aborts():
    cfg = q.Config(n_windows=60)
    rng = np.random.default_rng(2)
    st = q.static_state(cfg)
    T = q.sample(cfg, rng, st, *q.attack_yields("pns", st["eta"], st["y0"], st["ed"], cfg))
    r = fk.key_length(T.n[:, 0].sum(0), T.n[:, 1].sum(0), T.m[:, 0].sum(0),
                      T.m[:, 1].sum(0), cfg.mu, cfg.p_mu)
    assert r["ell"] == 0

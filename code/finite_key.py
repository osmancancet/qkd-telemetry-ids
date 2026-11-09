"""Finite-key length for three-intensity decoy-state BB84.

Implements the bounds of Lim, Curty, Walenta, Xu, Zbinden, Phys. Rev. A 89, 022307
(2014), with Z as the key basis and X as the test basis. Hoeffding deviations use
delta(n) = sqrt(n/2 * ln(21/eps_sec)), the ε-split of the original paper.
"""
from __future__ import annotations

import numpy as np


def h2(x):
    x = np.clip(x, 1e-15, 1 - 1e-15)
    return -x * np.log2(x) - (1 - x) * np.log2(1 - x)


def _tau(mu, p, n):
    from math import factorial
    return sum(pk * np.exp(-k) * k ** n / factorial(n) for k, pk in zip(mu, p))


def _bounds(cnt, mu, p, eps):
    """cnt: (..., 3) detections per intensity in one basis. Returns n^-, n^+ arrays."""
    tot = cnt.sum(-1, keepdims=True)
    d = np.sqrt(tot / 2 * np.log(21 / eps))
    ek = np.exp(np.array(mu)) / np.array(p)
    return ek * (cnt - d), ek * (cnt + d)


def s0_lower(cnt, mu, p, eps):
    m1, m2, m3 = mu
    nm, npl = _bounds(cnt, mu, p, eps)
    t0 = _tau(mu, p, 0)
    return np.maximum(t0 * (m2 * nm[..., 2] - m3 * npl[..., 1]) / (m2 - m3), 0.0)


def s1_lower(cnt, mu, p, eps):
    m1, m2, m3 = mu
    nm, npl = _bounds(cnt, mu, p, eps)
    t0, t1 = _tau(mu, p, 0), _tau(mu, p, 1)
    s0 = s0_lower(cnt, mu, p, eps)
    num = t1 * m1 * (nm[..., 1] - npl[..., 2]
                     - (m2 ** 2 - m3 ** 2) / m1 ** 2 * (npl[..., 0] - s0 / t0))
    den = m1 * (m2 - m3) - (m2 ** 2 - m3 ** 2)
    return np.maximum(num / den, 0.0)


def v1_upper(err, mu, p, eps):
    m1, m2, m3 = mu
    mm, mp = _bounds(err, mu, p, eps)
    t1 = _tau(mu, p, 1)
    return np.maximum(t1 * (mp[..., 1] - mm[..., 2]) / (m2 - m3), 0.0)


def gamma(a, b, c, d):
    b = np.clip(b, 1e-12, 0.5)
    c = np.maximum(c, 1.0); d = np.maximum(d, 1.0)
    arg = (c + d) / (c * d * (1 - b) * b) * (21 ** 2 / a ** 2)
    return np.sqrt((c + d) * (1 - b) * b / (c * d * np.log(2)) * np.log2(arg))


def key_length(nZ, nX, mZ, mX, mu, p, eps_sec=1e-10, eps_cor=1e-15, f_ec=1.16):
    """nZ, nX, mZ, mX: (..., 3) detections/errors per intensity in each basis,
    accumulated over one post-processing block. Returns dict with ell and parts."""
    sZ0 = s0_lower(nZ, mu, p, eps_sec)
    sZ1 = s1_lower(nZ, mu, p, eps_sec)
    sX1 = s1_lower(nX, mu, p, eps_sec)
    vX1 = v1_upper(mX, mu, p, eps_sec)
    ratio = np.where(sX1 > 0, vX1 / np.maximum(sX1, 1e-300), 0.5)
    phi = np.minimum(ratio + gamma(eps_sec, ratio, sX1, sZ1), 0.5)
    nz = nZ.sum(-1); ez = mZ.sum(-1) / np.maximum(nz, 1)
    lam = f_ec * nz * h2(ez)
    ell = (sZ0 + sZ1 * (1 - h2(phi)) - lam
           - 6 * np.log2(21 / eps_sec) - np.log2(2 / eps_cor))
    ell = np.where((sZ1 > 0) & (ell > 0), np.floor(ell), 0.0)
    return dict(ell=ell, sZ0=sZ0, sZ1=sZ1, sX1=sX1, vX1=vX1, phi=phi, lam=lam, nZ=nz, EZ=ez)

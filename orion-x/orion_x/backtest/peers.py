"""Peer algorithms.

A new strategy is only interesting if it beats the obvious ones on the same
data, through the same cost model, judged by the same selection-corrected
statistic. ORION-X v4's README listed "compare against BTC/ETH, cash,
equal-weight and simple baselines" as a research requirement and shipped no
comparison of any kind.

Each peer is a well-known published rule, implemented in its standard form and
deliberately not tuned. They are the null hypotheses ORION-X has to clear.

    tsmom            Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum",
                     *Journal of Financial Economics* 104(2).
    xs_momentum      Jegadeesh & Titman (1993), *Journal of Finance* 48(1),
                     applied cross-sectionally by the harness.
    reversal         Lehmann (1990), *Quarterly Journal of Economics* 105(1);
                     Lo & MacKinlay (1990), *Review of Financial Studies* 3(2).
    donchian         Donchian channel breakout, the Turtle rule.
    ma_cross         Dual moving-average crossover; Brock, Lakonishok &
                     LeBaron (1992), *Journal of Finance* 47(5).
    rsi2             Connors & Alvarez (2009) short-term RSI mean reversion.
    bollinger        Bollinger band reversion.
    funding_carry    Perpetual funding as a crowding/contrarian signal.
    ofi              Cont, Kukanov & Stoikov (2014) order flow imbalance.
    vol_breakout     Volatility-expansion breakout.
    random           A coin flip, as the explicit null.
"""
from __future__ import annotations

import numpy as np

__all__ = ["PEERS", "peer_side"]


def _safe_slice(x: np.ndarray, i: int, n: int) -> np.ndarray:
    lo = max(0, i - n + 1)
    return x[lo : i + 1]


def tsmom(ctx: dict, i: int) -> float:
    w = _safe_slice(ctx["log_return"], i, 168)
    if w.size < 24:
        return 0.0
    return float(np.sign(w.sum()))


def reversal(ctx: dict, i: int) -> float:
    w = _safe_slice(ctx["log_return"], i, 4)
    if w.size < 4:
        return 0.0
    return float(-np.sign(w.sum()))


def donchian(ctx: dict, i: int) -> float:
    p = _safe_slice(ctx["price"], i, 96)
    if p.size < 48:
        return 0.0
    if p[-1] >= p[:-1].max():
        return 1.0
    if p[-1] <= p[:-1].min():
        return -1.0
    return 0.0


def ma_cross(ctx: dict, i: int) -> float:
    p = _safe_slice(ctx["price"], i, 240)
    if p.size < 200:
        return 0.0
    return float(np.sign(p[-24:].mean() - p[-200:].mean()))


def rsi2(ctx: dict, i: int) -> float:
    p = _safe_slice(ctx["price"], i, 20)
    if p.size < 10:
        return 0.0
    d = np.diff(p[-11:])
    up, dn = d[d > 0].sum(), -d[d < 0].sum()
    if up + dn < 1e-12:
        return 0.0
    rsi = 100.0 * up / (up + dn)
    if rsi < 15:
        return 1.0
    if rsi > 85:
        return -1.0
    return 0.0


def bollinger(ctx: dict, i: int) -> float:
    p = _safe_slice(ctx["price"], i, 96)
    if p.size < 48:
        return 0.0
    mu, sd = p.mean(), p.std(ddof=1)
    if sd < 1e-12:
        return 0.0
    z = (p[-1] - mu) / sd
    if z < -2.0:
        return 1.0
    if z > 2.0:
        return -1.0
    return 0.0


def funding_carry(ctx: dict, i: int) -> float:
    f = _safe_slice(ctx["funding"], i, 336)
    if f.size < 100:
        return 0.0
    cur = f[-1]
    hi, lo = np.quantile(f, 0.85), np.quantile(f, 0.15)
    if cur > hi:
        return -1.0
    if cur < lo:
        return 1.0
    return 0.0


def ofi_signal(ctx: dict, i: int) -> float:
    o = _safe_slice(ctx["ofi"], i, 72)
    if o.size < 48:
        return 0.0
    z = (o[-1] - o.mean()) / (o.std(ddof=1) + 1e-12)
    return float(np.clip(z / 1.5, -1.0, 1.0))


def vol_breakout(ctx: dict, i: int) -> float:
    r = _safe_slice(ctx["log_return"], i, 96)
    if r.size < 48:
        return 0.0
    sd = r[:-4].std(ddof=1)
    if sd < 1e-12:
        return 0.0
    recent = r[-4:].sum()
    if abs(recent) > 2.0 * sd * 2.0:
        return float(np.sign(recent))
    return 0.0


def random_side(ctx: dict, i: int) -> float:
    rng = np.random.default_rng((i * 2654435761 + ctx["seed"]) % (2**32))
    return float(rng.choice([-1.0, 1.0]))


def buy_and_hold(ctx: dict, i: int) -> float:
    return 1.0


PEERS = {
    "buy_and_hold": buy_and_hold,
    "tsmom_7d": tsmom,
    "reversal_4h": reversal,
    "donchian_96h": donchian,
    "ma_cross_24_200": ma_cross,
    "rsi2_reversion": rsi2,
    "bollinger_2sd": bollinger,
    "funding_carry": funding_carry,
    "ofi_microstructure": ofi_signal,
    "vol_breakout": vol_breakout,
    "random_coinflip": random_side,
}


def peer_side(name: str, ctx: dict, i: int) -> float:
    return PEERS[name](ctx, i)

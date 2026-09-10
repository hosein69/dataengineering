"""Triple-barrier labeling.

The label must match what the strategy actually does. ORION-X v4 emitted three
entries, three take-profits and a stop, and then had no label at all -- there
was nothing to validate against. A fixed-horizon return label would not have
matched either, because it ignores that the position is closed early by the
stop.

Lopez de Prado (2018), ch. 3: the triple-barrier method labels each observation
by which of three barriers the path touches first -- profit target, stop loss,
or the vertical time barrier.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["BarrierLabel", "triple_barrier_labels"]


@dataclass
class BarrierLabel:
    outcome: np.ndarray        # +1 target, -1 stop, 0 timeout
    realized_return: np.ndarray
    end_index: np.ndarray
    holding_periods: np.ndarray


def triple_barrier_labels(
    prices: np.ndarray,
    sides: np.ndarray,
    tp_distance: np.ndarray,
    sl_distance: np.ndarray,
    horizon: int,
) -> BarrierLabel:
    """Label each observation by the first barrier its forward path touches.

    Args:
        prices: price series.
        sides: +1 / -1 / 0 per observation; 0 observations get a zero label.
        tp_distance, sl_distance: per-observation barrier distances as fractions.
        horizon: vertical barrier, in observations.

    Returns:
        BarrierLabel. `realized_return` is signed by side, so it is the return
        to the position rather than to the asset.
    """
    p = np.asarray(prices, dtype=float)
    n = p.size
    side = np.asarray(sides, dtype=float)
    tp = np.asarray(tp_distance, dtype=float)
    sl = np.asarray(sl_distance, dtype=float)

    outcome = np.zeros(n)
    ret = np.zeros(n)
    end = np.arange(n) + horizon
    hold = np.full(n, float(horizon))

    for i in range(n):
        s = side[i]
        stop_at = min(i + horizon, n - 1)
        end[i] = stop_at
        if s == 0 or i >= n - 1:
            continue
        entry = p[i]
        up = entry * (1.0 + s * tp[i])
        dn = entry * (1.0 - s * sl[i])
        path = p[i + 1 : stop_at + 1]
        if path.size == 0:
            continue
        hit_up = (path >= up) if s > 0 else (path <= up)
        hit_dn = (path <= dn) if s > 0 else (path >= dn)
        first_up = int(np.argmax(hit_up)) if hit_up.any() else n + 1
        first_dn = int(np.argmax(hit_dn)) if hit_dn.any() else n + 1
        if first_up < first_dn:
            # tp/sl are the position's own profit and loss distances; they must
            # not be multiplied by `side` again or every short is inverted.
            outcome[i], ret[i], hold[i] = 1.0, tp[i], first_up + 1.0
            end[i] = i + first_up + 1
        elif first_dn < first_up:
            outcome[i], ret[i], hold[i] = -1.0, -sl[i], first_dn + 1.0
            end[i] = i + first_dn + 1
        else:
            outcome[i] = 0.0
            ret[i] = s * (path[-1] / entry - 1.0)
            hold[i] = float(path.size)
            end[i] = stop_at
    return BarrierLabel(outcome, ret, end.astype(int), hold)

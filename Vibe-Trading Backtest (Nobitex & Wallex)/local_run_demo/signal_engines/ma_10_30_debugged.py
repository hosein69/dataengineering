import pandas as pd


class SignalEngine:
    """MA(10/30) crossover — debugged variant.

    Fixes over the raw version:
      D3  warm-up bars emit an explicit no-position signal instead of relying on
          `NaN > NaN` being False, so "indicator not ready" is never conflated
          with "bearish". Paired with `warmup_bars` in config.json, which keeps
          those bars out of the graded window entirely.
      D4  per-symbol target is 1/N of equity instead of a flat 1.0. With the raw
          version the book swung between 100% in a single coin (one signal live)
          and 20% each (all five live), so realised risk depended on how many
          symbols happened to agree rather than on any sizing decision. For a
          single-symbol run 1/N == 1.0, so this is inert there by construction.
    """

    def __init__(self, fast=10, slow=30):
        self.fast = fast
        self.slow = slow

    def generate(self, data_map):
        n = max(len(data_map), 1)
        out = {}
        for code, df in data_map.items():
            close = df["close"]
            fast_ma = close.rolling(self.fast, min_periods=self.fast).mean()
            slow_ma = close.rolling(self.slow, min_periods=self.slow).mean()
            ready = fast_ma.notna() & slow_ma.notna()
            sig = ((fast_ma > slow_ma) & ready).astype(float) / n
            out[code] = sig.where(ready, 0.0)
        return out

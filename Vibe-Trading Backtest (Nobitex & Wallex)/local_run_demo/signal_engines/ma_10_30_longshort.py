import pandas as pd


class SignalEngine:
    """MA(10/30) crossover, symmetric long/short — debugged sizing.

    The long-only variant sits in cash when fast <= slow. This one takes the
    other side instead (-1/N), so the short leg gets graded by the engine
    rather than assumed to work. CryptoEngine supports direction -1, so the
    short leg pays the same fees/slippage and is marked to market the same way.

    Sizing is 1/N per symbol for the same reason as the long-only debugged
    engine: a flat +/-1.0 lets a single live signal claim the whole book and
    then aborts the run when a second symbol wants capital.
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
            direction = (fast_ma > slow_ma).astype(float) * 2.0 - 1.0
            out[code] = (direction / n).where(ready, 0.0)
        return out

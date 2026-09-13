import pandas as pd

class SignalEngine:
    """MA crossover: long when MA(fast) > MA(slow), flat otherwise."""

    def __init__(self, fast=20, slow=50):
        self.fast = fast
        self.slow = slow

    def generate(self, data_map):
        out = {}
        for code, df in data_map.items():
            fast_ma = df["close"].rolling(self.fast).mean()
            slow_ma = df["close"].rolling(self.slow).mean()
            sig = (fast_ma > slow_ma).astype(float)
            out[code] = sig
        return out

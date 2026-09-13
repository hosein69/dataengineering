import pandas as pd

class SignalEngine:
    """Faster MA crossover: long when MA(10) > MA(30)."""

    def __init__(self, fast=10, slow=30):
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

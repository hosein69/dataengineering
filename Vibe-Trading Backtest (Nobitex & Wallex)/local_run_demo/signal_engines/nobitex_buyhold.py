import pandas as pd

class SignalEngine:
    """Buy & Hold baseline: signal = 1 as soon as data exists."""

    def generate(self, data_map):
        out = {}
        for code, df in data_map.items():
            out[code] = pd.Series(1.0, index=df.index)
        return out

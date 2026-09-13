import pandas as pd

class SignalEngine:
    """RSI(14) mean-reversion: long below 30, flat above 70, hold between."""

    def __init__(self, period=14, buy_below=30, sell_above=70):
        self.period = period
        self.buy_below = buy_below
        self.sell_above = sell_above

    def _rsi(self, close):
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    def generate(self, data_map):
        out = {}
        for code, df in data_map.items():
            rsi = self._rsi(df["close"])
            sig = pd.Series(0.0, index=df.index)
            state = 0.0
            vals = []
            for v in rsi:
                if pd.notna(v):
                    if v < self.buy_below:
                        state = 1.0
                    elif v > self.sell_above:
                        state = 0.0
                vals.append(state)
            sig[:] = vals
            out[code] = sig
        return out

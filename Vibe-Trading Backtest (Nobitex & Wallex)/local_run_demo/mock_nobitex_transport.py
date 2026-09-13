"""
DISCLOSURE: this sandbox's network egress policy blocks apiv2.nobitex.ir
(confirmed via direct curl and WebFetch -> both rejected with 403 at the
proxy). To still exercise the REAL, unmodified vibe-trading-ai package code
(backtest.loaders.nobitex.DataLoader, backtest.engines.crypto.CryptoEngine,
backtest.metrics), this module monkeypatches only the HTTP transport
(requests.Session.get) so nobitex.py's own parsing/pagination/validation
code runs against a synthetic-but-correctly-shaped UDF JSON payload instead
of the live endpoint. Every other line of engine/loader/metrics code is
100% the real installed package - nothing here touches signal generation,
order sizing, PnL, or the performance formulas.

Prices are a seeded random walk in a realistic BTCIRT (Toman) range -
NOT real market data.
"""
import numpy as np
import pandas as pd
import requests

_REAL_GET = requests.Session.get
NOBITEX_URL = "https://apiv2.nobitex.ir/market/udf/history"

_SEEDS = {"BTCIRT": 42, "USDTIRT": 7}
_START_PRICE = {"BTCIRT": 4_200_000_000.0, "USDTIRT": 91_000.0}
_DAILY_VOL = {"BTCIRT": 0.032, "USDTIRT": 0.006}
_DAILY_DRIFT = {"BTCIRT": 0.0012, "USDTIRT": 0.0004}


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def _synthetic_series(symbol: str, from_ts: int, to_ts: int, resolution: str):
    step_s = {"1": 60, "5": 300, "15": 900, "30": 1800, "60": 3600,
              "180": 10800, "240": 14400, "360": 21600, "720": 43200,
              "D": 86400}.get(resolution, 86400)
    times = list(range(int(from_ts), int(to_ts), step_s))
    if len(times) > 500:
        times = times[-500:]  # newest 500, like a real "page 1"
    n = len(times)
    if n == 0:
        return None
    seed = _SEEDS.get(symbol, 1)
    rng = np.random.default_rng(seed)
    daily_vol = _DAILY_VOL.get(symbol, 0.03)
    daily_drift = _DAILY_DRIFT.get(symbol, 0.0)
    bar_frac = step_s / 86400.0
    vol = daily_vol * np.sqrt(bar_frac)
    drift = daily_drift * bar_frac
    rets = rng.normal(drift, vol, size=n)
    price0 = _START_PRICE.get(symbol, 1_000_000.0)
    close = price0 * np.cumprod(1 + rets)
    open_ = np.empty(n)
    open_[0] = price0
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    vol_arr = rng.uniform(10, 500, n)
    return {
        "s": "ok",
        "t": times,
        "o": open_.tolist(),
        "h": high.tolist(),
        "l": low.tolist(),
        "c": close.tolist(),
        "v": vol_arr.tolist(),
    }


def _patched_get(self, url, params=None, timeout=None, **kwargs):
    if url == NOBITEX_URL and params is not None:
        if "countback" in params:
            # availability probe: always report healthy
            return _FakeResp({"s": "ok", "t": [int(params.get("to", 0))],
                               "o": [1.0], "h": [1.0], "l": [1.0], "c": [1.0], "v": [1.0]})
        page = int(params.get("page", 1))
        if page > 1:
            return _FakeResp({"s": "no_data"})
        payload = _synthetic_series(
            params["symbol"], params["from"], params["to"], params["resolution"]
        )
        if payload is None:
            return _FakeResp({"s": "no_data"})
        return _FakeResp(payload)
    return _REAL_GET(self, url, params=params, timeout=timeout, **kwargs)


def install():
    requests.Session.get = _patched_get

# -*- coding: utf-8 -*-
"""V29.9 — cash-flow engine must scale linearly and keep rate semantics."""
import time
from decimal import Decimal

import pandas as pd

from gsi.cashflow.engine import PreparedRates, build_cashflow, select_rate
from tools.cashflow_synthetic import synthetic_inputs


def test_engine_scales_linearly_on_dwh_sized_input():
    # 1500 cases ≈ 22k events. The 29.8.2 engine rescanned all events/links for
    # every case/stage (≈50 s here); the indexed engine needs ~1–2 s.
    ev, li, ra, ru, me = synthetic_inputs(cases=1500)
    t0 = time.perf_counter()
    r = build_cashflow(ev, links=li, rates=ra, as_of="2026-01-31", rules=ru, measurements=me)
    assert time.perf_counter() - t0 < 20
    assert len(r["chain"]) == 1500 * 9
    assert not r["summary"].empty and not r["valuation"].empty


def test_blank_value_date_falls_back_to_rate_date():
    rates = pd.DataFrame([
        dict(rate_id="a", value_date="2026-01-05", date="2026-01-05", base="EUR", quote="IRR",
             rate="600000", purpose="accounting", approved="true", source="CBI", max_age_days="30"),
        dict(rate_id="b", value_date=None, date="2026-01-10", base="EUR", quote="IRR",
             rate="610000", purpose="accounting", approved="true", source="CBI", max_age_days="30"),
    ])
    from datetime import date
    value, when, src = select_rate(rates, "EUR", "IRR", date(2026, 1, 20))
    assert value == Decimal("610000") and when == date(2026, 1, 10) and src == "CBI"
    assert select_rate(PreparedRates(rates), "EUR", "IRR", date(2026, 1, 20))[0] == Decimal("610000")


def test_adapter_header_attrs_are_not_deep_copied_per_operation():
    import copy
    from gsi.adapters.base import SharedList
    headers = SharedList(["a", "b"])
    assert copy.deepcopy(headers) is headers and copy.copy(headers) is headers
    df = pd.DataFrame({"x": [1, 2]})
    df.attrs["source_headers"] = headers
    assert df["x"].attrs["source_headers"] is headers      # shared, not copied
    import json
    assert json.loads(json.dumps(df.attrs)) == {"source_headers": ["a", "b"]}

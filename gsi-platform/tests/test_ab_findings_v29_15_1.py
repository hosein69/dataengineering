# -*- coding: utf-8 -*-
"""Locks for the three defects the 29.14.0 ↔ 29.15.0 A/B run exposed.

The A/B harness ran both packages on identical inputs (demo, realistic-header
synthetic, and a 40× scaled copy) and compared every frame, Excel sheet and
HTML export cell by cell. Business outputs were identical; the defects below
only showed up at scale or on the new surface, and each test here was run
against the unfixed code first and failed.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from gsi.trust import anomaly as A


def _materials(values):
    return pd.DataFrame({"KEY_MATERIAL": [f"M{i:03d}" for i in range(len(values))],
                         "DAILY_NEED": values})


def test_a_common_value_is_a_mode_not_an_outlier():
    """Scaled A/B: with most needs tied at 100/110 the MAD collapsed, and "10"
    and "411" — each shared by a sixth of all materials — became 82 questions."""
    values = [100] * 10 + [110] * 3 + [10] * 5 + [411] * 4
    hits = [a for a in A.detect(_materials(values)) if a.kind == A.VALUE_OUTLIER]
    assert hits == []


def test_rarity_guard_still_lets_a_lone_slip_through():
    values = [100] * 10 + [110] * 3 + [10] * 5 + [411] * 4 + [100_000]
    hits = [a for a in A.detect(_materials(values)) if a.kind == A.VALUE_OUTLIER]
    assert [h.key for h in hits] == [f"M{len(values) - 1:03d}"]
    assert hits[0].leading.code == A.SCALE_SLIP


def _invoices(currency):
    rows = [{"CANONICAL_REG": f"R{i}", "INVOICE_VALUE": 20_000 + 1_500 * i,
             "INVOICE_CURRENCY": currency} for i in range(20)]
    rows[7]["INVOICE_VALUE"] = rows[7]["INVOICE_VALUE"] * 1000
    return pd.DataFrame(rows)


def test_amounts_without_currency_are_not_compared_with_each_other():
    """Scaled A/B: blank-currency invoices were pooled as «همه پرونده‌ها» —
    EUR next to IRR — and 32 of 83 were called outliers."""
    assert [a for a in A.detect(_invoices("")) if a.kind == A.VALUE_OUTLIER] == []
    # the same data with a currency is judged as before
    hits = [a for a in A.detect(_invoices("EUR")) if a.kind == A.VALUE_OUTLIER]
    assert [h.key for h in hits] == ["R7"]


def test_unknown_invoice_value_stays_unknown_not_zero():
    """INVOICE_VALUE (the commitment basis since 29.12) was derived with a 0
    default: an absent SATA invoice counted as a filled field in the trust
    layer and reached the FX timeline as numeric evidence «۰»."""
    from gsi.stages.base import PipelineContext
    from gsi.stages.s20_derive import DeriveStage

    out = DeriveStage().run(pd.DataFrame({
        "SATA_INVOICE_VALUE": [float("nan"), 0, "1,250.5", ""],
    }), PipelineContext(rb=None, today=date(2026, 9, 27)))
    assert out["INVOICE_VALUE_IS_UNKNOWN"].tolist() == [True, False, False, True]
    assert pd.isna(out.loc[0, "INVOICE_VALUE"]) and pd.isna(out.loc[3, "INVOICE_VALUE"])
    assert out.loc[1, "INVOICE_VALUE"] == 0          # a real zero stays zero
    assert out.loc[2, "INVOICE_VALUE"] == 1250.5


def test_a_flood_of_outliers_becomes_one_question_about_the_field():
    """50k-row A/B: evenly spread quantities produced 880 questions for one
    field. Many symptoms, one cause — one question, like VOCABULARY_SHIFT."""
    import numpy as np
    rng = np.random.default_rng(3)
    df = pd.DataFrame({"KEY_MATERIAL": [f"M{i:05d}" for i in range(20_000)],
                       "STOCK_IKCO": rng.integers(0, 50_000, 20_000)})
    hits = [a for a in A.detect(df, limit=0) if a.field == "STOCK_IKCO"]
    assert len(hits) == 1
    assert hits[0].key == "*" and hits[0].leading.code == A.MIXED_POPULATION
    assert hits[0].repair is None


def test_a_few_outliers_are_still_asked_one_by_one():
    values = [100 + (i % 7) * 13 for i in range(200)] + [100_000, 150_000]
    hits = [a for a in A.detect(_materials(values)) if a.kind == A.VALUE_OUTLIER]
    assert sorted(h.key for h in hits) == ["M200", "M201"]


def test_invoice_amount_travels_with_its_own_currency():
    """Treatment A/B: a ×1000 SATA invoice went unseen because the derived
    CURRENCY (NTSW/FX/expert) was blank for that case while SATA itself said
    CNY — and the FX timeline labelled SATA's amount with another source's
    currency. The amount and its currency now come from the same source."""
    from gsi.stages.base import PipelineContext
    from gsi.stages.s20_derive import DeriveStage
    from gsi.stages.s55_fx_traceability import FxTraceabilityStage
    from gsi.rulebook import get_rulebook

    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 27)),
                          today=date(2026, 9, 27))
    out = DeriveStage().run(pd.DataFrame({
        "SATA_INVOICE_VALUE": ["1000", "2000"], "SATA_CURRENCY": ["CNY", ""],
        "NTSW_CURRENCY": ["EUR", "EUR"]}), ctx)
    assert out["INVOICE_CURRENCY"].tolist() == ["CNY", ""]   # never borrowed
    assert out["CURRENCY"].tolist() == ["EUR", "EUR"]         # unchanged

    df = pd.DataFrame([{"CANONICAL_REG": "12345678", "INVOICE_VALUE": 1000.0,
                        "INVOICE_CURRENCY": "CNY", "CURRENCY": "EUR",
                        "SATA_DATE": "1405/02/01", "SATA_NO": "S1"}])
    FxTraceabilityStage().run(df, ctx)
    events = ctx.extras["fx_eventlog"]
    sata = events[events["EVENT_TYPE"] == "SATA"]
    assert sata["CURRENCY"].tolist() == ["CNY"]

# -*- coding: utf-8 -*-
"""ادغام نسخه مالک با دور ۸ و دامنه تاریخی خروجی‌ها (داده ساختگی)."""
from datetime import date

import pandas as pd
import pytest

from gsi.studio_core import date_scope as DS
from gsi.warehouse import business_dwh as bd


def _frame():
    return pd.DataFrame({
        "KEY_ORDER": ["O1", "O2", "O3", "O4"],
        "NTSW_REQ_DATE": ["1405/01/10", "1405/03/01", "", "1404/12/29"],
        "ALLOC_QUEUE_ENTER_DATE": ["", "", "1405/02/02", ""],
        "IL_REG_DATE": ["1404/05/01", "", "1405/01/01", "1405/06/01"],
    })


def test_request_range_uses_first_candidate_then_fallback_column():
    res = DS.apply_date_scope(_frame(), {"request": DS.DateRange(DS.parse_bound("1405/01/01"),
                                                                 DS.parse_bound("1405/02/31"))})
    # O3 تاریخ درخواست ندارد ولی تاریخ ورود صفش در بازه است.
    assert list(res.df["KEY_ORDER"]) == ["O1", "O3"]
    assert res.rows_before == 4 and res.rows_after == 2


def test_rows_without_date_are_excluded_unless_kept():
    rng = DS.DateRange(DS.parse_bound("1405/01/01"), None)
    assert list(DS.apply_date_scope(_frame(), {"il": rng}).df["KEY_ORDER"]) == ["O3", "O4"]
    rng.include_missing = True
    assert list(DS.apply_date_scope(_frame(), {"il": rng}).df["KEY_ORDER"]) == ["O2", "O3", "O4"]


def test_ranges_combine_and_gregorian_bounds_work():
    res = DS.apply_date_scope(_frame(), {
        "request": DS.DateRange(DS.parse_bound("2026-03-01"), None),
        "il": DS.DateRange(None, DS.parse_bound("1405/03/01")),
    })
    assert list(res.df["KEY_ORDER"]) == ["O1", "O3"]


def test_missing_scope_column_is_reported_not_applied():
    res = DS.apply_date_scope(_frame(), {"po": DS.DateRange(date(2026, 1, 1), None)})
    assert len(res.df) == 4
    assert res.unavailable and "PO" in DS.describe(res)


def test_bad_bound_is_an_error_not_a_silent_no_op():
    with pytest.raises(ValueError):
        DS.parse_bound("فردا")


def test_inactive_scope_returns_same_frame():
    df = _frame()
    assert DS.apply_date_scope(df, {"request": DS.DateRange()}).df is df


def _supply(rows):
    return pd.DataFrame(rows)


def test_conflicting_fact_rows_raise_with_all_keys():
    rows = _supply([
        {"KEY_ORDER": "O1", "KEY_MATERIAL": "M1", "MOGH_QTY_TRANSIT": 1},
        {"KEY_ORDER": "O1", "KEY_MATERIAL": "M1", "MOGH_QTY_TRANSIT": 2},
        {"KEY_ORDER": "O2", "KEY_MATERIAL": "M2", "MOGH_QTY_TRANSIT": 1},
        {"KEY_ORDER": "O2", "KEY_MATERIAL": "M2", "MOGH_QTY_TRANSIT": 3},
    ])
    with pytest.raises(bd.FactGrainConflict) as ex:
        bd._fact_rows("dwh_fact_supply_position", rows)
    assert ex.value.count == 2 and "DWH_FACT_GRAIN_CONFLICT" in str(ex.value)


def test_identical_duplicates_are_one_row():
    rows = _supply([{"KEY_ORDER": "O1", "KEY_MATERIAL": "M1", "MOGH_QTY_TRANSIT": 1}] * 2)
    out, _ = bd._fact_rows("dwh_fact_supply_position", rows)
    assert len(out) == 1


def test_orderless_material_lines_are_kept_apart_by_content():
    rows = _supply([
        {"KEY_ORDER": "", "KEY_MATERIAL": "M1", "MOGH_QTY_TRANSIT": 1},
        {"KEY_ORDER": "بدون سفارش", "KEY_MATERIAL": "M1", "MOGH_QTY_TRANSIT": 2},
    ])
    a, _ = bd._fact_rows("dwh_fact_supply_position", rows)
    b, _ = bd._fact_rows("dwh_fact_supply_position", rows.iloc[::-1])
    assert sorted(r[:2] for r in a) == [("#1", "M1"), ("#2", "M1")]
    assert sorted(a) == sorted(b)

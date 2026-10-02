# -*- coding: utf-8 -*-
"""V29.9 — data-accuracy regressions found in the full-package review.

Every case below reproduced a wrong number/date/currency on the 29.8.2 build.
"""
import math
from datetime import date

import pandas as pd
import pytest

from gsi.core import jalali
from gsi.core.jalali import CalendarEngine, gregorian_to_jalali, is_jalali_leap, jalali_sort_key
from gsi.core.numeric_parse import parse_decimal
from gsi.core.text import clean_key, is_empty_val, normalize_persian_text, num_safe
from gsi.warehouse.numeric import decimal_text, number


# ── numbers ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, expected", [
    (1e-05, 1e-05),            # was 105.0 (exponent stripped)
    (5e-05, 5e-05),            # was 505.0
    (1.5e16, 1.5e16),          # was 1.516
    ("1.5E+06", 1_500_000.0),  # was 1.506
    ("1٫5", 1.5),              # Persian decimal separator; was 15.0
    ("۱٬۲۳۴٫۵", 1234.5),       # Persian digits + separators; was 12345.0
    ("1,234.56-", -1234.56),   # SAP trailing minus; was +1234.56
    ("−1234", -1234.0),   # Unicode minus; was +1234
    ("(1,234)", -1234.0),
    ("‏1,234", 1234.0),   # RLM from copy/paste
    ("1 234 567", 1234567.0),
])
def test_num_safe_and_strict_number_agree_on_unambiguous_notation(raw, expected):
    assert num_safe(raw) == pytest.approx(expected)
    assert number(raw) == pytest.approx(expected)


def test_strict_parser_keeps_unknown_distinct_from_zero():
    for raw in ("12,34", "1.234.567", "?", "نامشخص", "", None, float("nan"), True):
        assert parse_decimal(raw) is None, raw
        assert math.isnan(number(raw)), raw
    assert decimal_text("0") == "0"
    # legacy num_safe contract is unchanged for ambiguous/empty input
    assert num_safe("12,34") == pytest.approx(12.34)
    assert num_safe("1.234.567") == 1234567.0
    assert num_safe("نامشخص") == 0.0


def test_cashflow_engine_rejects_ambiguous_comma_instead_of_multiplying():
    from gsi.cashflow.engine import number as cf_number
    assert cf_number("1,5") is None          # was Decimal("15")
    assert cf_number("1,500") == 1500
    assert str(cf_number("2.5e-3")) in {"0.0025", "2.5E-3"}


# ── Jalali calendar ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", ["1402/12/30", "1403/07/31", "1403/13/05", "1403/00/05", "1403/05/00"])
def test_invalid_jalali_dates_are_rejected_not_rolled_over(raw):
    assert CalendarEngine.parse(raw) is None
    assert jalali_sort_key(raw) == "0000-00-00"


def test_jalali_leap_year_and_esfand_30():
    assert [y for y in range(1395, 1410) if is_jalali_leap(y)] == [1395, 1399, 1403, 1408]
    assert CalendarEngine.parse("1403/12/30") == date(2025, 3, 20)
    assert CalendarEngine.parse("1405/07/04") == date(2026, 9, 26)


def test_internal_converter_round_trips_without_jdatetime(monkeypatch):
    monkeypatch.setattr(jalali, "HAS_JDATETIME", False)
    d = date(2020, 1, 1)
    while d < date(2030, 1, 1):
        assert jalali.jalali_to_gregorian(*gregorian_to_jalali(d)) == d
        d = date.fromordinal(d.toordinal() + 1)


def test_iso_timestamp_excel_serial_and_invisible_marks():
    assert CalendarEngine.parse("2026-07-26T10:00:00") == date(2026, 7, 26)
    assert CalendarEngine.parse("45371") == date(2024, 3, 20)       # OOXML date cell
    assert CalendarEngine.parse("45371.75") == date(2024, 3, 20)
    assert CalendarEngine.parse("12345") is None                    # not a plausible serial
    assert CalendarEngine.parse("‏1405/07/04") == date(2026, 9, 26)


# ── text / keys ─────────────────────────────────────────────────────────────
def test_keys_ignore_invisible_bidi_marks():
    assert clean_key("‏12345") == clean_key("12345‎") == "12345"
    assert clean_key("﻿AB-1") == "AB-1"
    assert normalize_persian_text("علی ى") == "علی ی"


# ── currencies ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, code", [
    ("دلار کانادا", "CAD"), ("دلار هنگ کنگ", "HKD"), ("Hong Kong Dollar", "HKD"),
    ("روپیه پاکستان", "PKR"), ("ریال عمان", "OMR"), ("ریال قطر", "QAR"),
    ("کرون سوئد", "SEK"), ("کرون نروژ", "NOK"), ("دلار", "USD"), ("دلار آمریکا", "USD"),
    ("ریال", "IRR"), ("یوروی اروپا", "EUR"), ("ین  ژاپن ", "JPY"), ("Yuan", "CNY"),
])
def test_currency_longest_name_wins(raw, code):
    from gsi.rulebook import get_rulebook
    assert get_rulebook().normalize_currency(raw) == code


def test_currency_ambiguous_or_unknown_is_never_merged():
    from gsi.rulebook import get_rulebook
    rb = get_rulebook()
    assert rb.normalize_currency("USD/EUR") == ""            # two currencies
    assert rb.normalize_currency("USDT") == "USDT"           # not USD
    assert rb.normalize_currency("کرون") == "کرون"           # kept whole, not "کرو"
    assert rb.normalize_currency("کرون سوئد") != rb.normalize_currency("کرون نروژ")


# ── commitment / FX stages: Unknown is not Zero ─────────────────────────────
def test_commitment_unparseable_balance_is_unknown_not_settled():
    from gsi.engines.commitment import CommitmentEngine
    res = CommitmentEngine().evaluate({"BALANCE": "در حال بررسی", "CB_DATE": "1405/01/10"}, date(2026, 9, 26))
    assert res.balance_is_unknown and math.isnan(res.outstanding)
    ok = CommitmentEngine().evaluate({"BALANCE": "1٬250٫5"}, date(2026, 9, 26))
    assert ok.outstanding == pytest.approx(1250.5) and not ok.balance_is_unknown


def test_credit_amounts_are_lc_deduped_and_currency_safe():
    from gsi.stages.s55_fx_traceability import _credit_amounts
    one_lc_twice = pd.DataFrame({"CRD_LC_NO": ["LC1", "LC1"], "CRD_CURRENCY": ["EUR", "EUR"],
                                 "CRD_PREPAYMENT": [100, 100], "CRD_PROFORMA_VALUE": [500, 500],
                                 "CRD_REMAINING": [50, 50]})
    out = _credit_amounts(one_lc_twice)
    assert out["CRD_PREPAYMENT"] == 100            # was 200 (snapshot double count)
    mixed = pd.DataFrame({"CRD_LC_NO": ["LC1", "LC2"], "CRD_CURRENCY": ["EUR", "CNY"],
                          "CRD_PREPAYMENT": [100, 700]})
    assert _credit_amounts(mixed)["CRD_PREPAYMENT"] is None   # was 800 EUR+CNY
    unknown = pd.DataFrame({"CRD_LC_NO": ["LC1"], "CRD_CURRENCY": ["EUR"], "CRD_PREPAYMENT": [None]})
    assert _credit_amounts(unknown)["CRD_PREPAYMENT"] is None  # was 0.0


def _money_flow(allocated_amount, deadline):
    from gsi.rulebook import get_rulebook
    from gsi.stages.base import PipelineContext
    from gsi.stages.s55_fx_traceability import FxTraceabilityStage
    from gsi.stages.s56_money_flow_control import MoneyFlowControlStage
    reg = "12345678"
    sources = {
        "ntsw": {
            "allocation": pd.DataFrame([{"KEY_REG": reg, "NTSW_REQ_CURRENCY": "EUR",
                                         "NTSW_ALLOCATED": True, "NTSW_ALLOCATED_AMOUNT": allocated_amount,
                                         "NTSW_OPEN_QUEUE_AMOUNT": 0.0, "NTSW_ALLOC_REQUESTS": 1,
                                         "NTSW_ALLOCATED_REQUESTS": 1, "NTSW_OPEN_REQUESTS": 0}]),
            "commitment": pd.DataFrame([{"KEY_REG": reg, "NTSW_INITIAL_COMMIT": 100, "NTSW_BALANCE": 20,
                                         "NTSW_CURRENCY": "EUR", "NTSW_DEADLINE": deadline,
                                         "NTSW_RELEASE_STATUS": "رفع تعهد نشده"}]),
        },
    }
    df = pd.DataFrame([{"CANONICAL_REG": reg}])
    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 21)),
                          today=date(2026, 9, 21), sources=sources)
    out = MoneyFlowControlStage().run(FxTraceabilityStage().run(df, ctx), ctx)
    return out, ctx


def test_unknown_allocation_amount_is_not_reported_as_zero():
    _, ctx = _money_flow(float("nan"), "2026-10-01")
    led = ctx.extras["fx_ledger"].iloc[0]
    assert pd.isna(led["FX_ALLOCATED_AMOUNT"]) and pd.isna(led["FX_ALLOC_REQUEST_AMOUNT"])
    _, ctx = _money_flow(100.0, "2026-10-01")
    assert ctx.extras["fx_ledger"].iloc[0]["FX_ALLOCATED_AMOUNT"] == 100.0


def test_days_remaining_is_unknown_without_a_deadline():
    out, _ = _money_flow(100.0, "")
    row = out.iloc[0]
    if not str(row.get("FX_DEADLINE_DATE") or "").strip():
        assert pd.isna(row["FX_DAYS_REMAINING"])      # was 0 = "due today"


def test_process_explorer_dates_use_gsi_calendar():
    from gsi.cashflow.process_design import _date_value
    assert _date_value("1403/05/12") == "2024-08-02T00:00:00"   # was lost (NaT)
    assert _date_value("05/03/2026") == "2026-03-05T00:00:00"   # D/M/Y like the ledger


def test_is_empty_val_handles_pandas_na_without_crashing():
    # 29.8.2 raised "TypeError: boolean value of NA is ambiguous"; stages write
    # pd.NA into nullable numeric columns and then read them back with _s().
    assert is_empty_val(pd.NA) and is_empty_val(pd.NaT) and is_empty_val(float("nan"))
    assert not is_empty_val(0, treat_zero_as_empty=False) and is_empty_val("0")


def test_placeholder_registration_file_numbers_never_bridge_orders():
    from gsi.resolve.registration_bridge import build_ntsw_order_reg_bridge
    lic = pd.DataFrame({"KEY_REG_FILE": ["0", "664823825"], "NTSW_KEY_REG": ["11111111", "33333333"],
                        "KEY_ORDER": ["", ""]})
    il = pd.DataFrame({"KEY_REG_FILE": ["0", "0", "000", "664823825"],
                       "KEY_ORDER": ["500001", "500002", "500004", "500003"]})
    res, diag = build_ntsw_order_reg_bridge({"ntsw": {"import_license": lic}, "ilappend": {"main": il}})
    # 29.8.2 mapped 500001, 500002 and 500004 to REG 11111111 through file "0".
    assert res.set_index("KEY_ORDER")["NTSW_KEY_REG"].to_dict() == {"500003": "33333333"}
    assert diag.empty

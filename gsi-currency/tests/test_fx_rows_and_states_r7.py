# -*- coding: utf-8 -*-
"""دور ۷ — ردیف درست، نه ردیف اول یا باطل.

پس از گزارش مالک (ارز ثبت سفارش از اولین درخواست تخصیص، که باطل شده بود) همه جاهایی که یک
ردیف را به‌جای ردیف درست برمی‌داشتند بررسی شد. این آزمون‌ها هر اصلاح را قفل می‌کنند:

* وضعیت «آماده براي تخصيص» با فرایند «اتمام» درخواست باز است، نه بسته یا تخصیص‌یافته؛
* وضعیت نمایشی پرونده از درخواست زنده می‌آید، نه از آخرین درخواست ردشده؛
* مهلت تعهد از تعهدهای باز می‌آید، نه از تعهد رفع‌شده قدیمی؛
* قیف چرخه خرید درخواست ردشده را «تخصیص» و مانده نامعلوم را «رفع تعهد» نمی‌شمارد؛
* صف تخصیص با درخواست‌های فقط رد یا باطل‌شده «انجام شد» نیست؛
* اعتبار اسنادی ابطال‌شده مبنای ارزش ثبت سفارش یا جمع اعتبار نیست؛
* در فایل خرید ارز ۱۴۰۵ نرخ ارز پروفرم کنار مبلغ خرید نمی‌نشیند، خط تکراری یک رکورد دوبار
  جمع نمی‌شود و مبلغ ریالی مشترک یک رکورد یک بار شمرده می‌شود؛
* خرید «دربرنامه» در جدول تخت جای خرید انجام‌شده نمی‌نشیند.

همه داده‌ها ساختگی‌اند.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext


def test_ready_for_allocation_with_finished_process_is_an_open_request():
    from gsi.adapters.a50_ntsw import request_state
    assert request_state("آماده براي تخصيص", "اتمام", "") == "OPEN"
    assert request_state("منتظر بررسي بانک", "اتمام", "1404/05/03") == "OPEN"
    assert request_state("تخصيص يافته", "اتمام", "") == "ALLOCATED"
    for status in ("پذيرفته نشده", "رد شده", "ابطال", "باطل شده"):
        assert request_state(status, "اتمام", "1404/05/03") == "REJECTED"
    assert request_state("", "اتمام", "") == "CLOSED"
    assert request_state("", "", "1404/05/03") == "ALLOCATED"


def _request(p, reg, no, status, ccy, created, allocated=""):
    return {"KEY_REG": reg, p("REQ_ROW"): no, p("REQ_AMOUNT"): 100, p("REQ_CURRENCY"): ccy,
            p("REQ_DATE"): created, p("APPROVE_DATE"): "", p("ALLOC_DATE"): allocated,
            p("ALLOC_STATUS"): status, p("ALLOC_PROCESS"): "اتمام", p("REQ_TYPE"): "", p("QUEUE_RANK"): "",
            p("FX_SOURCE"): "", p("FX_RATE_TYPE"): "", p("FX_RATE_NUMERIC"): None, p("ALLOC_BRANCH"): ""}


def test_registration_status_comes_from_the_live_request_not_a_later_rejection():
    from gsi.adapters.a50_ntsw import NtswAdapter
    a = NtswAdapter()
    p = a.p
    raw = pd.DataFrame([_request(p, "88000002", "1", "تخصيص يافته", "USD", "2026-01-01", "2026-01-05"),
                        _request(p, "88000002", "2", "پذيرفته نشده", "EUR", "2026-02-01")])
    s = a._agg_allocation(a._allocation_request_ledger(raw)).iloc[0]
    assert s[p("ALLOC_STATUS")] == "تخصيص يافته"
    assert s[p("LAST_REQUEST_STATUS")] == "پذيرفته نشده"
    assert s[p("REQ_CURRENCY")] == "USD"


def test_commitment_deadline_comes_from_open_rows_not_an_old_released_row():
    from gsi.adapters.a50_ntsw import NtswAdapter
    a = NtswAdapter()
    p = a.p

    def row(no, balance, created, deadline, status):
        return {"KEY_REG": "88000003", p("COMMIT_ROW"): no, p("CURRENCY"): "EUR", p("INITIAL_COMMIT"): 100.0,
                p("BALANCE"): balance, p("COMMIT_DATE"): created, p("DEADLINE"): deadline,
                p("RELEASE_STATUS"): status, p("BRANCH"): "", p("COMPANY"): ""}

    s = a._agg_commitment(pd.DataFrame([row("1", 0.0, "2023-01-01", "2024-01-01", "رفع تعهد شده"),
                                        row("2", 50.0, "2026-03-01", "2027-03-01", "رفع تعهد نشده")])).iloc[0]
    assert s[p("DEADLINE")] == "2027-03-01"
    assert s[p("COMMIT_DATE")] == "2026-03-01"


def test_lifecycle_funnel_counts_only_real_allocations_and_known_zero_balances():
    from gsi.report.insight import LIFECYCLE, _stage_counts
    g = pd.DataFrame([
        {"ALLOC_STATUS": "پذيرفته نشده", "ALLOCATED_REQUESTS": 0, "ALLOCATED": False, "مانده تعهد": None},
        {"ALLOC_STATUS": "تخصيص يافته", "ALLOCATED_REQUESTS": 1, "ALLOCATED": True, "مانده تعهد": 0.0},
        {"ALLOC_STATUS": "", "ALLOCATED_REQUESTS": 0, "ALLOCATED": False, "مانده تعهد": 120.0},
    ])
    counts = dict(zip([code for code, _, _ in LIFECYCLE], _stage_counts(g)))
    assert counts["ALLOC"] == 1
    assert counts["RELEASE"] == 1


def test_material_view_flags_a_rejection_written_with_arabic_yeh():
    from gsi.report.supply_views import _ntsw_advisory
    alert, _ = _ntsw_advisory(pd.DataFrame([{"NTSW_ALLOC_STATUS": "پذيرفته نشده"},
                                            {"NTSW_ALLOC_STATUS": "تخصيص يافته"}]))
    assert "وضعیت تخصیص NTSW نیازمند بررسی است" in alert.iloc[0]
    assert "وضعیت تخصیص" not in alert.iloc[1]


def test_queue_is_not_done_when_every_request_was_rejected_or_void():
    from gsi.stages.s55_fx_traceability import FxTraceabilityStage
    from gsi.stages.s56_money_flow_control import MoneyFlowControlStage
    reg = "88000006"
    rows = pd.DataFrame([
        {"KEY_REG": reg, "NTSW_REQUEST_KEY": "R1", "NTSW_REQ_AMOUNT": 100, "NTSW_REQ_CURRENCY": "CNY",
         "NTSW_REQ_DATE": "2026-03-01", "NTSW_ALLOC_DATE": "2026-03-03", "NTSW_REQUEST_STATE": "REJECTED",
         "NTSW_ALLOC_STATUS": "باطل شده"},
        {"KEY_REG": reg, "NTSW_REQUEST_KEY": "R2", "NTSW_REQ_AMOUNT": 100, "NTSW_REQ_CURRENCY": "EUR",
         "NTSW_REQ_DATE": "2026-04-01", "NTSW_ALLOC_DATE": "", "NTSW_REQUEST_STATE": "REJECTED",
         "NTSW_ALLOC_STATUS": "پذيرفته نشده"}])
    summary = pd.DataFrame([{"KEY_REG": reg, "NTSW_ALLOC_REQUESTS": 2, "NTSW_OPEN_REQUESTS": 0,
                             "NTSW_ALLOCATED_REQUESTS": 0, "NTSW_REJECTED_REQUESTS": 2, "NTSW_ALLOCATED": False,
                             "NTSW_REQ_DATE": "2026-04-01", "NTSW_ALLOC_STATUS": "پذيرفته نشده"}])
    sources = {"ntsw": {"allocation_rows": rows, "allocation": summary},
               "ilappend": {"main": pd.DataFrame([{"KEY_REG": reg, "IL_REG_DATE": "2026-02-01"}])}}
    df = pd.DataFrame([{"CANONICAL_REG": reg, "CANONICAL_ORDER": "O6", "CANONICAL_BL": ""}])
    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 21)), today=date(2026, 9, 21),
                          sources=sources)
    MoneyFlowControlStage().run(FxTraceabilityStage().run(df, ctx), ctx)
    t = ctx.extras["fx_stage_timeline"]
    t = t[t["KEY_REG"].eq(reg)].set_index("STAGE_CODE")
    assert t.loc["ALLOCATION_QUEUE", "STATUS"] != "DONE"
    assert t.loc["ALLOCATION_QUEUE", "EVENT_DATE"] == ""
    assert "درخواست زنده‌ای نیست" in t.loc["ALLOCATION_QUEUE", "EVIDENCE"]
    assert t.loc["ALLOCATION", "STATUS"] != "DONE"


def test_void_letter_of_credit_is_not_the_registration_value_or_the_credit_total():
    from gsi.finance.registration import currency_coder, registration_values
    from gsi.stages.s55_fx_traceability import _credit_amounts
    reg = "88000007"
    credit = pd.DataFrame([
        {"KEY_REG": reg, "CRD_PROFORMA_VALUE": 900.0, "CRD_CURRENCY": "CNY", "CRD_LAST_STATUS": "ابطال شده",
         "CRD_LC_NO": "LC-OLD"},
        {"KEY_REG": reg, "CRD_PROFORMA_VALUE": 120.0, "CRD_CURRENCY": "EUR", "CRD_LAST_STATUS": "گشایش شده",
         "CRD_LC_NO": "LC-NEW"}])
    frames = {("credit", "main"): credit}
    value = registration_values(lambda source, frame: frames.get((source, frame)), currency_coder())[reg]
    assert (value["value"], value["currency"]) == (120.0, "EUR")
    totals = _credit_amounts(credit)
    assert totals["currency"] == "EUR"
    assert totals["CRD_PROFORMA_VALUE"] == 120.0


def _fx_1405(rows):
    head = {"تاريخ خريد": "1405/01/10", "نام بانک": "بانک نمونه", "وضعیت": "مختومه شد"}
    df = pd.DataFrame([{**head, **r} for r in rows])
    df["_SOURCE_ROW"] = range(2, 2 + len(df))
    df["_SOURCE_SHEET"] = "خرید جاری"
    df["_SOURCE_FILE_ID"] = "synthetic-1405"
    return df


def _line(record, order, reg, proforma, ccy, rate, rial, bought):
    return {"ردیف": record, "سفارش": order, "ثبت سفارش": reg, "مبلغ ارز پروفرم": proforma, "نوع ارز": ccy,
            "نرخ ارز": rate, "مبلغ ریالی": rial, "ارز خريداري شده": bought, "نوع ارز خريداري شده": "USD"}


def test_fx_1405_rate_duplicate_line_and_shared_rial_total():
    from gsi.adapters.a60_finance import FxTransactionAdapter
    out = FxTransactionAdapter().transform({"خرید جاری": _fx_1405([
        # «نرخ ارز» = مبلغ ریالی ÷ مبلغ پروفرم: نرخ ریالی یوان، نه نرخ دلار خریداری‌شده
        _line("1", "900001", "11110001", "1000000", "CNY", "300000", "300000000000", "140000"),
        # یک رکورد در دو خط (دو خرید) با یک «مبلغ ریالی» کل
        _line("2", "900002", "11110002", "400000", "CNY", "750000", "300000000000", "56000"),
        _line("2", "900002", "11110002", "600000", "CNY", "500000", "300000000000", "84000"),
        # خط دوم عیناً همان خط اول است: یک خرید، نه دو خرید
        _line("3", "900003", "11110003", "500000", "EUR", "900000", "450000000000", "580000"),
        _line("3", "900003", "11110003", "500000", "EUR", "900000", "450000000000", "580000"),
    ])})
    m = out["main"].set_index("FX_RECORD_NO", append=True)
    main = out["main"]
    assert main["FX_CURRENCY"].eq("USD").all()
    assert main["FX_RATE"].isna().all()
    assert main.loc[main["KEY_REG"].eq("11110001"), "FX_PROFORMA_RATE"].iloc[0] == 300000.0
    # خط تکراری قرنطینه شد و مبلغ خرید یک بار ماند
    assert main.loc[main["KEY_REG"].eq("11110003"), "FX_AMOUNT"].tolist() == [580000.0]
    assert out["quarantine"]["_QUARANTINE_REASON"].tolist() == ["DUPLICATE_LINE_SAME_RECORD"]
    # مبلغ ریالی مشترک رکورد دوخطی یک بار شمرده می‌شود
    two = main[main["KEY_REG"].eq("11110002")]
    assert two["FX_RIAL_SCOPE"].eq("RECORD_TOTAL").all()
    assert two["FX_RIAL_VALUE"].sum() == 300000000000.0
    assert two["FX_RIAL_VALUE"].notna().sum() == 1
    assert len(m) == 4


def test_record_total_rial_is_counted_once_and_never_used_as_a_line_rate():
    from gsi.finance.equivalents import _weighted_ratio, summarize_fx_purchases
    lines = pd.DataFrame([
        {"KEY_REG": "R9", "FX_AMOUNT": 40.0, "FX_CURRENCY": "USD", "FX_RIAL_VALUE": 1000.0,
         "FX_RIAL_SCOPE": "RECORD_TOTAL", "FX_PURCHASE_STATE": "SOURCE_OBSERVED"},
        {"KEY_REG": "R9", "FX_AMOUNT": 60.0, "FX_CURRENCY": "USD", "FX_RIAL_VALUE": None,
         "FX_RIAL_SCOPE": "RECORD_TOTAL", "FX_PURCHASE_STATE": "SOURCE_OBSERVED"}])
    s = summarize_fx_purchases(lines)
    assert s.source_rial_total == 1000.0
    assert s.rial_coverage_pct == 100.0
    rate, eligible, usable = _weighted_ratio(lines, "FX_RIAL_VALUE")
    assert rate is None and eligible == 2 and usable == 0


def test_planned_purchase_never_fills_purchase_fields_of_the_flat_row():
    from gsi.pipeline import _executed_fx_first
    fx = pd.DataFrame([
        {"KEY_REG": "R1", "FX_BUY_DATE": "1405/02/01", "FX_AMOUNT": 100.0, "FX_CURRENCY": "EUR",
         "FX_STATUS": "خرید ارز شد", "FX_PURCHASE_STATE": "SOURCE_OBSERVED"},
        {"KEY_REG": "R1", "FX_BUY_DATE": "1405/05/01", "FX_AMOUNT": 900.0, "FX_CURRENCY": "USD",
         "FX_STATUS": "دربرنامه خرید", "FX_PURCHASE_STATE": "PLANNED"},
        {"KEY_REG": "R2", "FX_BUY_DATE": "1405/05/01", "FX_AMOUNT": 700.0, "FX_CURRENCY": "USD",
         "FX_STATUS": "دربرنامه خرید", "FX_PURCHASE_STATE": "PLANNED"}])
    out = _executed_fx_first(fx)
    r1 = out[out["KEY_REG"].eq("R1")]
    assert r1["FX_AMOUNT"].tolist() == [100.0]
    r2 = out[out["KEY_REG"].eq("R2")].iloc[0]
    assert r2["FX_STATUS"] == "دربرنامه خرید"
    assert pd.isna(r2["FX_AMOUNT"]) and r2["FX_BUY_DATE"] == "" and r2["FX_CURRENCY"] == ""

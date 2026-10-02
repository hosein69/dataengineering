# -*- coding: utf-8 -*-
"""دور ۷ — مبلغ دو ارز، یا مبلغی که ارزش معلوم نیست، هرگز یک عدد نمی‌شود.

پس از گزارش مالک (عدد یورو با برچسب یوان) هر جایی که مبلغ‌ها جمع، مقایسه یا تقسیم می‌شدند
بررسی شد. این آزمون‌ها هر اصلاح را قفل می‌کنند:

* خلاصه عددی، صحت محاسبات، جدول محوری و کارت HTML «مانده تعهد» را به تفکیک ارز جمع می‌زنند؛
* «یورو» و «EUR» یک ارزند و «نامشخص» یا «حواله» ارز نیستند (سنجش ناهنجاری، معادل‌ها، کارشناسان)؛
* کاشی صف تخصیص مبلغ‌های بی‌ارز را جمع نمی‌زند؛
* جریان وجوه مبلغ بی‌ارز را در جمع نمی‌آورد و ارزش ثبت سفارش را از ایمپورت لایسنس می‌گیرد؛
* سنجش اعتماد منبع‌ها مبلغ بی‌ارز را در سطل «—» جمع نمی‌زند؛
* جمع مبلغ‌های انبار داده درخواست رد یا باطل و ارز نامعلوم را کنار می‌گذارد؛
* «مانده حمل‌نشده» وقتی بخشی از حمل نامعلوم است «حداکثر» است؛
* امتیاز ریسک جریمه یوانی را بر ارزش دلاری تقسیم نمی‌کند.

همه داده‌ها ساختگی‌اند.
"""
from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pandas as pd

from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext


def _commitments() -> pd.DataFrame:
    """یک ثبت سفارش یوانی روی دو بارنامه، دو یورو و یکی با ارز «نامشخص»."""
    return pd.DataFrame({
        "KEY_REG": ["R1", "R1", "R2", "R3", "R4"],
        "CANONICAL_REG": ["R1", "R1", "R2", "R3", "R4"],
        "KEY_BL": ["B1", "B2", "B3", "B4", "B5"],
        "مانده تعهد": [13_000_000, 13_000_000, 1000, 500, 250],
        "NTSW_CURRENCY": ["یوان چین", "CNY", "EUR", "نامشخص", "EUR"],
        "dept": ["A", "A", "A", "B", "B"],
    })


# ═══════════════════════════ Studio ═══════════════════════════
def test_studio_summary_and_integrity_split_a_money_column_by_currency():
    from gsi.studio_core import grain as G
    row = G.summarize(_commitments(), ["مانده تعهد"]).iloc[0]
    assert row["جمع"] is None and row["میانگین"] is None and row["بیشینه"] is None
    # R1 یک بار (دانه ثبت سفارش)، «یوان چین» همان CNY، و «نامشخص» بیرون از جمع
    assert row["جمع به تفکیک ارز"] == "13,000,000.00 CNY | 1,250.00 EUR · 1 ردیف با ارز نامعلوم خارج از جمع"
    check = G.integrity_report(_commitments(), ["مانده تعهد"]).iloc[0]
    assert check["جمع درست (دانه‌ای)"] is None and "چند ارز" in check["وضعیت"]
    one = _commitments()[lambda d: d["NTSW_CURRENCY"].eq("EUR")]
    assert G.summarize(one, ["مانده تعهد"]).iloc[0]["جمع"] == 1250


def test_studio_pivot_puts_each_currency_in_its_own_column():
    from app.analytics import _pivot
    pv = _pivot(_commitments(), "dept", None, "sum", "مانده تعهد")
    assert list(pv.columns) == ["CNY", "EUR"]
    assert pv.loc["A", "CNY"] == 13_000_000 and pv.loc["A", "EUR"] == 1000 and pv.loc["B", "EUR"] == 250
    assert pv.attrs["unknown_currency_rows"] == 1


def test_studio_html_cards_sum_money_per_currency():
    from gsi.studio_core.html_export import build_dynamic_html
    page = build_dynamic_html(_commitments(), "1405/07/06",
                              tabs=[{"title": "تعهد", "fields": ["مانده تعهد", "dept", "KEY_REG"],
                                     "blocks": ["kpi", "table"]}])
    assert re.search(r'"ccy"\s*:\s*\{"مانده تعهد"\s*:\s*"__CCY__NTSW_CURRENCY"\}', page)
    assert "function gaggCcy" in page


# ═══════════════════════════ ارز ناشناخته ارز نیست ═══════════════════════════
def test_unknown_currency_text_forms_no_peer_group_and_spellings_are_one_currency():
    from gsi.finance.equivalents import _currency
    from gsi.trust.anomaly import _normalizer_for_group
    norm = _normalizer_for_group("INVOICE_CURRENCY")
    assert [norm(v) for v in ("یورو", "EUR", "نامشخص", "حواله")] == ["EUR", "EUR", "", ""]
    assert [_currency(v) for v in ("یورو", "EUR", "نامشخص", "")] == ["EUR", "EUR", "", ""]


def test_expert_order_with_two_currencies_or_unknown_text_has_no_pi_sum():
    from gsi.adapters.moghavemat import MoghavematAdapter

    def line(no, order, ccy, value=100):
        return {"Row No.": no, "Order No. (Our Reference)": order, "Material": f"M{no}",
                "Material Description": "قطعه", "Quantity In Order": 1, "PI Line Value": value, "Currency": ccy}
    raw = pd.DataFrame([line(1, "O1", "EUR"), line(2, "O1", "یورو"),
                        line(3, "O2", "EUR"), line(4, "O2", "CNY"),
                        line(5, "O3", "نامشخص"), line(6, "O3", "نامشخص")])
    main = MoghavematAdapter().transform({"Expert Data": raw})["main"].drop_duplicates("KEY_ORDER").set_index("KEY_ORDER")
    assert main.loc["O1", "MOGH_CURRENCY"] == "EUR" and main.loc["O1", "MOGH_PI_VALUE_SUM"] == 200
    for order in ("O2", "O3"):
        assert main.loc[order, "MOGH_CURRENCY"] == "" and pd.isna(main.loc[order, "MOGH_PI_VALUE_SUM"])


def test_queue_tile_counts_unknown_currency_cases_instead_of_summing_them():
    from gsi.report.fx_html import queue_section
    q = pd.DataFrame({"KEY_REG": ["R1", "R2", "R3", "R4"], "CURRENCY": ["یورو", "EUR", "نامشخص", "حواله"],
                      "OPEN_AMOUNT": [100, 50, 7, 9], "QUEUE_STATE": ["IN_QUEUE"] * 4,
                      "QUEUE_RANK": [1, 2, 3, 4], "WAIT_DAYS": [3, 4, 5, 6]})
    page = queue_section(SimpleNamespace(queue=q))
    assert "مبلغ باز صف (EUR)" in page and "150.00" in page
    assert "پرونده صف با ارز نامعلوم" in page and "16.00" not in page


# ═══════════════════════════ جریان وجوه ═══════════════════════════
def _event(eid, kind, amount, currency, **kw):
    e = {"event_id": eid, "case_id": "R1", "kind": kind, "date": "2026-07-01", "amount": amount,
         "currency": currency, "status": "SOURCE_FACT", "document": "doc-" + eid, "source": "test"}
    e.update(kw)
    return e


def test_cash_flow_keeps_a_step_without_currency_but_never_sums_its_amount():
    from gsi.cashflow.engine import build_cashflow
    from gsi.cashflow.process_design import _amounts
    events = pd.DataFrame([_event("E1", "REGISTRATION", "1000", ""), _event("E2", "QUEUE", "700", ""),
                           _event("E3", "QUEUE", "300", "")])
    res = build_cashflow(events, as_of="2026-09-22")
    assert int(res["issues"]["code"].eq("AMOUNT_WITHOUT_CURRENCY").sum()) == 3
    assert len(res["events"]) == 3                          # گام‌ها ثبت شدند
    s = res["summary"]
    assert s.empty or (s["registration_value"].isna().all() and s["allocation_requested"].isna().all())
    chain = res["chain"].set_index("stage")
    assert chain.loc["PI", "status"] == chain.loc["ALLOCATION_REQUEST", "status"] == "EVIDENCED"
    assert chain.loc["PI", "amounts"] == chain.loc["ALLOCATION_REQUEST", "amounts"] == "?"
    assert _amounts([{"amount": 5, "currency": ""}, {"amount": 7, "currency": ""},
                     {"amount": 3, "currency": "EUR"}]) == "3.0 EUR | 2 مبلغ بی‌ارز"


# ═══════════════════════════ سنجش اعتماد منبع‌ها ═══════════════════════════
def test_fitness_never_adds_amounts_without_a_known_currency():
    from gsi.trust.fitness import DecisionContract, FitnessVerdict, evaluate
    profile = SimpleNamespace(states={k: {"مانده تعهد": "OK"} for k in ("R1", "R2", "R3", "R4")})
    df = pd.DataFrame({"KEY_REG": ["R1", "R2", "R3", "R4"], "مانده تعهد": [100, 200, 300, 400],
                       "CCY": ["EUR", "یورو", "نامشخص", ""]})
    contract = DecisionContract(id="T", title_fa="جمع", question_fa="؟", entity_type="REG",
                                required=("مانده تعهد",), amount_field="مانده تعهد", currency_field="CCY")
    v: FitnessVerdict = evaluate(contract, profile, df, "KEY_REG")
    assert v.known_total == {"EUR": 300.0}                  # نه سطل «—» با ۷۰۰ و نه سطر «نامشخص»
    assert v.unknown_currency == 2
    assert "2 پرونده با ارز نامعلوم خارج از جمع" in v.total_display()


# ═══════════════════════════ انبار داده ═══════════════════════════
def test_warehouse_totals_leave_out_rejected_requests_and_unknown_currency():
    from gsi.warehouse import marts
    from gsi.warehouse.store import Warehouse
    wh = Warehouse()
    alloc = pd.DataFrame([
        {"کد ثبت سفارش": "R1", "وضعیت": "باطل شده", "فرآیند فعلی": "اتمام", "مبلغ درخواست": "900", "ارز درخواست": "یوان"},
        {"کد ثبت سفارش": "R1", "وضعیت": "پذيرفته نشده", "فرآیند فعلی": "اتمام", "مبلغ درخواست": "800", "ارز درخواست": "یورو"},
        {"کد ثبت سفارش": "R1", "وضعیت": "تخصيص يافته", "فرآیند فعلی": "اتمام", "مبلغ درخواست": "700", "ارز درخواست": "یورو"},
        {"کد ثبت سفارش": "R2", "وضعیت": "آماده براي تخصيص", "فرآیند فعلی": "اتمام", "مبلغ درخواست": "50", "ارز درخواست": "نامشخص"},
    ])
    alloc["_SOURCE_ROW"] = range(2, 2 + len(alloc))
    with wh.run({"reference_date": "1405-07-06"}):
        fid = wh.blob(b"fixture", "fixture.xlsx", "ntsw", "/fixture.xlsx")
        marts.stage(alloc, "ntsw", "Allocation", fid)
    got = {r["currency"]: r for r in marts.totals(fid)}
    assert got["یورو"]["known_total"] == "700" and got["یورو"]["rejected_request_rows"] == 1
    assert got["یوان"]["known_total"] is None and got["یوان"]["rejected_request_rows"] == 1
    assert got["نامشخص"]["known_total"] is None and got["نامشخص"]["unresolved_rows"] == 1


# ═══════════════════════════ مانده حمل‌نشده ═══════════════════════════
def test_stage_values_say_when_the_unshipped_balance_is_an_upper_bound():
    from gsi.report import fx_insight as X
    from gsi.report.fx_html import _values_html
    table = pd.DataFrame({"KEY_REG": ["R1", "R2"], "STAGE_CODE": ["CLEARANCE"] * 2, "REG_CURRENCY": ["EUR"] * 2,
                          "REG_VALUE": [1000.0, 500.0], "SHIPPED_VALUE": [600.0, 500.0],
                          "UNSHIPPED_VALUE": [400.0, 0.0], "SHIPPED_IS_LOWER_BOUND": [True, False],
                          "CRITICAL_LEVEL": ["", ""]})
    v = X.stage_values(SimpleNamespace(reg_table=table))
    eur = v.set_index("CURRENCY").loc["EUR"]
    assert eur["UNSHIPPED_VALUE"] == 400 and eur["UNSHIPPED_UPPER_BOUND_REGS"] == 1
    assert "مانده حمل‌نشده (حداکثر)" in _values_html(v.to_dict("records"), "fa")


# ═══════════════════════════ ریسک ═══════════════════════════
def test_penalty_exposure_divides_only_by_a_value_in_the_penalty_currency():
    from gsi.engines.risk import PENALTY_BASE, RiskScoreEngine
    from gsi.stages.s70_risk import RiskStage
    rb = get_rulebook()
    df = pd.DataFrame({"CB_VALUE": [1000.0, 1000.0, 1000.0],
                       "CB_CURRENCY": ["USD", "USD", "USD"],
                       "NTSW_CURRENCY": ["USD", "یوان", "نامشخص"],
                       "NTSW_INITIAL_COMMIT": [1000.0, 7000.0, 500.0]})
    bases = RiskStage._penalty_bases(df, df["CB_VALUE"], PipelineContext(rb=rb, today=date(2026, 9, 1)))
    # هم‌ارز: CB_VALUE؛ جریمه یوانی: تعهد اولیه یوانی؛ ارز تعهد نامعلوم: مبنا نیست
    assert bases == [1000.0, 7000.0, None]
    engine = RiskScoreEngine(max_cb_value=1000, rb=rb)
    ratio = float(rb.get("alarms.risk_engine.penalty_exposure_base_ratio", 0.10))
    f = engine.score({"CB_VALUE": 1000, "PENALTY": 35, PENALTY_BASE: 7000.0}).factors
    assert abs(f["penalty_exposure"] - min(100.0, 35 / (7000 * ratio) * 100)) < 1e-9
    assert engine.score({"CB_VALUE": 1000, "PENALTY": 35, PENALTY_BASE: None}).factors["penalty_exposure"] == 100

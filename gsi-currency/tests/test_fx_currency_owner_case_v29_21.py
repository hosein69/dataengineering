# -*- coding: utf-8 -*-
"""29.21 — پرونده‌ای که مالک پیدا کرد: ارز ثبت سفارش از ایمپورت لایسنس و IL Append، نه از تخصیص.

داده ساختگی است (نه داده واقعی) ولی شکل پرونده همان است: ثبت سفارش یورو در ایمپورت لایسنس و
IL Append، خرید ارز یورو، فاکتور ساتا یورو با همان عدد؛ تخصیص سه بار: یوان (اولین درخواست،
باطل‌شده، حتی با تاریخ تخصیص)، یورو (پذیرفته نشده) و دلار (تخصیص یافته؛ برات دلاری آن زمان مجاز
بود). تعهد NTSW یک ردیف یوان و یک ردیف دلار دارد.

تا 29.20 گزارش ارز ثبت سفارش را یوان نشان می‌داد (از تعهد NTSW درخواست باطل) و عدد آن را با
فاکتور یورو یکی می‌گرفت. قاعده‌های مالک که این آزمون قفل می‌کند:
  * ارز و مبلغ ثبت سفارش فقط از ایمپورت لایسنس و IL Append (بعد پروفرم اعتبارات)؛
  * درخواست رد یا باطل‌شده نه ارزی تعیین می‌کند، نه تخصیص است، نه تقاضا؛
  * ارز تخصیص، خرید یا تعهد اگر فرق دارد کنار هم گزارش می‌شود و ادغام نمی‌شود؛
  * مبلغ‌های دو ارز هرگز هم‌ارز، جمع یا مقایسه نمی‌شوند؛ متن ناشناخته ارز نیست.
"""
from __future__ import annotations

import importlib.util
import os
import tempfile
from datetime import date

import pandas as pd

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gsi_make_synthetic_owner_fx",
                                               os.path.join(_TESTS_DIR, "make_synthetic.py"))
_ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ms)

REG = _ms.REGS[1]
AMOUNT = 2726378.4
_X = "2726378.4"


def _rewrite(path, edit):
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    edit(sheets)
    with pd.ExcelWriter(path) as w:
        for name, frame in sheets.items():
            frame.to_excel(w, sheet_name=name, index=False)


def _request(row, no, status, ccy, created, allocated, approved):
    return {"ردیف": row, "کد ثبت سفارش": REG, "ردیف درخواست": no, "وضعیت": status, "فرآیند فعلی": "اتمام",
            "مبلغ درخواست": _X, "ارز درخواست": ccy, "تاریخ ایجاد درخواست": created, "تاریخ تخصیص": allocated,
            "محل تامین ارز": "سامانه نیما", "نرخ ارز": "آزاد", "نوع درخواست": "اصل", "شعبه": "واحد ارزی قرنی",
            "تاریخ تایید": approved, "شرکت": "IKCO"}


def _owner_case(d):
    def ntsw(sheets):
        alloc = sheets["Allocation"].fillna("")
        sheets["Allocation"] = pd.concat([alloc[alloc["کد ثبت سفارش"] != REG], pd.DataFrame([
            _request("11", "1", "باطل شده", "یوان چین", "1404/05/01", "1404/05/03", ""),
            _request("12", "2", "پذیرفته نشده", "یورو", "1404/05/20", "", ""),
            _request("13", "3", "تخصیص یافته", "دلار آمریکا", "1404/06/01", "1404/06/05", "1404/06/04"),
        ])], ignore_index=True)
        commit = sheets["Release Commitment"].fillna("")
        sheets["Release Commitment"] = pd.concat([commit[commit["کد ثبت سفارش"] != REG], pd.DataFrame([
            {"ردیف": f"2{i}", "کد ثبت سفارش": REG, "شماره ردیف تعهد": str(i + 1), "شعبه": "بانک شهر", "ارز": c,
             "تعهد اولیه": _X, "مانده تعهد": _X, "تاریخ ایجاد تعهد": "1404/06/05", "مهلت رفع تعهد": "1405/06/05",
             "وضعیت رفع تعهد": "رفع تعهد نشده", "شرکت": "IKCO"}
            for i, c in enumerate(["یوان چین", "دلار آمریکا"])])], ignore_index=True)
        sheets["Import Licence"] = pd.DataFrame({
            "شماره پرونده": ["664823825", "664851493", "664851595"],
            "شماره پیش فاکتور": ["PI-1", "PI-2", "PI-3"],
            "تاریخ صدور ثبت سفارش": ["1403/02/07", "1404/02/07", "1405/02/07"],
            "مبلغ کل پیش فاکتور": ["13554250", _X, "300000"],
            "نوع ارز": ["یوان چین", "یورو", "درهم امارات"],
            "نوع عملیات ارزی": ["بانکی"] * 3, "وضعیت": ["تایید شده"] * 3,
            "شماره ثبت سفارش": _ms.REGS[:3]})

    def il_append(sheets):
        a = sheets["Append"].fillna("")
        a["ارزش ثبت سفارش"] = ["13554250", _X, "300000"]
        a["نوع ارز "] = ["یوان چین", "یورو", "درهم"]
        sheets["Append"] = a

    def credit(sheets):
        c = sheets["PURCREDIT"].fillna("")
        sheets["PURCREDIT"] = c[c["شماره ثبت سفارش"] != REG]

    def sata(sheets):
        s = sheets["Sata Tracking"].fillna("")
        s.loc[s["ثبت سفارش"] == REG, ["ارزش فاکتور", "_نوع ارز_"]] = [_X, "EUR"]
        sheets["Sata Tracking"] = s

    _rewrite(os.path.join(d["foreign"], "NTSW Export.xlsx"), ntsw)
    _rewrite(os.path.join(d["foreign"], "IL Append.xlsx"), il_append)
    _rewrite(os.path.join(d["foreign"], "Credit Dept.xlsx"), credit)
    _rewrite(os.path.join(d["bls"], "SATA Tracking.xlsx"), sata)
    os.replace(os.path.join(d["foreign"], "Foreign Exchange Transaction.xlsx"),
               os.path.join(d["foreign"], "IKCO, Foreign Exchange Transaction.xlsx"))
    return d


# conftest منابع و تنظیمات را برای ماژولی که DIRS دارد به همین پوشه می‌بندد
DIRS = _owner_case(_ms.build(tempfile.mkdtemp(prefix="gsi_owner_fx_")))
_RUN: dict = {}


def _run() -> dict:
    """یک اجرای کامل برای همه آزمون‌های پرونده (داخل اولین آزمون، تا منابع بسته باشند)."""
    if not _RUN:
        from gsi.pipeline import Pipeline
        pipe = Pipeline()
        res = pipe.run(build_report=False)
        _RUN.update(res=res, sources=pipe.sources, dwh=os.environ["GSI_DWH_PATH"])
    return _RUN


def _mine(frame: pd.DataFrame, key: str = "KEY_REG") -> pd.DataFrame:
    return frame[frame[key].astype(str) == REG]


def _extra(name: str) -> pd.DataFrame:
    return _mine(_run()["res"].extras[name])


# ═══════════════════════════ اجرای کامل ═══════════════════════════
def test_void_first_request_and_rejected_request_never_become_the_allocation():
    ntsw = _run()["sources"]["ntsw"]
    rows = _mine(ntsw["allocation_rows"]).set_index("NTSW_REQ_CURRENCY")
    assert rows.loc["CNY", "NTSW_REQUEST_STATE"] == "REJECTED"   # باطل‌شده، حتی با تاریخ تخصیص
    assert rows.loc["EUR", "NTSW_REQUEST_STATE"] == "REJECTED"
    assert rows.loc["USD", "NTSW_REQUEST_STATE"] == "ALLOCATED"
    agg = _mine(ntsw["allocation"]).iloc[0]
    assert agg["NTSW_ALLOCATED_CURRENCY"] == "USD" and float(agg["NTSW_ALLOCATED_AMOUNT"]) == AMOUNT


def test_registration_value_and_currency_come_from_the_import_licence():
    from gsi.finance.registration import BASIS_LICENSE
    r = _extra("registration_value_recon").iloc[0]
    assert (r["REG_VALUE"], r["REG_CURRENCY"], r["REG_VALUE_BASIS"]) == (AMOUNT, "EUR", BASIS_LICENSE)
    assert "منبع‌ها یکی نیست" not in str(r["FLAGS"])            # IL Append هم یورو است
    link = _extra("bl_registration_link").iloc[0]
    assert link["BL_CURRENCY"] == link["REG_CURRENCY"] == "EUR" and link["SHARE_PCT"] == 100


def test_step_currencies_are_shown_side_by_side_and_never_merged():
    r = _extra("fx_lifecycle").iloc[0]
    assert r["VALUE_REG_CURRENCY"] == "EUR"
    assert (r["ALLOC_CURRENCY"], r["PURCHASE_CURRENCY"]) == ("USD", "EUR")
    assert r["COMMITMENT_CURRENCY"] == "CNY، USD" and r["REJECTED_REQUEST_CURRENCIES"] == "CNY، EUR"
    assert bool(r["CURRENCY_MISMATCH"])
    assert r["CURRENCY_CHECK"].split(" · ") == [
        "ارز تخصیص (USD) با ارز ثبت سفارش (EUR) یکی نیست",
        "ارز خرید (EUR) با ارز تخصیص (USD) یکی نیست",
        "ارز تعهد (CNY، USD) با ارز تخصیص (USD) یکی نیست"]


def test_money_ledger_keeps_every_amount_in_its_own_currency():
    led = _extra("fx_money_ledger")

    def ccys(code):
        return sorted(led.loc[led["EVENT_CODE"].eq(code), "CURRENCY"])
    assert ccys("REGISTRATION_VALUE") == ["EUR"]
    assert led.loc[led["EVENT_CODE"].eq("REGISTRATION_VALUE"), "SOURCE"].tolist() == ["ntsw/import_license"]
    assert ccys("ALLOCATION_REQUEST") == ["USD"] and ccys("ALLOCATION") == ["USD"]
    assert ccys("ALLOCATION_REQUEST_REJECTED") == ["CNY", "EUR"]
    assert ccys("COMMITMENT_INITIAL") == ["CNY", "USD"]          # هر ارز جدا، نه جمع و قرنطینه
    quarantine = _run()["sources"]["ntsw"].get("commitment_quarantine")
    assert quarantine is None or _mine(quarantine).empty


def test_rejected_requests_are_not_demand_and_currencies_are_not_compared():
    rec = _extra("fx_money_reconciliation").set_index("CURRENCY")
    assert pd.isna(rec.loc["EUR", "REQUESTED_AMOUNT"]) and rec.loc["EUR", "REJECTED_REQUEST_AMOUNT"] == AMOUNT
    assert rec.loc["EUR", "REGISTRATION_AMOUNT"] == AMOUNT and pd.isna(rec.loc["USD", "REGISTRATION_AMOUNT"])
    assert rec.loc["USD", "REQUESTED_AMOUNT"] == rec.loc["USD", "ALLOCATED_AMOUNT"] == AMOUNT
    assert pd.isna(rec.loc["USD", "REQUEST_MINUS_ALLOCATED"]) or rec.loc["USD", "REQUEST_MINUS_ALLOCATED"] == 0
    note = rec.loc["EUR", "CROSS_CURRENCY_NOTE"]
    assert "ارزش ثبت سفارش=EUR" in note and "درخواست تخصیص=USD" in note
    assert note.endswith("مبلغ‌های ارزهای مختلف جمع یا مقایسه نشدند")


def test_timeline_dates_the_queue_from_a_live_request_and_names_currencies():
    tl = _extra("fx_stage_timeline").set_index("STAGE_CODE")
    # درخواست دلار ۱۴۰۴/۰۶/۰۱؛ نه درخواست باطل یوان ۱۴۰۴/۰۵/۰۱
    assert tl.loc["ALLOCATION_QUEUE", "EVENT_DATE"] == "2025-08-23"
    assert "درخواست رد یا باطل‌شده به ارز CNY، EUR" in tl.loc["ALLOCATION_QUEUE", "EVIDENCE"]
    assert "مبلغ=2,726,378.40 USD" in tl.loc["ALLOCATION", "EVIDENCE"]
    assert "مانده=2,726,378.40 CNY · 2,726,378.40 USD" in tl.loc["SETTLEMENT", "EVIDENCE"]


def test_cash_flow_skips_rejected_requests():
    from gsi.cashflow.dwh import bundle_from_dwh
    from gsi.warehouse.store import Warehouse
    bundle = bundle_from_dwh("2026-08-31", Warehouse(_run()["dwh"]))
    ev = bundle["events"][bundle["events"]["case_id"].astype(str) == REG]
    assert set(ev.loc[ev["kind"].eq("QUEUE"), "currency"]) == {"USD"}
    assert set(ev.loc[ev["kind"].eq("ALLOCATION"), "currency"]) == {"USD"}
    diag = bundle["diagnostics"]
    assert int((diag["code"].eq("REJECTED_ALLOCATION_REQUEST") & diag["entity_key"].astype(str).eq(REG)).sum()) == 2


def test_cash_flow_registration_value_comes_from_the_import_licence_not_the_pi():
    """دور ۷: رویداد «ارزش ثبت سفارش» جریان وجوه از ایمپورت لایسنس (یورو)، نه از جمع PI کارشناسان."""
    from gsi.cashflow.dwh import bundle_from_dwh
    from gsi.warehouse.store import Warehouse
    bundle = bundle_from_dwh("2026-08-31", Warehouse(_run()["dwh"]))
    ev = bundle["events"][bundle["events"]["case_id"].astype(str) == REG]
    reg = ev[ev["kind"].eq("REGISTRATION")]
    assert len(reg) == 1
    assert reg.iloc[0]["currency"] == "EUR" and reg.iloc[0]["source"] == "DWH/ntsw/import_license"
    assert "DWH/moghavemat/main" not in set(reg["source"])


def test_reports_show_the_mismatch_in_persian_and_english():
    from gsi.i18n import columns as C
    from gsi.report import fx_html as H
    res = _run()["res"]
    fa = H.build_report(res.df, res.extras, "2026-08-31", embed_fonts=False, embed_excel=False)
    en = H.build_report(res.df, res.extras, "2026-08-31", lang=C.EN, embed_fonts=False, embed_excel=False)
    assert "مغایرت ارز گام‌ها" in fa and "ارز تخصیص (USD) با ارز ثبت سفارش (EUR) یکی نیست" in fa
    assert "گام‌ها در چند ارز" in fa
    assert "Allocation currency (USD) differs from the registration currency (EUR)" in en
    assert "Import licence (NTSW)" in en and "Steps in several currencies" in en


# ═══════════════════════════ واحد ═══════════════════════════
def test_unknown_currency_text_is_never_a_currency():
    from gsi.finance.registration import currency_coder
    from gsi.rulebook import get_rulebook
    code = currency_coder(get_rulebook())
    assert [code(v) for v in ("یورو", "یوان چین", "دلار آمریکا", "نامشخص", "حواله", "", None)] == \
        ["EUR", "CNY", "USD", "", "", "", ""]

    class _Loose:
        """قاعده‌نامه آزمونی بدون فهرست ارزها: فقط کد سه‌حرفی لاتین ارز است."""
        def normalize_currency(self, v):
            return {"یورو": "EUR"}.get(str(v), str(v))
    loose = currency_coder(_Loose())
    assert [loose(v) for v in ("یورو", "نامشخص", "eur", "EUR")] == ["EUR", "", "", "EUR"]


def test_registration_reference_order_void_rows_and_amendments():
    from gsi.finance import registration as R
    from gsi.rulebook import get_rulebook
    frames = {
        ("ntsw", "import_license"): pd.DataFrame([
            {"KEY_REG": "R1", "NTSW_LICENSE_VALUE": 500, "NTSW_LICENSE_CURRENCY": "یوان چین",
             "NTSW_LICENSE_STATUS": "باطل شده"},
            {"KEY_REG": "R1", "NTSW_LICENSE_VALUE": 1000, "NTSW_LICENSE_CURRENCY": "یورو",
             "NTSW_LICENSE_STATUS": "تایید شده"},
            {"KEY_REG": "R2", "NTSW_LICENSE_VALUE": 700, "NTSW_LICENSE_CURRENCY": "حواله",
             "NTSW_LICENSE_STATUS": "تایید شده"}]),
        ("ilappend", "main"): pd.DataFrame([
            {"KEY_REG": "R3", "IL_REG_VALUE": 900, "IL_CURRENCY": "EUR", "IL_AMENDMENT_NO": "0"},
            {"KEY_REG": "R3", "IL_REG_VALUE": 900, "IL_CURRENCY": "EUR", "IL_AMENDMENT_NO": "1",
             "IL_CHANGE_CURRENCY": "USD"}]),
        ("credit", "main"): pd.DataFrame([
            {"KEY_REG": "R4", "CRD_PROFORMA_VALUE": 300, "CRD_CURRENCY": "EUR"},
            {"KEY_REG": "R1", "CRD_PROFORMA_VALUE": 1000, "CRD_CURRENCY": "USD"}]),
    }
    out = R.registration_values(lambda s, f: frames.get((s, f)), R.currency_coder(get_rulebook()))
    r1 = out["R1"]
    assert (r1["value"], r1["currency"], r1["basis"]) == (1000, "EUR", R.BASIS_LICENSE)
    assert "ارز ثبت سفارش در منبع‌ها یکی نیست: ایمپورت لایسنس (NTSW)=EUR، ارزش پروفرم (اعتبارات اسنادی)=USD" \
        in r1["flags"]
    # مبلغ مرجع می‌ماند و ارز نامعلوم گزارش می‌شود؛ جمع PI جای آن نمی‌نشیند
    assert (out["R2"]["value"], out["R2"]["currency"], out["R2"]["basis"]) == (700, "", R.BASIS_LICENSE)
    assert out["R2"]["flags"] == ["ارز ناشناخته در ایمپورت لایسنس (NTSW): حواله",
                                  "مبلغ هست ولی ارز آن معلوم نیست: ایمپورت لایسنس (NTSW)=700.00"]
    assert (out["R3"]["currency"], out["R3"]["basis"]) == ("USD", R.BASIS_IL)
    assert "ارز از اصلاحیه 1 (USD)" in out["R3"]["flags"]
    assert (out["R4"]["value"], out["R4"]["currency"], out["R4"]["basis"]) == (300, "EUR", R.BASIS_CREDIT)


def test_rejected_only_currency_is_not_an_evidence_gap():
    from gsi.stages.s56_money_flow_control import MoneyFlowControlStage
    money = pd.DataFrame([
        {"KEY_REG": "R1", "EVENT_CODE": code, "AMOUNT": 100.0, "CURRENCY": ccy}
        for code, ccy in [("REGISTRATION_VALUE", "EUR"), ("ALLOCATION_REQUEST_REJECTED", "CNY"),
                          ("ALLOCATION_REQUEST", "EUR"), ("ALLOCATION", "EUR")]])
    rec = MoneyFlowControlStage()._build_money_reconciliation(money).set_index("CURRENCY")
    assert rec.loc["CNY", "RECON_STATUS"] == "REJECTED_REQUESTS_ONLY" and rec.loc["CNY", "EVIDENCE_GAPS"] == ""
    assert rec.loc["EUR", "REQUESTED_AMOUNT"] == 100 and pd.isna(rec.loc["EUR", "REJECTED_REQUEST_AMOUNT"])


def test_cb_value_carries_the_currency_of_the_source_that_gave_it():
    from gsi.rulebook import get_rulebook
    from gsi.stages.base import PipelineContext
    from gsi.stages.s20_derive import DeriveStage
    df = pd.DataFrame([
        {"KEY_REG": "R1", "NTSW_INITIAL_COMMIT": 5000, "NTSW_CURRENCY": "CNY", "MOGH_PI_VALUE_SUM": 900,
         "MOGH_CURRENCY": "USD"},
        {"KEY_REG": "R2", "NTSW_INITIAL_COMMIT": None, "NTSW_CURRENCY": "", "MOGH_PI_VALUE_SUM": 900,
         "MOGH_CURRENCY": "USD", "FX_CURRENCY": "EUR"}])
    out = DeriveStage().run(df, PipelineContext(rb=get_rulebook(), today=date(2026, 8, 31)))
    assert out[["CB_VALUE", "CB_CURRENCY"]].values.tolist() == [[5000.0, "CNY"], [900.0, "USD"]]


def test_value_at_risk_compares_values_only_within_one_currency():
    from gsi.engines.risk import SAME_CURRENCY_CAP, RiskScoreEngine
    from gsi.rulebook import get_rulebook
    from gsi.stages.base import PipelineContext
    from gsi.stages.s70_risk import RiskStage
    rb = get_rulebook()
    df = pd.DataFrame({"CB_VALUE": [1_000_000, 100_000, 50_000, 10],
                       "CB_CURRENCY": ["یوان چین", "EUR", "نامشخص", "یورو"]})
    caps = RiskStage._same_currency_caps(df, df["CB_VALUE"], PipelineContext(rb=rb, today=date(2026, 8, 31)))
    assert caps == [1_000_000.0, 100_000.0, 0.0, 100_000.0]
    engine = RiskScoreEngine(max_cb_value=1_000_000, rb=rb)
    # بزرگ‌ترین ارزش یورو: ۱۰۰٪، نه ۱۰٪ کنار یک میلیون یوان؛ ارز نامعلوم سهم ارزشی نمی‌گیرد
    assert engine.score({"CB_VALUE": 100_000, SAME_CURRENCY_CAP: 100_000}).factors["value_at_risk"] == 100
    assert engine.score({"CB_VALUE": 50_000, SAME_CURRENCY_CAP: 0}).factors["value_at_risk"] == 0


def test_invoice_amounts_across_sources_are_compared_only_within_one_known_currency():
    """سنجش اعتماد: عدد یکسان به دو ارز «هم‌خوان» نیست و عدد بی‌ارز با هیچ عددی سنجیده نمی‌شود."""
    from gsi.trust.contracts import REG, cross_source_for
    from gsi.trust.profiling import profile_frame
    rules = cross_source_for(REG)
    value_rule = [r for r in rules if r.column == "INVOICE_VALUE"][0]
    assert dict(zip(value_rule.sources, value_rule.currency_columns)) == {
        "CL_INVOICE_VALUE": "CL_CURRENCY", "SATA_INVOICE_VALUE": "SATA_CURRENCY", "COT_INVOICE_VALUE": ""}

    def value_defects(**row):
        ledger = profile_frame(pd.DataFrame([{"CANONICAL_REG": "1", **row}]), (), entity_type="REG",
                               key_column="CANONICAL_REG", cross_source=rules).ledger
        return [d.note for d in ledger if d.code == "SOURCE_DISAGREEMENT"]

    # همان عدد به یوان و یورو، و عدد متفاوت به یوان و یورو: هیچ‌کدام مقایسه مبلغ نیست
    assert value_defects(CL_INVOICE_VALUE=AMOUNT, CL_CURRENCY="یوان", SATA_INVOICE_VALUE=AMOUNT,
                         SATA_CURRENCY="EUR") == []
    assert value_defects(CL_INVOICE_VALUE=1_540_510.08, CL_CURRENCY="یوان", SATA_INVOICE_VALUE=199_635,
                         SATA_CURRENCY="EUR") == []
    # یک ارز با دو نوشتار سنجیده می‌شود و ارز کنار هر عدد می‌آید
    notes = value_defects(CL_INVOICE_VALUE=413_056.67, CL_CURRENCY="یورو", SATA_INVOICE_VALUE=16_284_521.76,
                          SATA_CURRENCY="EUR")
    assert len(notes) == 1 and "CL_INVOICE_VALUE=413,056.67 EUR" in notes[0]
    # ارز ناشناخته، و کوتاژ که ستون ارز ندارد: سنجیده نمی‌شوند
    assert value_defects(CL_INVOICE_VALUE=400, CL_CURRENCY="حواله", SATA_INVOICE_VALUE=1000,
                         SATA_CURRENCY="EUR") == []
    assert value_defects(CL_INVOICE_VALUE=1000, CL_CURRENCY="EUR", SATA_INVOICE_VALUE=1000, SATA_CURRENCY="EUR",
                         COT_INVOICE_VALUE=57_000) == []


def test_sata_and_customs_values_are_compared_only_in_one_known_currency():
    from gsi.rulebook import get_rulebook
    from gsi.stages.base import PipelineContext
    from gsi.stages.s59_bl_registration_link import BLRegistrationLinkStage

    def flags(cl_value, cl_currency):
        ctx = PipelineContext(rb=get_rulebook(), today=date(2026, 8, 31))
        BLRegistrationLinkStage().run(pd.DataFrame([{
            "KEY_REG": "R1", "CANONICAL_BL": "BL1", "KEY_ORDER": "O1", "KEY_MATERIAL": "M1",
            "INVOICE_VALUE": 1000, "INVOICE_CURRENCY": "EUR",
            "CL_INVOICE_VALUE": cl_value, "CL_CURRENCY": cl_currency}]), ctx)
        return ctx.extras["bl_registration_link"].iloc[0]["FLAGS"]

    assert "اختلاف ارزش فاکتور ساتا و گمرک" in flags(400, "یورو")
    assert flags(1000, "یوان") == "ارز فاکتور ساتا (EUR) با ارز اظهار گمرکی (CNY) یکی نیست"
    # ارز گمرکی خالی یا ناشناخته: عدد گمرک نه هم‌خوان است نه متعارض
    assert flags(400, "") == "" and flags(400, "حواله") == "" and flags(1000, "") == ""

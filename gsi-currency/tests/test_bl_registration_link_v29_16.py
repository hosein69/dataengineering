# -*- coding: utf-8 -*-
"""29.16 — پیوند مبلغی بارنامه ↔ ثبت سفارش، چرخه ارز، صف تخصیص و تابلوی بحرانی.

هر آزمون یک خطای مدیریتی واقعی را قفل می‌کند:
  * ارزش بارنامه‌ای که روی چند متریال تکرار شده دوبار شمرده نشود (fan-out)؛
  * بارنامه یوان هرگز به ثبت سفارش یورو اضافه نشود (جمع بین‌ارزی)؛
  * بارنامه مشترک بین دو ثبت سفارش سهمش حدس زده نشود؛
  * ارزش نامعلوم «صفر» نشود؛
  * مرحله جاری چرخه، گام بعد از پیشرفته‌ترین گام انجام‌شده باشد، نه اولین گام بی‌شاهد.
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from gsi.stages.base import PipelineContext
from gsi.stages.s59_bl_registration_link import (BLRegistrationLinkStage, ST_CCY_MISMATCH, ST_FULL,
                                                 ST_NO_REG, ST_OVER, ST_PARTIAL, ST_REG_UNKNOWN)

TODAY = date(2026, 9, 27)


class _RB:
    """نرمال‌ساز ساده ارز برای آزمون واحد (نسخه واقعی در RuleBook است)."""
    ALIASES = {"یورو": "EUR", "یوان": "CNY", "درهم": "AED"}

    def normalize_currency(self, v):
        t = "" if v is None else str(v).strip()
        return self.ALIASES.get(t, t.upper() if t.lower() not in ("", "nan", "none") else "")


def _ctx(credit=None, timeline=None):
    ctx = PipelineContext(rb=_RB(), today=TODAY)
    if credit is not None:
        ctx.sources["credit"] = {"main": credit}
    if timeline is not None:
        ctx.extras["fx_stage_timeline"] = timeline
    return ctx


def _row(reg, bl, mat, value, ccy, **kw):
    r = {"KEY_REG": reg, "CANONICAL_BL": bl, "KEY_ORDER": "O-" + reg, "KEY_MATERIAL": mat,
         "INVOICE_VALUE": value, "INVOICE_CURRENCY": ccy}
    r.update(kw)
    return r


def _credit(rows):
    return pd.DataFrame([{"KEY_REG": r, "CRD_PROFORMA_VALUE": v, "CRD_CURRENCY": c} for r, v, c in rows])


def _run(df, ctx):
    out = BLRegistrationLinkStage().run(pd.DataFrame(df), ctx)
    return out, ctx.extras["registration_value_recon"].set_index("KEY_REG"), ctx.extras["bl_registration_link"]


def test_bl_value_repeated_on_material_rows_is_counted_once():
    df = [_row("R1", "BL1", "M1", 400, "EUR"), _row("R1", "BL1", "M2", 400, "EUR"),
          _row("R1", "BL2", "M3", 100, "EUR")]
    out, recon, link = _run(df, _ctx(_credit([("R1", 1000, "EUR")])))
    assert recon.loc["R1", "SHIPPED_VALUE"] == 500
    assert recon.loc["R1", "SHIPPED_PCT"] == 50
    assert recon.loc["R1", "UNSHIPPED_VALUE"] == 500
    assert recon.loc["R1", "STATUS"] == ST_PARTIAL
    assert len(link) == 2
    assert set(out["BLREG_BL_SHARE_PCT"].dropna()) == {40.0, 10.0}


def test_full_and_over_shipment():
    df = [_row("R1", "BL1", "M1", 1000, "EUR"), _row("R2", "BL2", "M2", 1300, "EUR")]
    _, recon, _ = _run(df, _ctx(_credit([("R1", 1000, "EUR"), ("R2", 1000, "EUR")])))
    assert recon.loc["R1", "STATUS"] == ST_FULL
    assert recon.loc["R2", "STATUS"] == ST_OVER
    assert recon.loc["R2", "UNSHIPPED_VALUE"] == -300


def test_other_currency_bl_is_never_added_without_a_rate():
    df = [_row("R1", "BL1", "M1", 500, "EUR"), _row("R1", "BL2", "M2", 9000, "یوان")]
    _, recon, link = _run(df, _ctx(_credit([("R1", 1000, "EUR")])))
    assert recon.loc["R1", "SHIPPED_VALUE"] == 500
    assert recon.loc["R1", "STATUS"] == ST_CCY_MISMATCH
    assert bool(recon.loc["R1", "SHIPPED_IS_LOWER_BOUND"])
    assert link.set_index("KEY_BL").loc["BL2", "BL_CURRENCY"] == "CNY"


def test_unshipped_balance_is_an_upper_bound_when_part_of_the_shipment_is_unknown():
    """دور ۷: بارنامه دوم ارز یوان دارد و در جمع نمی‌آید؛ «حمل‌شده» حداقل و «مانده» حداکثر است."""
    df = [_row("R1", "BL1", "M1", 600, "EUR"), _row("R1", "BL2", "M2", 9000, "یوان")]
    _, recon, _ = _run(df, _ctx(_credit([("R1", 1000, "EUR")])))
    assert recon.loc["R1", "UNSHIPPED_VALUE"] == 400 and bool(recon.loc["R1", "SHIPPED_IS_LOWER_BOUND"])
    assert "مانده حمل‌نشده حداکثر است" in recon.loc["R1", "FLAGS"]
    full = [_row("R2", "BL3", "M3", 1000, "EUR")]
    _, recon2, _ = _run(full, _ctx(_credit([("R2", 1000, "EUR")])))
    assert "حداکثر" not in recon2.loc["R2", "FLAGS"]


def test_bl_shared_by_two_registrations_has_unknown_share():
    df = [_row("R1", "BL1", "M1", 800, "EUR"), _row("R2", "BL1", "M2", 800, "EUR")]
    _, recon, link = _run(df, _ctx(_credit([("R1", 1000, "EUR"), ("R2", 1000, "EUR")])))
    assert recon.loc["R1", "SHIPPED_VALUE"] == 0
    assert "مشترک" in recon.loc["R1", "FLAGS"]
    assert (link["BL_REG_COUNT"] == 2).all()


def test_unknown_registration_value_stays_unknown_not_zero():
    df = [_row("R9", "BL9", "M9", 300, "EUR")]
    out, recon, _ = _run(df, _ctx())
    assert recon.loc["R9", "STATUS"] == ST_REG_UNKNOWN
    assert pd.isna(recon.loc["R9", "REG_VALUE"]) and pd.isna(recon.loc["R9", "SHIPPED_PCT"])
    assert out["BLREG_REG_VALUE"].isna().all()


def test_ntsw_commitment_is_never_the_registration_value():
    """29.21: تا 29.20 تعهد NTSW مبنای دوم ارزش ثبت سفارش بود و ارز تعهدِ یک درخواست باطل (یوان)
    جای ارز ثبت سفارش (یورو) می‌نشست. ارزش و ارز فقط از ایمپورت لایسنس و IL Append می‌آید."""
    df = [_row("R1", "BL1", "M1", 250, "AED", FX_NTSW_INITIAL=500, FX_NTSW_CURRENCY="AED")]
    _, recon, _ = _run(df, _ctx())
    assert pd.isna(recon.loc["R1", "REG_VALUE"])
    assert recon.loc["R1", "REG_VALUE_BASIS"] == "ارزش ثبت سفارش در هیچ منبعی نیست"
    ctx = _ctx()
    ctx.sources["ntsw"] = {"import_license": pd.DataFrame([
        {"KEY_REG": "R1", "NTSW_LICENSE_VALUE": 500, "NTSW_LICENSE_CURRENCY": "درهم"}])}
    _, recon, _ = _run(df, ctx)
    assert (recon.loc["R1", "REG_VALUE"], recon.loc["R1", "REG_CURRENCY"]) == (500, "AED")
    assert recon.loc["R1", "REG_VALUE_BASIS"] == "ایمپورت لایسنس (NTSW)"


def test_bl_without_registration_is_flagged():
    df = [_row("", "BLX", "M1", 100, "EUR")]
    out, _, link = _run(df, _ctx())
    assert link.iloc[0]["STATUS"] == ST_NO_REG
    assert out.iloc[0]["BLREG_STATUS"] == ST_NO_REG


def test_sata_and_customs_invoice_disagreement_is_reported():
    df = [_row("R1", "BL1", "M1", 1000, "EUR", CL_INVOICE_VALUE=400, CL_CURRENCY="یورو")]
    _, _, link = _run(df, _ctx(_credit([("R1", 1000, "EUR")])))
    assert "اختلاف ارزش فاکتور ساتا و گمرک" in link.iloc[0]["FLAGS"]


def _timeline(reg, statuses):
    codes = ["ORDER_REG", "ALLOCATION_QUEUE", "ALLOCATION", "FX_PURCHASE", "FUNDING", "SWIFT_CONVERSION",
             "SHIPMENT", "CUSTOMS", "CLEARANCE", "BANK_DOCS", "SETTLEMENT"]
    return pd.DataFrame([{"KEY_REG": reg, "STAGE_CODE": c, "STATUS": statuses.get(c, "PENDING"),
                          "EVENT_DATE": "2026-09-01" if statuses.get(c) == "DONE" else "", "DUE_DATE": "",
                          "EVIDENCE": ""} for c in codes])


def test_current_stage_follows_the_furthest_completed_step():
    tl = _timeline("R1", {"ORDER_REG": "DONE", "ALLOCATION": "DONE", "FX_PURCHASE": "DONE",
                          "ALLOCATION_QUEUE": "EVIDENCE_GAP"})
    df = [_row("R1", "BL1", "M1", 10, "EUR", KEY_REG_FILE="F-1")]
    out, _, _ = _run(df, _ctx(_credit([("R1", 10, "EUR")]), tl))
    lc = BLRegistrationLinkStage  # noqa: F841 — stage class stays importable
    assert out.iloc[0]["LIFECYCLE_STAGE"] == "تأمین وجه"
    assert out.iloc[0]["LIFECYCLE_STAGE_DAYS"] == 26
    assert "صف تخصیص" in out.iloc[0]["LIFECYCLE_GAPS"]


def test_settled_registration_is_closed():
    tl = _timeline("R1", {c: "DONE" for c in ["ORDER_REG", "SHIPMENT", "CLEARANCE", "SETTLEMENT"]})
    ctx = _ctx(_credit([("R1", 10, "EUR")]), tl)
    _run([_row("R1", "BL1", "M1", 10, "EUR")], ctx)
    lc = ctx.extras["fx_lifecycle"].set_index("KEY_REG")
    assert lc.loc["R1", "CURRENT_STAGE_CODE"] == "CLOSED"
    assert lc.loc["R1", "PROGRESS_PCT"] == 100


def test_allocation_queue_puts_critical_orders_first():
    df = [_row("R1", "BL1", "M1", 1, "EUR", ALLOC_QUEUE_STATE="IN_QUEUE", ALLOC_QUEUE_ENTER_DATE="2026-09-20",
               OPEN_QUEUE_AMOUNT=50, NTSW_REQ_CURRENCY="EUR", OPEN_ALLOC_REQUESTS=1, ORDER_CRITICAL_LEVEL="SAFE"),
          _row("R2", "BL2", "M2", 1, "EUR", ALLOC_QUEUE_STATE="IN_QUEUE", ALLOC_QUEUE_ENTER_DATE="2026-09-25",
               OPEN_QUEUE_AMOUNT=70, NTSW_REQ_CURRENCY="EUR", OPEN_ALLOC_REQUESTS=1, ORDER_CRITICAL_LEVEL="STOCKOUT"),
          _row("R3", "BL3", "M3", 1, "EUR", ALLOC_QUEUE_STATE="ALLOCATED")]
    ctx = _ctx()
    _run(df, ctx)
    q = ctx.extras["allocation_queue"]
    assert q["KEY_REG"].tolist() == ["R2", "R1"]
    assert q.set_index("KEY_REG").loc["R1", "WAIT_DAYS"] == 7


# ─────────────────────────── تابلوی بحرانی ───────────────────────────
def _crit_df():
    return pd.DataFrame([
        {"KEY_MATERIAL": "M1", "MATERIAL_DESC": "پلوس", "کد طبقه بحرانی": "STOCKOUT", "مقاومت (روز)": 0,
         "CANONICAL_BL": "BL1", "BL_CRITICAL_LEVEL": "STOCKOUT", "KEY_REG": "R1", "روزهای رسوب": 40,
         "BLREG_BL_INVOICE_VALUE": 100, "BLREG_BL_CURRENCY": "EUR", "BLREG_REG_VALUE": 1000,
         "BLREG_REG_CURRENCY": "EUR", "BLREG_REG_SHIPPED_PCT": 10, "مانده تعهد": 900, "FX_DAYS_REMAINING": -3},
        {"KEY_MATERIAL": "M2", "MATERIAL_DESC": "کاسه نمد", "کد طبقه بحرانی": "SAFE", "مقاومت (روز)": 300,
         "CANONICAL_BL": "BL2", "BL_CRITICAL_LEVEL": "SAFE", "KEY_REG": "R2"},
        {"KEY_MATERIAL": "M3", "MATERIAL_DESC": "دریچه", "کد طبقه بحرانی": "CRITICAL", "مقاومت (روز)": 4,
         "CANONICAL_BL": "BL1", "BL_CRITICAL_LEVEL": "STOCKOUT", "KEY_REG": "R1", "روزهای رسوب": 40},
    ])


def test_critical_board_grains_and_order():
    from gsi.report.critical_board import critical_bls, critical_materials
    m = critical_materials(_crit_df())
    b = critical_bls(_crit_df())
    assert m["متریال"].tolist() == ["M1", "M3"]
    assert b["بارنامه"].tolist() == ["BL1"]             # یک ردیف برای هر بارنامه، نه هر متریال
    assert b.iloc[0]["ارزش فاکتور"] == 100


def test_critical_board_takes_each_amount_with_the_currency_of_its_own_row():
    """دور ۷: مبلغ و ارز از یک ردیف؛ ارزش، حمل‌شده و مانده ثبت سفارش فقط برای بارنامه تک‌ثبت‌سفارشی."""
    from gsi.report.critical_board import critical_bls
    base = {"CANONICAL_BL": "BL1", "BL_CRITICAL_LEVEL": "STOCKOUT", "مقاومت (روز)": 0}
    one = pd.DataFrame([
        {**base, "KEY_MATERIAL": "M1", "KEY_REG": "R1", "BLREG_BL_INVOICE_VALUE": 100, "BLREG_BL_CURRENCY": "",
         "BLREG_REG_VALUE": 1000, "BLREG_REG_CURRENCY": "", "مانده تعهد": 900, "NTSW_CURRENCY": "CNY"},
        {**base, "KEY_MATERIAL": "M2", "KEY_REG": "R1", "BLREG_BL_INVOICE_VALUE": None, "BLREG_BL_CURRENCY": "EUR",
         "BLREG_REG_VALUE": None, "BLREG_REG_CURRENCY": "EUR", "مانده تعهد": None, "NTSW_CURRENCY": ""},
    ])
    r = critical_bls(one).iloc[0]
    # مبلغی که ارزش نامعلوم است برچسب «EUR» ردیف دیگر را نمی‌گیرد
    assert r["ارزش فاکتور"] == 100 and r["ارز فاکتور"] == ""
    assert r["ارزش ثبت سفارش"] == 1000 and r["ارز ثبت سفارش"] == ""
    assert r["مانده تعهد"] == 900 and r["ارز تعهد"] == "CNY"
    two = one.assign(KEY_REG=["R1", "R2"])
    r2 = critical_bls(two).iloc[0]
    assert pd.isna(r2["ارزش ثبت سفارش"]) and pd.isna(r2["مانده تعهد"]) and r2["ارز تعهد"] == ""
    assert r2["وضعیت پیوند"] == "بارنامه به 2 ثبت سفارش وصل است؛ سهم هر یک در منبع نیست"


def test_critical_html_is_rtl_offline_and_uses_only_design_tokens():
    from gsi.design import tokens as T
    from gsi.report.critical_board import build_critical_html
    page = build_critical_html(_crit_df(), "1405/07/05")
    assert 'dir="rtl"' in page and "<script src" not in page and 'rel="stylesheet"' not in page
    allowed = {c.lower() for c in (T.SURFACE_PAGE, T.SURFACE_RAISED, T.SURFACE_SUNKEN, T.SURFACE_INVERSE,
                                   T.SURFACE_PAPER, T.SURFACE_PAPER_SOFT, T.PAPER_RULE, T.PENCIL, T.AQUA_MIST,
                                   T.LAPIS_WASH, T.BORDER, T.BORDER_STRONG, T.BORDER_FOCUS, T.TEXT,
                                   T.TEXT_SECONDARY, T.TEXT_MUTED, T.TEXT_ON_DARK, T.BRAND_NAVY, T.BRAND_TEAL,
                                   T.BRAND_GOLD, T.TEAL_INK, T.GOLD_INK, T.TEAL_WASH, T.GOLD_WASH, T.NAVY_WASH)}
    allowed |= {v.lower() for s in T.STATUS_SCALE for v in (s.ink, s.fill, s.wash)}
    allowed |= {c.lower() for c in T.CATEGORICAL + T.SEQUENTIAL + T.TEAL_PALETTE}
    allowed |= {c.lower() for c in T.BRAND_BAND}  # R10: سربرگ برند با پالت موشن‌گرافیک
    used = {m.lower() for m in re.findall(r"#[0-9A-Fa-f]{6}\b", page)}
    assert not (used - allowed), sorted(used - allowed)
    assert "رفع تعهد" not in page or "روز گذشته" in page


def test_brand_colours_come_from_the_owner_teal_palette():
    from gsi.design import tokens as T
    palette = {c.lower() for c in T.TEAL_PALETTE}
    assert T.BRAND_TEAL.lower() in palette and T.TEAL_INK.lower() in palette
    assert {c.lower() for c in T.SEQUENTIAL} <= palette
    assert T.CATEGORICAL[0].lower() in palette
    assert not T.audit(), T.audit_report()

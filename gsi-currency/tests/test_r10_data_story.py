# -*- coding: utf-8 -*-
"""R10 (مالک، ۱۴۰۵/۰۷/۰۹): فضای «دیتا استوری‌تلینگ». هر ارز جدا، بی‌داده ≠ صفر، انتظار فقط با جفت
شناسه درخواست، مقایسه دوره‌ها از ۱۴۰۴، و پرسش بی‌منبع با کارت «داده نداریم». داده ساختگی."""
import io
import re

import pandas as pd
from openpyxl import load_workbook

from gsi.report import data_story as D

REF = "1405/06/10"

_DERIVED = {"ARRIVAL_DATE": "CL_ARRIVAL_DATE", "DISCHARGE_DATE": "BL_DISCHARGE_DATE", "DO_DATE": "BL_DO_DATE",
            "FULL_CLEAR_DATE": "CL_CLEAR_DATE"}


def _ev(reg, code, d, amt, cur, ref="", status=""):
    return {"KEY_REG": reg, "EVENT_CODE": code, "EVENT_DATE": d, "AMOUNT": amt, "CURRENCY": cur,
            "REFERENCE": ref, "STATUS": status, "SOURCE": "t"}


def _ledger():
    rows = [
        # پیش از ۱۴۰۴: انتظار ۶۰ روز، یک رد
        _ev("R1", "ALLOCATION_REQUEST", "1403/02/01", 100, "EUR", "Q1", "ALLOCATED"),
        _ev("R1", "ALLOCATION", "1403/03/30", 100, "EUR", "Q1"),
        _ev("R1", "FX_PURCHASE", "1403/05/01", 100, "EUR"),
        _ev("R1", "COMMITMENT_INITIAL", "1403/04/01", 100, "EUR"),
        _ev("R1", "COMMITMENT_RELEASED", "", 100, "EUR"),
        _ev("R2", "ALLOCATION_REQUEST_REJECTED", "1403/03/01", 50, "CNY", "Q2"),
        # ۱۴۰۴ به بعد: انتظار ۲۰ روز
        _ev("R2", "ALLOCATION_REQUEST", "1404/02/01", 70, "USD", "Q3", "ALLOCATED"),
        _ev("R2", "ALLOCATION", "1404/02/21", 70, "USD", "Q3"),
        _ev("R2", "FX_PURCHASE", "1404/03/10", 70, "USD"),
        _ev("R2", "COMMITMENT_INITIAL", "1404/02/21", 70, "USD"),
        _ev("R3", "ALLOCATION_REQUEST", "1404/08/01", 200, "EUR", "Q4", "ALLOCATED"),
        _ev("R3", "ALLOCATION", "1404/08/21", 200, "EUR", "Q4"),
        _ev("R3", "FX_PURCHASE", "1404/09/01", 200, "EUR"),
        _ev("R4", "ALLOCATION_REQUEST", "1405/03/01", 999, "EUR", "Q5", "OPEN"),
        # تخصیص بی‌درخواست جفت‌شده: در انتظار شمرده نمی‌شود
        _ev("R4", "ALLOCATION", "1405/04/01", 10, "EUR", "QX"),
    ]
    return pd.DataFrame(rows)


def _r(bl, reg, order, mat, group, level, **kw):
    row = {"CANONICAL_BL": bl, "KEY_BL": bl, "KEY_REG": reg, "CANONICAL_ORDER": order, "KEY_ORDER": order,
           "KEY_MATERIAL": mat, "PART_GROUP": group, "TRANSPORT_MODE": "SEA", "کد طبقه بحرانی": level,
           "MOGH_BL_COUNT": 1, **kw}
    row.update({d: kw[s] for d, s in _DERIVED.items() if s in kw})
    return row


def _frame():
    return pd.DataFrame([
        _r("BL1", "R1", "O1", "M1", "بدنه", "SAFE", BL_DISCHARGE_DATE="1403/06/01", IS_FULL_CLEARED=True,
           CL_CLEAR_DATE="1403/07/30", BLREG_BL_INVOICE_VALUE=80, BLREG_BL_CURRENCY="EUR"),
        _r("BL2", "R3", "O3", "M3", "موتور", "CRITICAL", BL_DISCHARGE_DATE="1404/10/01", IS_FULL_CLEARED=True,
           CL_CLEAR_DATE="1404/10/21", BLREG_BL_INVOICE_VALUE=150, BLREG_BL_CURRENCY="EUR"),
        _r("BL3", "R2", "O2", "M2", "موتور", "STOCKOUT", BL_DISCHARGE_DATE="1405/05/01",
           MOGH_PI_VALUE_SUM=40, MOGH_CURRENCY="USD"),
        _r("BL3", "R2", "O2", "M5", "برق", "CRITICAL", MOGH_PI_VALUE_SUM=30, MOGH_CURRENCY="CNY"),
    ])


def _story(extras=None, df=None):
    ex = {"fx_money_ledger": _ledger()} if extras is None else extras
    return D.build_story(_frame() if df is None else df, ex, REF, critical_runs=[])


def test_periods_waits_and_no_cross_currency():
    s = _story()
    ch = {c.key: c for c in s.chapters}
    since = ch["since"].table.set_index("شاخص")
    assert since.columns[0] == D.PERIOD_BASE
    wait = since.loc["میانه انتظار تخصیص"]
    assert wait[D.PERIOD_BASE] == 60 and wait["نیمه اول ۱۴۰۴"] == 20 and wait["از ۱۴۰۴ (تجمیعی)"] == 20
    assert pd.isna(wait["نیمه اول ۱۴۰۵"])                    # QX با درخواستی جفت نشد؛ بی‌داده، نه صفر
    acc = since.loc["پذیرش درخواست تخصیص"]
    assert acc[D.PERIOD_BASE] == 50 and acc["نیمه اول ۱۴۰۴"] == 100
    clr = since.loc["میانه تخلیه تا ترخیص کامل"]
    assert clr[D.PERIOD_BASE] == 60 and clr["نیمه دوم ۱۴۰۴"] == 20
    assert "بهتر" in ch["since"].headline
    # پول: هر ارز ردیف خودش؛ هیچ جمع میان ارزها
    money = ch["money"].table
    assert set(money["ارز"]) == {"EUR", "USD"}
    assert money.groupby("ارز")["مبلغ خرید"].sum().to_dict() == {"EUR": 300, "USD": 70}
    # پول و کالا فقط در ارزی که هر دو را دارد (EUR)
    goods = ch["goods"].table
    assert set(goods["ارز"]) == {"EUR"} and goods["ارزش کالای تخلیه‌شده (انباشته)"].max() == 230
    # قطعات بحرانی باز: ارزش PI هر ارز جدا
    assert "۴۰ دلار" in ch["critical"].headline and "۳۰ یوآن" in ch["critical"].headline
    assert any("غیرضروری" in g for g in ch["critical"].gaps)
    # رفع تعهد: تاریخ ندارد و به نیم‌سال ایجاد نسبت داده می‌شود
    st = ch["settle"].table
    assert st.loc[st["ارز"].eq("EUR") & st["نیم‌سال تعهد"].eq("نیمه اول ۱۴۰۳"), "رفع تعهد (٪ مبلغ همان ارز)"].iloc[0] == 100
    assert st.loc[st["ارز"].eq("USD"), "رفع تعهد (٪ مبلغ همان ارز)"].isna().all()   # رفع ثبت نشده ≠ صفر
    # گروه: R2 قطعه دو گروه دارد ← «چند گروه»
    assert D.groups_of(_frame(), "KEY_REG")["R2"] == D.MULTI_GROUP
    assert s.hero[0][1] == "۲" and s.hero[1][1] == "۳"


def test_missing_sources_become_gap_chapters():
    s = D.build_story(pd.DataFrame(), {}, REF, critical_runs=[])
    ch = {c.key: c for c in s.chapters}
    for k in ("since", "money", "goods", "queue", "settle", "groups", "critical", "crit_hist", "ship"):
        assert not ch[k].has_data and ch[k].gaps, k
    assert ch["gaps"].has_data and "دموراژ" in ch["gaps"].visual
    assert "<section" in D.build_html(s, embed_fonts=False)


def test_html_and_excel_render():
    s = _story()
    html = D.build_html(s, embed_fonts=False)
    assert html.startswith("<!DOCTYPE html>") and 'dir="rtl"' in html
    assert html.count('class="ds-ch ') == len(s.chapters) and "<svg" in html
    assert "۱۴۰۴/۰۳/۲۳" in html                              # نشانه زمانی، نه علت
    wb = load_workbook(io.BytesIO(D.build_excel(s)))
    assert wb.sheetnames[0] == "خلاصه" and len(wb.sheetnames) >= 6


def test_counts_compare_per_half_not_whole_period():
    """شمار پیش از ۱۴۰۴ (چند نیم‌سال) با میانگین هر نیم‌سال کامل از ۱۴۰۴ سنجیده می‌شود، نه با کل دوره."""
    s = _story()
    t = {c.key: c for c in s.chapters}["since"].table.set_index("شاخص")
    al = t.loc["شمار تخصیص در هر نیم‌سال"]
    assert al[D.PERIOD_BASE] == 1 and al["نیمه اول ۱۴۰۵"] == 1
    # پیش از ۱۴۰۴: یک تخصیص در ۲ نیم‌سال (نیمه اول و دوم ۱۴۰۳) = ۰٫۵؛ از ۱۴۰۴: ۲ تخصیص در ۲ نیم‌سال کامل = ۱
    assert al["از ۱۴۰۴ (تجمیعی)"] == 1


def test_composer_block_is_optional_and_renders():
    from gsi.studio_core import composer
    from gsi.studio_core.html_export import build_dynamic_html
    assert "data_story" in composer.BLOCKS
    assert all("data_story" not in v for v in composer.DEFAULT_BLOCKS.values())   # افزودنی، نه پیش‌فرض
    tabs = [{"id": "ds", "title": "داستان", "blocks": ["data_story"], "block_sizes": {}}]
    page = build_dynamic_html(_frame(), REF, tabs=tabs, process_extras={"fx_money_ledger": _ledger()})
    assert 'data-composer-block="data_story"' in page and 'class="ds-ch ' in page and ".ds-kpi{" in page



def test_settlement_is_sata_tracking_code_and_its_date():
    """مالک ۱۴۰۵/۰۷/۰۹: رفع تعهد = داشتن کد رهگیری ساتا؛ تاریخ = «تاریخ اخذ کد رهگیری» (دیرترین بارنامه)."""
    led = pd.concat([_ledger(), pd.DataFrame([
        _ev("R5", "ALLOCATION", "1404/01/10", 30, "EUR", "Q9"), _ev("R5", "COMMITMENT_INITIAL", "1404/01/10", 30, "EUR")])],
        ignore_index=True)
    df = pd.concat([_frame(), pd.DataFrame([
        _r("BL1", "R1", "O1", "M9", "بدنه", "SAFE", SATA_KEY_REG="R1", SATA_NO="140300112", SATA_TRACKING_DATE="1403/09/01"),
        _r("BL7", "R1", "O7", "M7", "بدنه", "SAFE", SATA_KEY_REG="R1", SATA_NO="140300113", SATA_TRACKING_DATE="1403/10/01"),
        _r("BL3", "R2", "O2", "M8", "موتور", "SAFE", SATA_KEY_REG="R2", SATA_NO="0", SATA_CREDIT_STATUS="در انتظار تخصیص ارز"),
        _r("BL8", "R5", "O8", "M8", "موتور", "SAFE", SATA_KEY_REG="R5", SATA_CREDIT_STATUS="کد رهگیری دارد"),
        _r("BL9", "R5", "O9", "M8", "موتور", "SAFE", SATA_KEY_REG="R5", SATA_NO="140400999", SATA_TRACKING_DATE="1404/05/01"),
        _r("BL4", "R4", "O4", "M4", "برق", "SAFE", SATA_KEY_REG="R4", SATA_NO="140500001", SATA_TRACKING_DATE="1405/04/01"),
        _r("BL5", "R4", "O5", "M4", "برق", "SAFE", SATA_KEY_REG="R4", SATA_NO="0")])], ignore_index=True)
    st = D.sata_settlement(df, D.ledger({"fx_money_ledger": led})).set_index("KEY_REG")
    assert st.loc["R1", "STATE"] == D.SETTLED and str(st.loc["R1", "DATE"]) == "2024-12-21"   # دیرترین: ۱۴۰۳/۱۰/۰۱
    assert st.loc["R1", "NTSW_FULL"] is True
    assert "R2" not in st.index                                    # کد «۰» یعنی کد ندارد
    assert st.loc["R5", "STATE"] == D.SETTLED_NO_DATE and st.loc["R5", "DATE"] is None        # کد دارد، تاریخ یکی نیست
    assert st.loc["R5", "NTSW_FULL"] is False                      # فقط مقایسه؛ تاریخ را عوض نمی‌کند
    assert st.loc["R4", "STATE"] == D.PARTIAL                      # یکی از دو بارنامه کد دارد
    s = D.build_story(df, {"fx_money_ledger": led}, REF, critical_runs=[])
    ch = {c.key: c for c in s.chapters}
    assert "میانه نخستین تخصیص تا رفع تعهد" in ch["settle"].headline and not ch["settle"].gaps
    assert "تاریخ اخذ کد" in ch["settle"].note
    t = ch["since"].table.set_index("شاخص")
    assert t.loc["میانه نخستین تخصیص تا رفع تعهد", D.PERIOD_BASE] == 185    # ۱۴۰۳/۰۳/۳۰ تا ۱۴۰۳/۱۰/۰۱
    gaps = ch["gaps"].visual
    assert "NTSW نیست" not in gaps and "دلیل خرید" not in gaps


def _snap(levels):
    return D.history_frame(pd.DataFrame([
        {"KEY_ORDER": f"O{i}", "KEY_MATERIAL": f"M{i}", "KEY_REG": reg, "PART_GROUP": g, "کد طبقه بحرانی": lv}
        for i, (reg, g, lv) in enumerate(levels)]))


def test_critical_history_flows_and_purchase_level_at_time():
    from datetime import date
    base = [("R1", "موتور"), ("R2", "موتور"), ("R3", "بدنه"), ("R4", "بدنه"), ("R5", "برق")]
    runs = [(date(2026, 5, 22), _snap([(r, g, l) for (r, g), l in zip(base, ["CRITICAL", "BECOMING_CRITICAL", "STOCKOUT", "SAFE", "CRITICAL"])])),
            (date(2026, 5, 29), _snap([(r, g, l) for (r, g), l in zip(base, ["CRITICAL", "CRITICAL", "CRITICAL", "SAFE", "SAFE"])])),
            (date(2026, 6, 5), _snap([(r, g, l) for (r, g), l in zip(base, ["STOCKOUT", "CRITICAL", "UNKNOWN", "CRITICAL", "SAFE"])]))]
    led = D.ledger({"fx_money_ledger": pd.DataFrame([
        _ev("R4", "FX_PURCHASE", "1405/03/02", 40, "EUR"),      # R4 در Snapshot قبلی ایمن بود
        _ev("R1", "FX_PURCHASE", "1405/03/02", 60, "EUR"),      # R1 بحرانی
        _ev("R2", "FX_PURCHASE", "1405/01/02", 99, "EUR")])})   # پیش از نخستین Snapshot: سطح ندارد
    c = D.ch_critical_history(runs, led)
    assert c.has_data and "از ۱ به ۱" not in c.headline
    t = c.table.set_index("Snapshot")
    assert t.iloc[0]["توقف خط"] == 1 and t.iloc[-1]["توقف خط"] == 1 and t.iloc[-1]["سطح نامشخص"] == 1
    flows = dict(re.findall(r'<b>([۰-۹]+)</b><span>([^<]+)</span>', c.visual)[i][::-1] for i in range(6))
    assert flows["تازه وارد وضعیت بحرانی"] == "۱"                  # R4
    assert flows["بدتر شد (یک پله به سوی توقف خط)"] == "۲"         # R1 بحرانی→توقف، R2 در حال→بحرانی
    assert flows["از وضعیت بحرانی بیرون آمد"] == "۱"               # R5
    assert flows["سطحش نامشخص شد (نه بهبود)"] == "۱"               # R3: نامشخص بهبود نیست
    assert "۶۰٪" in c.visual and "۴۰٪" in c.visual                 # خرید پیش از نخستین Snapshot کنار گذاشته شد
    one = D.ch_critical_history(runs[:1])
    assert one.gaps and "۱ Snapshot" in one.headline


def test_history_loader_reads_only_needed_columns(tmp_path, monkeypatch):
    from gsi.warehouse.framecodec import decode_columns, encode_frame
    df = pd.DataFrame({"KEY_ORDER": ["a"], "کد طبقه بحرانی": ["CRITICAL"], "WIDE": [1.0]})
    assert list(decode_columns(encode_frame(df), D.HISTORY_COLS).columns) == ["KEY_ORDER", "کد طبقه بحرانی"]
    monkeypatch.setenv("GSI_DWH_PATH", str(tmp_path / "none" / "warehouse.sqlite"))
    assert D.load_critical_history() == []                           # انبار نیست: تاریخچه خالی، نه خطا

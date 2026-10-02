# -*- coding: utf-8 -*-
"""بخش‌های ۱۰، ۱۱ و ۱۲ ممیزی دانه (grain_audit/gsi_grain_audit.py) با داده کاملاً ساختگی."""
import importlib.util
import math
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("gsi_grain_audit_under_test",
                                                  ROOT / "grain_audit" / "gsi_grain_audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GA = _load()


class StubRulebook:
    """واژگان ساختگی و کوچک؛ به rules/*.yaml واقعی وابسته نیست."""
    STATES = {"در راه": "IN_TRANSIT", "نزد سازنده": "AT_SUPPLIER", "آماده حمل": "READY", "در گمرک": "IN_CUSTOMS"}

    def part_state(self, v):
        s = "" if v is None else str(v).strip()
        if s.lower() in ("", "nan", "none"):
            return ""
        return self.STATES.get(s, "UNRECOGNIZED")

    def get(self, path, default=None):
        if path == "status_lexicon.part_states":
            return {c: {} for c in self.STATES.values()}
        return default

    def transport_mode(self, v):
        return {"sea": "SEA", "air": "AIR"}.get(str(v or "").strip().lower(), "")

    def parse_status_note(self, v):
        return {"STAGE": "SHIPMENT" if "حمل" in str(v or "") else ""}

    def currency_code(self, v):
        return str(v) if str(v) in ("EUR", "USD") else ""

    def validate_bl(self, v):
        s = re.sub(r"[^A-Z0-9]", "", str(v or "").upper())
        return (len(s) >= 6 and not s.isdigit()), ""


def ctx(mask=False):
    return GA.Ctx(5, mask)


# ── ۱۰: فروریختگی ──
def test_collapse_flags_two_bls_per_order_kept_as_one():
    detail = pd.DataFrame({
        "KEY_ORDER": ["T-ORD-A", "T-ORD-A", "T-ORD-B"],
        "T_BL_NO": ["TSTBL00001", "TSTBL00002", "TSTBL00003"],
        "T_NOTE": ["x", "x", "y"],
    })
    agg_first = pd.DataFrame({"KEY_ORDER": ["T-ORD-A", "T-ORD-B"],
                              "T_BL_NO": ["TSTBL00001", "TSTBL00003"], "T_NOTE": ["x", "y"]})
    rows = {r["ستون"]: r for r in GA.collapse_metrics(detail, agg_first, ["KEY_ORDER"], ctx(), "t")}
    bl = rows["T_BL_NO"]
    assert bl["وضعیت نگهداری"] == GA.KEEP_ONE
    assert bl["گروه کلید"] == 2 and bl["گروه چندمقداری"] == 1
    assert bl["احتمال چندمقداری"] == pytest.approx(0.5)
    assert bl["ردیف اثرپذیر"] == 2
    assert bl["ریسک (سهم × ردیف)"] == pytest.approx(1.0)
    assert "T-ORD-A" in bl["نمونه"]
    assert rows["T_NOTE"]["گروه چندمقداری"] == 0
    # بالاترین ریسک اول
    assert GA.collapse_metrics(detail, agg_first, ["KEY_ORDER"], ctx(), "t")[0]["ستون"] == "T_BL_NO"

    # همان داده وقتی خروجی فهرست کامل (*S_ALL) دارد: فروریختگی نیست
    agg_all = agg_first.assign(T_BLS_ALL=["TSTBL00001، TSTBL00002", "TSTBL00003"])
    kept = {r["ستون"]: r for r in GA.collapse_metrics(detail, agg_all, ["KEY_ORDER"], ctx(), "t")}["T_BL_NO"]
    assert kept["وضعیت نگهداری"] == GA.KEEP_ALL
    assert kept["ریسک (سهم × ردیف)"] == 0

    masked = {r["ستون"]: r for r in GA.collapse_metrics(detail, agg_first, ["KEY_ORDER"], ctx(True), "t")}
    assert "T-ORD-A" not in masked["T_BL_NO"]["نمونه"] and masked["T_BL_NO"]["نمونه"].startswith("#")


def test_counterpart_names():
    cols = ["MOGH_BL_NO", "MOGH_BLS_ALL", "MOGH_BL_COUNT", "MOGH_ORDER_STATUSES_ALL", "MOGH_TRANSPORT_MODES_ALL"]
    assert GA.find_counterparts("MOGH_BL_NO", cols) == {"self": "MOGH_BL_NO", "value": "MOGH_BLS_ALL",
                                                        "count": "MOGH_BL_COUNT"}
    assert GA.find_counterparts("MOGH_ORDER_STATUS", cols)["value"] == "MOGH_ORDER_STATUSES_ALL"
    assert GA.find_counterparts("MOGH_TRANSPORT_MODE_CODE", cols)["value"] == "MOGH_TRANSPORT_MODES_ALL"


# ── ۱۱: واژگان ──
def test_lexicon_flags_unmapped_status_and_quantity_share():
    lines = pd.DataFrame({
        "MOGH_ORDER_STATUS": ["در راه", "وضعیت آزمایشی ناشناخته", "", "در راه"],
        "MOGH_QTY_IN_PART": [10.0, 30.0, 5.0, 5.0],
    })
    rows, summ = GA.lexicon_coverage(lines, "MOGH_ORDER_STATUS", "part_state", StubRulebook(),
                                     "MOGH_QTY_IN_PART", "moghavemat/lines")
    assert summ["ردیف نگاشت‌نشده"] == 1 and summ["مقدار یکتای نگاشت‌نشده"] == 1
    assert summ["مقدار اثرپذیر"] == pytest.approx(30.0)
    assert summ["سهم مقدار اثرپذیر"] == pytest.approx(0.6)
    bad = [r for r in rows if r["نگاشت نشد"]]
    assert [r["مقدار خام"] for r in bad] == ["وضعیت آزمایشی ناشناخته"]
    assert bad[0]["کد نگاشت‌شده"] == "UNRECOGNIZED"
    ok = next(r for r in rows if r["مقدار خام"] == "در راه")
    assert ok["تعداد"] == 2 and ok["کد نگاشت‌شده"] == "IN_TRANSIT"
    assert next(r for r in rows if r["مقدار خام"] == "(خالی)")["نگاشت نشد"] is False

    c = ctx()
    GA.audit_lexicon({"moghavemat": {"lines": lines}}, c, rb=StubRulebook())
    hit = [f for f in c.findings if "MOGH_ORDER_STATUS" in f["موضوع"]]
    assert hit and hit[0]["شدت"] == "بحرانی" and hit[0]["تعداد"] == 1
    assert any(f["موضوع"] == "خلاصه بخش ۱۱" for f in c.findings)


# ── ۱۲: تطبیق ──
def _expert_lines():
    return pd.DataFrame({
        "KEY_ORDER": ["T-ORD-A", "T-ORD-A", "T-ORD-B"],
        "KEY_MATERIAL": ["T-MAT-1", "T-MAT-1", "T-MAT-2"],
        "MOGH_PART_NO_PARTIAL": ["", "", "P1"],
        "MOGH_QTY_IN_PART": [4.0, 6.0, 3.0],
        "MOGH_CLEARED_QTY": [None, None, None],
        "MOGH_ORDER_STATUS": ["در راه", "در راه", "نزد سازنده"],
        "MOGH_BL_RAW": ["TSTU 000001", "TSTU.000002", ""],
        "MOGH_TRANSPORT_NO": ["", "", ""],
    })


def test_reconcile_counts_two_shipments_without_part_no_as_two():
    exp = GA.expert_positions(_expert_lines(), StubRulebook(),
                              ["AT_SUPPLIER", "READY", "IN_TRANSIT", "IN_CUSTOMS"])
    a = exp[exp.KEY_ORDER == "T-ORD-A"].iloc[0]
    assert a["SHIPMENTS"] == 2
    assert a["QTY_IN_TRANSIT"] == pytest.approx(10.0)
    assert a["QTY_AT_SUPPLIER"] == 0 and a["QTY_UNKNOWN"] == 0
    assert set(a["BLS"]) == {"TSTU000001", "TSTU000002"}
    b = exp[exp.KEY_ORDER == "T-ORD-B"].iloc[0]
    assert b["QTY_AT_SUPPLIER"] == pytest.approx(3.0)

    # یک وضعیت ناشناخته: وضعیت‌های صفر نامعلوم می‌مانند، صفر ساخته نمی‌شود
    unk = _expert_lines().assign(MOGH_ORDER_STATUS=["در راه", "وضعیت آزمایشی ناشناخته", "نزد سازنده"])
    ua = GA.expert_positions(unk, StubRulebook(), ["AT_SUPPLIER", "IN_TRANSIT"])
    ua = ua[ua.KEY_ORDER == "T-ORD-A"].iloc[0]
    assert ua["QTY_UNKNOWN"] == pytest.approx(6.0) and ua["QTY_IN_TRANSIT"] == pytest.approx(4.0)
    assert math.isnan(ua["QTY_AT_SUPPLIER"])


def test_reconcile_reports_quantity_mismatch_and_missing_bl():
    inventory = pd.DataFrame({  # خروجی معیوب: دو محموله بی‌Part No. یکی شده (بیشینه)
        "KEY_ORDER": ["T-ORD-A", "T-ORD-B"], "KEY_MATERIAL": ["T-MAT-1", "T-MAT-2"],
        "MOGH_QTY_AT_SUPPLIER": [0.0, 3.0], "MOGH_QTY_READY": [0.0, 0.0],
        "MOGH_QTY_IN_TRANSIT": [6.0, 0.0], "MOGH_QTY_IN_CUSTOMS": [0.0, 0.0],
        "MOGH_QTY_STATE_UNKNOWN": [0.0, 0.0]})
    main = pd.DataFrame({  # خروجی معیوب: فقط اولین بارنامه
        "KEY_ORDER": ["T-ORD-A", "T-ORD-B"], "KEY_MATERIAL": ["T-MAT-1", "T-MAT-2"],
        "MOGH_BL_NO": ["TSTU000001", ""], "MOGH_ORDER_STATUS": ["در راه", "نزد سازنده"]})
    c = ctx()
    exp, qty_rows, set_rows = GA.reconcile(
        _expert_lines(), {"inv": (inventory, "om"), "main": (main, "om")}, c, StubRulebook())
    it = next(r for r in qty_rows if r["خروجی اپ"] == "inv" and r["ستون اپ"] == "MOGH_QTY_IN_TRANSIT"
              and r["سنجه"].startswith("وضعیت"))
    assert it["مقدار متفاوت"] == 1 and it["برابر"] == 1 and it["ناهمخوانی"] == 1
    assert it["نرخ ناهمخوانی"] == pytest.approx(0.5)
    assert "T-ORD-A" in it["نمونه"]
    sup = next(r for r in qty_rows if r["خروجی اپ"] == "inv" and r["ستون اپ"] == "MOGH_QTY_AT_SUPPLIER")
    assert sup["ناهمخوانی"] == 0

    bl_all = next(r for r in set_rows if r["خروجی اپ"] == "main" and r["موضوع"] == "بارنامه"
                  and r["ستون اپ"] == "همه ستون‌ها")
    assert bl_all["مقدار در فایل کارشناسان"] == 2
    assert bl_all["پیدا شد"] == 1 and bl_all["نیست"] == 1
    assert bl_all["نیست: معتبر در rulebook"] == 1
    assert "TSTU.000002" in bl_all["نمونه"]
    # inventory ستون بارنامه ندارد: گفته می‌شود، عدد ساخته نمی‌شود
    inv_bl = [r for r in set_rows if r["خروجی اپ"] == "inv" and r["موضوع"] == "بارنامه"]
    assert len(inv_bl) == 1 and "نیست" not in inv_bl[0] and inv_bl[0]["توضیح"]


def test_norm_bl_keeps_only_letters_and_digits():
    assert GA.norm_bl(" tstu 0000.01 ") == "TSTU000001"
    assert GA.norm_bl("123-4567 8901") == "12345678901"
    assert GA.norm_bl("۱۲۳۴۵۶۷۸۹۰۱") == "12345678901"
    assert GA.norm_bl(None) == ""


def test_item_value_repeated_on_parts_is_expected_once_and_a_row_sum_is_flagged():
    lines = pd.DataFrame({
        "KEY_ORDER": ["O1"] * 3, "KEY_MATERIAL": ["M1"] * 3, "MOGH_PR_NO": ["P1"] * 3, "MOGH_PR_ITEM": ["10"] * 3,
        "MOGH_PART_NO_PARTIAL": ["1", "2", "3"], "MOGH_QTY_IN_ORDER": [900] * 3,
        "MOGH_PI_LINE_VALUE": [4500] * 3, "MOGH_CURRENCY": ["CNY"] * 3})
    tot = GA.expert_item_totals(lines).iloc[0]
    assert tot["ORDER_QTY"] == 900 and tot["PI_VALUE"] == 4500 and tot["ROWS_SUM_ORDER_QTY"] == 2700
    app = pd.DataFrame({"KEY_ORDER": ["O1"], "MOGH_ORDER_QTY_SUM": [2700], "MOGH_PI_VALUE_SUM": [4500]})
    rows = GA.compare_measures(GA.expert_item_totals(lines), app,
                               [("q", "ORDER_QTY", "MOGH_ORDER_QTY_SUM"), ("v", "PI_VALUE", "MOGH_PI_VALUE_SUM")],
                               "main", GA.Ctx(5, False), keys=("KEY_ORDER",))
    assert [r["ناهمخوانی"] for r in rows] == [1, 0]

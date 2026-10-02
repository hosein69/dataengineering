"""29.15.13 — برگ تصمیم HTML و تب تأمین خاموش با تنظیم صریح.

قواعد مدل تصمیم مالک که این‌جا قفل می‌شوند:
* ترتیب DONE / OWNER / DATE / RISK / NEXT / ASK؛
* نامعلوم ≠ صفر (ستون غایب → «نامشخص»، نه ۰)؛
* ASK فقط با شاهد؛ بدون شاهد: «درخواستی از مدیر نیست»؛
* دروازه مالکیت و بستن (بدون مالک / بدون موعد)؛
* فقط از df همین خروجی (نه extras، نه ستون بیرون از دامنه).
"""
import dataclasses
import re
from unittest import mock

import pandas as pd

import gsi.config.settings as settings
from gsi.report.decision_brief import (GATE_EVIDENCE, GATE_NO_DATE, GATE_OWNERLESS, GATE_READY,
                                       build_decision_brief_html, compute_decision_brief)
from gsi.studio_core.html_export import build_dynamic_html

REF = "2026-08-31"


def _row(reg, mat, band="SAFE", res=60, aid="", title="", owner="", due="", prio="", gaps="", order=None):
    return {"KEY_REG": reg, "CANONICAL_ORDER": order or f"O{reg}", "KEY_MATERIAL": mat,
            "کد طبقه بحرانی": band, "مقاومت (روز)": res, "بحرانی (کوتاه)": band,
            "NEXT_ACTION_ID": aid, "NEXT_ACTION_TITLE": title, "NEXT_ACTION_OWNER": owner,
            "NEXT_ACTION_DUE_DATE": due, "NEXT_ACTION_PRIORITY": prio,
            "NEXT_ACTION_EVIDENCE_GAPS": gaps, "NEXT_ACTION_DAYS": None}


def _df():
    return pd.DataFrame([
        # یک اقدام، دو متریال (Order×Material) — باید یک اقدام شمرده شود
        _row("R1", "M1", "CRITICAL", 5, "ACT-1", "پیگیری رفع تعهد", "رفع تعهد/بانک عامل", "2026-08-20", "CRITICAL"),
        _row("R1", "M2", "SAFE", 90, "ACT-1", "پیگیری رفع تعهد", "رفع تعهد/بانک عامل", "2026-08-20", "CRITICAL"),
        # بدون مالک
        _row("R2", "M3", "WATCH", 30, "ACT-2", "ارائه سند", "", "2026-09-10", "HIGH"),
        # بدون موعد
        _row("R3", "M4", "SAFE", 80, "ACT-3", "ثبت شاهد", "کارشناس ترخیص", "", "MEDIUM"),
        # شاهد ناقص ولی آماده اجرا
        _row("R4", "M5", "SAFE", 80, "ACT-4", "تطبیق بانک", "کارشناس ترخیص", "2026-09-05", "LOW", gaps="رسید بانک"),
        # توقف خط بدون هیچ اقدامی
        _row("R5", "M6", "STOCKOUT", 0),
    ]).assign(**{"اقدام پیشنهادی مقاومت": "اقدام اضطراری"})


def _section(h):
    i = h.find('id="decision_brief"')
    assert i >= 0
    j = h.find('<nav class="tabbar', i)
    return h[i:j if j > 0 else None]


def test_actions_deduplicated_gated_and_ordered():
    b = compute_decision_brief(_df(), REF)
    ids = [a["id"] for a in b["actions"]]
    assert sorted(ids) == ["ACT-1", "ACT-2", "ACT-3", "ACT-4"]          # ACT-1 یک بار
    a1 = next(a for a in b["actions"] if a["id"] == "ACT-1")
    assert a1["materials"] == ["M1", "M2"]
    gates = {a["id"]: a["gate"] for a in b["actions"]}
    assert gates == {"ACT-1": GATE_READY, "ACT-2": GATE_OWNERLESS,
                     "ACT-3": GATE_NO_DATE, "ACT-4": GATE_EVIDENCE}
    # معوق اول، سپس اولویت (HIGH > MEDIUM > LOW)، سپس موعد
    assert ids == ["ACT-1", "ACT-2", "ACT-3", "ACT-4"] and a1["days"] == -11
    assert b["next"]["id"] == "ACT-1"


def test_owner_date_risk_ask_from_evidence():
    b = compute_decision_brief(_df(), REF)
    assert b["ownerless"] == 1
    assert dict(b["owners"]) == {"رفع تعهد/بانک عامل": 1, "کارشناس ترخیص": 2}
    assert b["overdue"] == 1 and b["overdue_critical"] == 1 and b["undated"] == 1
    assert b["next_due"]["id"] == "ACT-4"
    mats = {m["material"]: m for m in b["risk"]}
    assert set(mats) == {"M1", "M6"} and mats["M6"]["has_action"] is False
    assert mats["M6"]["advice"] == "اقدام اضطراری"            # توصیه s40 هست ولی مالک/موعد ندارد
    assert [m["material"] for m in b["risk"]][0] == "M6"               # توقف خط اول
    assert len(b["asks"]) == 3
    assert any("بدون مالک" in a for a in b["asks"])
    assert any("در صف اقدام نیست" in a for a in b["asks"])
    assert any("موعدش گذشته" in a for a in b["asks"])
    assert b["orders"] == 5 and b["materials"] == 6 and b["regs"] == 5


def test_no_evidence_no_ask():
    df = pd.DataFrame([_row("R1", "M1", "SAFE", 90, "ACT-1", "پیگیری", "کارشناس", "2026-09-30", "LOW")])
    b = compute_decision_brief(df, REF)
    assert b["asks"] == []
    h = build_decision_brief_html(df, REF)
    assert "درخواستی از مدیر نیست" in h


def test_unknown_is_not_zero():
    df = pd.DataFrame([{"KEY_REG": "R1", "CANONICAL_ORDER": "O1", "KEY_MATERIAL": "M1"}])
    b = compute_decision_brief(df, REF)
    assert b["owners"] is None and b["ownerless"] is None and b["overdue"] is None
    assert b["risk"] is None and b["risk_without_action"] is None
    assert b["asks"] == []
    h = build_decision_brief_html(df, REF)
    for key in ("OWNER", "DATE", "RISK", "NEXT"):
        card = re.search(rf'<section class="dcard"[^>]*data-brief="{key}".*?</section>', h, re.S).group(0)
        assert 'data-tone="unknown"' in card and "نامشخص" in card
        assert re.search(r">\s*0 ", card) is None
    assert "NEXT_ACTION_OWNER" in h and "کد طبقه بحرانی" in h         # ستون غایب نام برده می‌شود


def test_brief_is_first_after_header_in_norouzani_order():
    h = build_dynamic_html(_df(), REF, title="GSI")
    i = h.find('id="decision_brief"')
    assert 0 < i < h.find('<nav class="tabbar')
    keys = re.findall(r'data-brief="([A-Z]+)"', h)
    assert keys == ["DONE", "OWNER", "DATE", "RISK", "NEXT", "ASK"]
    assert "بدون مالک — آماده اجرا نیست" in h and "بدون موعد — هنوز Task نشده" in h
    # هر کارت ستون منبعش را اعلام می‌کند
    assert h.count('class="src"') == 6


def test_brief_reads_only_this_outputs_dataframe():
    df = _df().drop(columns=["NEXT_ACTION_OWNER"])
    extras = {"case_actions": pd.DataFrame([{"KEY_REG": "R1", "OWNER_ROLE": "SECRET_OWNER_ROLE",
                                             "TITLE": "x", "PRIORITY": "CRITICAL"}])}
    h = build_dynamic_html(df, REF, title="GSI", process_extras=extras)
    brief = _section(h)
    assert "SECRET_OWNER_ROLE" not in brief
    assert "رفع تعهد/بانک عامل" not in brief
    owner = re.search(r'data-brief="OWNER".*?</section>', brief, re.S).group(0)
    assert "نامشخص" in owner


def test_escaping():
    df = pd.DataFrame([_row("<b>R</b>", "M<script>", "CRITICAL", 1, "A1", "<img src=x onerror=alert(1)>",
                            "o<i>", "2026-09-01", "HIGH")])
    h = build_decision_brief_html(df, REF)
    assert "<script>" not in h and "<img" not in h and "<i>" not in h and "<b>R</b>" not in h


def test_brief_switch_and_setting():
    df = _df()
    assert 'id="decision_brief"' not in build_dynamic_html(df, REF, include_decision_brief=False)
    off = dataclasses.replace(settings.SETTINGS, HTML_DECISION_BRIEF=False)
    with mock.patch.object(settings, "SETTINGS", off):
        assert 'id="decision_brief"' not in build_dynamic_html(df, REF)
    assert settings.Settings().HTML_DECISION_BRIEF is True


def test_supply_tab_off_by_default_on_by_setting_or_argument():
    df = pd.DataFrame([{"KEY_MATERIAL": "MAT-1", "CANONICAL_ORDER": "O1", "CANONICAL_BL": "B1",
                        "KEY_REG": "R1", "بحرانی (کوتاه)": "بحرانی", "مقاومت (روز)": 4, "STAGE_FA": "حمل"}])
    tab = 'دید تأمین — متریال محور</button>'
    assert settings.Settings().HTML_SUPPLY_MATERIAL_TAB is False
    off = build_dynamic_html(df, REF)
    assert tab not in off
    # خاموش یعنی داده‌اش هم در فایل نیست. بسته تحویلی فقط تب را پنهان می‌کرد و در A/B
    # (داده ۴۰ برابر) ۳۳۸KB داده متریال نادیده در هر HTML می‌ماند (Confidentiality Gate).
    assert "const MATERIAL_SUPPLY_DATA=[];" in off and "MAT-1" not in off.split("const MATERIAL_SUPPLY_DATA=")[1][:50]
    assert build_dynamic_html(df, REF, include_material_view=True).count(tab) == 1
    on = dataclasses.replace(settings.SETTINGS, HTML_SUPPLY_MATERIAL_TAB=True)
    with mock.patch.object(settings, "SETTINGS", on):
        assert build_dynamic_html(df, REF).count(tab) == 1
    with mock.patch.dict("os.environ", {"GSI_HTML_SUPPLY_TAB": "1"}):
        assert settings.Settings().HTML_SUPPLY_MATERIAL_TAB is True


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))

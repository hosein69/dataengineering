# -*- coding: utf-8 -*-
"""نماهای Kanban/Scrum — درستی محاسبه و صداقت نمایش."""
from __future__ import annotations

import pandas as pd
import pytest

from gsi.report import process_insights as PI
from gsi.studio_core import process_views_html as PV
from gsi.studio_core.composer import PROCESS_VIEWS, DEFAULT_PROCESS_VIEWS
from gsi.studio_core.html_export import build_dynamic_html


def _eventlog() -> pd.DataFrame:
    rows = [
        ("C1", "ثبت سفارش", "2026-01-05", 1, "بازرگانی"),
        ("C1", "تخصیص ارز", "2026-01-20", 2, "مالی"),
        ("C1", "ترخیص", "2026-02-10", 3, "گمرک"),
        ("C2", "ثبت سفارش", "2026-01-12", 1, "بازرگانی"),
        ("C2", "تخصیص ارز", "2026-02-02", 2, "مالی"),
        ("C2", "تخصیص ارز", "2026-02-09", 2, "مالی"),      # دوباره‌کاری واقعی
        ("C3", "ثبت سفارش", "2026-02-01", 1, "بازرگانی"),
    ]
    return pd.DataFrame(rows, columns=["_CASE_KEY", "ACTIVITY_FA", "EVENTTIME",
                                       "_SORTING", "ORG_UNIT"])


def _case_table() -> pd.DataFrame:
    return pd.DataFrame([
        dict(CASE_KEY="C1", CASE_STATE="CLOSED", LAST_EVENT="2026-02-10",
             LAST_ACTIVITY="ترخیص", THROUGHPUT_DAYS=36, CASE_AGE_DAYS=36,
             CURRENT_WAIT_DAYS=0, VARIANT="مسیر کامل"),
        dict(CASE_KEY="C2", CASE_STATE="OPEN", LAST_EVENT="2026-02-09",
             LAST_ACTIVITY="تخصیص ارز", THROUGHPUT_DAYS=None, CASE_AGE_DAYS=100,
             CURRENT_WAIT_DAYS=28, VARIANT="مسیر کوتاه"),
        dict(CASE_KEY="C3", CASE_STATE="OPEN", LAST_EVENT="2026-02-01",
             LAST_ACTIVITY="ثبت سفارش", THROUGHPUT_DAYS=None, CASE_AGE_DAYS=9,
             CURRENT_WAIT_DAYS=9, VARIANT="مسیر کوتاه"),
    ])


# ═════════ محاسبه ═════════

def test_cumulative_flow_counts_each_case_once_per_stage():
    cfd = PI.cumulative_flow(_eventlog())
    assert not cfd.empty
    last = cfd.sort_values("دوره").groupby("مرحله").tail(1).set_index("مرحله")
    assert last.loc["ثبت سفارش", "پرونده رسیده (انباشتی)"] == 3
    # C2 دوبار «تخصیص ارز» دارد؛ انباشتی باید ۲ پرونده باشد نه ۳ رویداد
    assert last.loc["تخصیص ارز", "پرونده رسیده (انباشتی)"] == 2


def test_cumulative_flow_is_monotonic_per_stage():
    cfd = PI.cumulative_flow(_eventlog())
    for _, g in cfd.groupby("مرحله"):
        v = list(g.sort_values("دوره")["پرونده رسیده (انباشتی)"])
        assert v == sorted(v), "منحنی انباشتی هرگز نباید پایین بیاید"


def test_throughput_counts_only_closed_cases():
    t = PI.throughput(_case_table())
    assert int(t["پرونده بسته‌شده"].sum()) == 1


def test_aging_wip_lists_only_open_cases_with_historic_benchmark():
    a = PI.aging_wip(_case_table())
    assert set(a["پرونده"]) == {"C2", "C3"}
    # فقط یک پروندهٔ بسته وجود دارد، پس مبنای صدک کافی نیست و ادعا نمی‌شود
    assert set(a["هشدار"]) == {"مبنای تاریخی کافی نیست"}
    assert a["صدک ۵۰ تاریخی"].isna().all()


def test_percentiles_are_withheld_below_the_minimum_sample():
    ct = _case_table()
    c = PI.cycle_time_percentiles(ct)
    row = c[c["گروه"] == "مسیر کامل"].iloc[0]
    assert row["پرونده بسته"] == 1
    assert pd.isna(row["صدک ۵۰ (روز)"]), "با یک مشاهده صدک گزارش نمی‌شود"
    assert row["بیشینه (روز)"] == 36


def test_percentiles_appear_once_there_is_enough_history():
    ct = pd.DataFrame([dict(CASE_KEY=f"C{i}", CASE_STATE="CLOSED",
                            LAST_EVENT="2026-02-10", LAST_ACTIVITY="ترخیص",
                            THROUGHPUT_DAYS=d, CASE_AGE_DAYS=d,
                            CURRENT_WAIT_DAYS=0, VARIANT="V")
                       for i, d in enumerate([10, 20, 30, 40, 100])])
    c = PI.cycle_time_percentiles(ct).iloc[0]
    assert c["صدک ۵۰ (روز)"] == 30
    assert c["صدک ۸۵ (روز)"] >= c["صدک ۵۰ (روز)"]
    assert c["بیشینه (روز)"] == 100


def test_rework_reports_the_repeated_activity_only():
    r = PI.rework_loops(_eventlog())
    assert list(r["فعالیت"]) == ["تخصیص ارز"]
    assert int(r.iloc[0]["کل تکرار اضافه"]) == 1
    assert int(r.iloc[0]["پرونده با تکرار"]) == 1


def test_handoff_ignores_staying_in_the_same_unit():
    h = PI.handoff_matrix(_eventlog())
    pairs = set(zip(h["از"], h["به"]))
    assert ("مالی", "مالی") not in pairs, "ماندن در یک واحد تحویل نیست"
    assert ("بازرگانی", "مالی") in pairs


def test_every_metric_degrades_to_an_empty_frame_not_a_crash():
    for fn in (PI.cumulative_flow, PI.throughput, PI.aging_wip,
               PI.cycle_time_percentiles, PI.rework_loops, PI.handoff_matrix,
               PI.stage_evidence_coverage):
        assert fn(None).empty
        assert fn(pd.DataFrame()).empty
        assert fn(pd.DataFrame({"irrelevant": [1, 2]})).empty


def test_stage_coverage_separates_unmeasured_from_not_done():
    matrix = pd.DataFrame([
        dict(PROCESS_CASE_ID="P1", STAGE_FA="ثبت سفارش", STAGE_ORDER=1, OBSERVATION_COUNT=2),
        dict(PROCESS_CASE_ID="P2", STAGE_FA="ثبت سفارش", STAGE_ORDER=1, OBSERVATION_COUNT=0),
        dict(PROCESS_CASE_ID="P1", STAGE_FA="ترخیص", STAGE_ORDER=2, OBSERVATION_COUNT=0),
        dict(PROCESS_CASE_ID="P2", STAGE_FA="ترخیص", STAGE_ORDER=2, OBSERVATION_COUNT=0),
    ])
    cov = PI.stage_evidence_coverage(matrix).set_index("مرحله")
    assert cov.loc["ثبت سفارش", "پوشش (٪)"] == 50.0
    assert cov.loc["ترخیص", "پرونده بدون شاهد"] == 2


# ═════════ نمایش ═════════

def test_catalog_grew_and_every_view_has_a_renderer():
    assert len(PROCESS_VIEWS) == 15, "هشت نمای قبلی + هفت نمای Kanban/Scrum"
    for key in PV.RENDERERS:
        assert key in PROCESS_VIEWS, f"نمای «{key}» در فهرست Composer نیست"
    for key in DEFAULT_PROCESS_VIEWS:
        assert key in PROCESS_VIEWS


def test_an_empty_view_states_its_reason_instead_of_a_blank_box():
    extras = {"eventlog": pd.DataFrame(), "case_table": pd.DataFrame()}
    for key in PV.RENDERERS:
        html = PV.render(key, dict(extras))
        assert "<div class=\"empty\">" in html
        body = html.split('<div class="empty">')[1].split("</div>")[0].strip()
        assert len(body) > 20, f"نمای «{key}» علت خالی‌بودن را نمی‌گوید"


def test_views_render_real_svg_and_reach_the_exported_html():
    extras = {"eventlog": _eventlog(), "case_table": _case_table()}
    df = pd.DataFrame({"KEY_MATERIAL": ["M1"], "ORG_DEPT": ["A"], "_CASE_KEY": ["C1"]})
    html = build_dynamic_html(
        df, "2026-03-01", process_extras=extras,
        tabs=[{"id": "p", "title": "فرآیند", "blocks": ["process"],
               "fields": ["KEY_MATERIAL"], "process_views": list(PROCESS_VIEWS)}])
    assert html.count('class="process-viz') == 15
    assert html.count(".gsi-chart{width:100%") == 1, "CSS باید یک بار بیاید، نه در هر پنل"
    assert "Cumulative Flow" in html and "Aging WIP" in html


def test_no_view_presents_an_observation_as_a_target():
    """صدک مشاهده‌شده نباید به‌جای هدف یا تعهد خوانده شود."""
    extras = {"eventlog": _eventlog(), "case_table": _case_table(),
              "process_stage_matrix": pd.DataFrame([
                  dict(PROCESS_CASE_ID="P1", STAGE_FA="ثبت سفارش", STAGE_ORDER=1,
                       OBSERVATION_COUNT=1)])}
    must_say = {
        "aging_wip": "«هدف» نیستند",
        "throughput": "نه ظرفیت وعده‌داده‌شده",
        "cycle_percentiles": "بسته شده‌اند",
        "stage_coverage": "یعنی اندازه‌گیری نشده، نه انجام‌نشده",
        "rework": "لزوماً خطا نیست",
        "handoff": "زمان انتظار است نه زمان کار",
        "cfd": "کارِ در جریان",
    }
    for key in PV.RENDERERS:
        html = PV.render(key, dict(extras))
        assert must_say[key] in html, f"نمای «{key}» محدودهٔ ادعایش را نمی‌گوید"
        for banned in ("SLA", "تضمین", "پیش‌بینی می‌کند"):
            assert banned not in html, f"نمای «{key}» ادعای «{banned}» می‌کند"


# ═════════ لِین‌های کانبان ═════════

def _actions() -> pd.DataFrame:
    return pd.DataFrame([
        dict(KEY_REG="R1", TITLE="پیگیری صف تخصیص", OWNER_ROLE="خزانه",
             PRIORITY="CRITICAL", STATUS="PENDING_REVIEW", DUE_DATE="2026-01-01",
             DAYS_REMAINING=-5, ACTION_CODE="FOLLOW_ALLOCATION_QUEUE",
             EVIDENCE_GAPS="ALLOCATION"),
        dict(KEY_REG="R2", TITLE="ارائه اسناد بانکی", OWNER_ROLE="اعتبارات",
             PRIORITY="MEDIUM", STATUS="PENDING_REVIEW", DUE_DATE="2026-03-01",
             DAYS_REMAINING=20, ACTION_CODE="BANK_DOCS_COMMITMENT_OPEN",
             EVIDENCE_GAPS=""),
    ])


def test_kanban_offers_the_new_work_mix_and_blocked_lanes():
    from gsi.studio_core.composer import KANBAN_MODES
    assert "action_code" in KANBAN_MODES and "evidence" in KANBAN_MODES


def test_kanban_evidence_mode_separates_ready_from_blocked():
    import re
    from gsi.studio_core.html_export import _kanban_board_html
    html = _kanban_board_html({"case_actions": _actions()}, "evidence")
    lanes = dict(re.findall(r'<header><h3>(.*?)</h3><span>(\d+)</span>', html))
    assert lanes == {"مسدود — شکاف شاهد": "1", "آماده اقدام": "1"}


def test_kanban_action_code_mode_groups_by_work_type():
    import re
    from gsi.studio_core.html_export import _kanban_board_html
    html = _kanban_board_html({"case_actions": _actions()}, "action_code")
    lanes = dict(re.findall(r'<header><h3>(.*?)</h3><span>(\d+)</span>', html))
    assert set(lanes) == {"FOLLOW_ALLOCATION_QUEUE", "BANK_DOCS_COMMITMENT_OPEN"}


def test_kanban_says_so_when_there_is_no_action_queue():
    from gsi.studio_core.html_export import _kanban_board_html
    html = _kanban_board_html({}, "evidence")
    assert "Action Queue واقعی برای این دامنه موجود نیست" in html

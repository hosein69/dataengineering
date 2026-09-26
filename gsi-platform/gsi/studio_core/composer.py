# -*- coding: utf-8 -*-
"""Report Composer contracts for GSI Studio.

V28.4 makes a report tab a *self-contained document slice*.  A tab owns its
fields, block order, chart selection, process visualisations and kanban mode.
Nothing presentation-related is implicitly shared between tabs.
"""
from __future__ import annotations

from hashlib import sha1
from typing import Any, Dict, Iterable, List
from uuid import uuid4

SIZES: Dict[str, str] = {"full": "تمام عرض", "half": "نیم عرض", "third": "یک‌سوم", "quarter": "یک‌چهارم"}

BLOCKS: Dict[str, str] = {
    "story": "روایت تصمیم / Decision Story",
    "kpi": "کارت‌های KPI",
    "charts": "نمودارهای تحلیلی",
    "cashflow": "برج کنترل جریان پول / FX",
    "process": "Process Mining تخصصی",
    "kanban": "کانبان / Action Board",
    "table": "جدول تفصیلی",
    "quality": "کیفیت داده و Lineage",
}

# Specialized process views.  These are intentionally different questions,
# not cosmetic variants of one bar chart.
PROCESS_VIEWS: Dict[str, str] = {
    "flow_map": "نقشه جریان فرآیند و WIP",
    "stage_aging": "Aging مراحل / زمان انتظار جاری",
    "bottleneck": "رتبه‌بندی گلوگاه گذارها",
    "transition_heatmap": "Heatmap گذارها",
    "variants": "Variant Explorer",
    "conformance": "Conformance / انحراف فرآیند",
    "funnel": "Funnel عبور پرونده‌ها",
    "case_timeline": "Case Timeline تعاملی",
    # ── نماهای Kanban/Scrum (V29.8) ──
    # هشت نمای بالا وضعیت «الان» را می‌گویند. این هفت‌تا سه پرسش دیگر را جواب
    # می‌دهند: روند کار در جریان، نرخ واقعی تحویل، و پیرترین پروندهٔ بازِ امروز.
    "cfd": "Cumulative Flow — روند انباشت مراحل",
    "throughput": "Throughput — نرخ بسته‌شدن پرونده",
    "aging_wip": "Aging WIP — سن پروندهٔ باز",
    "cycle_percentiles": "توزیع زمان چرخه (صدک ۵۰/۸۵/۹۵)",
    "rework": "دوباره‌کاری و حلقهٔ فرآیند",
    "handoff": "تحویل بین واحدها",
    "stage_coverage": "پوشش شاهد در هر مرحله",
}

KANBAN_MODES: Dict[str, str] = {
    "due_window": "بر اساس موعد: معوق / این هفته / بعدی / Backlog",
    "priority": "بر اساس اولویت اقدام",
    "owner": "بر اساس مالک اقدام",
    "status": "بر اساس وضعیت واقعی Action Queue",
    # دو پرسش کانبانی که با ستون‌های موجود قابل جواب بود ولی لِین نداشت:
    # ترکیب نوع کار، و اینکه چه سهمی از Backlog اصلاً «قابل شروع» نیست.
    "action_code": "بر اساس نوع اقدام (ترکیب کار)",
    "evidence": "آماده اقدام در برابر مسدود به‌دلیل شکاف شاهد",
}

KANBAN_CARD_FIELDS: Dict[str, str] = {
    "title": "اقدام بعدی",
    "owner": "مالک",
    "due": "موعد / روز باقیمانده",
    "priority": "اولویت",
    "reason": "علت / Rationale",
    "evidence": "شکاف شواهد",
    "basis": "مبنای Rule",
}

DEFAULT_PROCESS_VIEWS = ["flow_map", "stage_aging", "bottleneck", "variants",
                         "aging_wip", "cfd", "throughput", "stage_coverage"]
DEFAULT_KANBAN_FIELDS = ["title", "owner", "due", "priority", "evidence"]

DEFAULT_BLOCKS = {
    "expert": ["story", "cashflow", "kanban", "table", "charts", "process"],
    "manager": ["story", "kpi", "cashflow", "process", "kanban", "charts", "table"],
    "executive": ["story", "kpi", "cashflow", "charts", "process"],
    "analyst": ["story", "kpi", "cashflow", "process", "charts", "kanban", "table", "quality"],
}

HEADER_PRESETS: Dict[str, Dict[str, str]] = {
    "figma_aqua": {
        "fa": "Figma Aqua — Process First",
        "title": "هوشمندی زنجیره خرید خارجی",
        "subtitle": "Data • Process • Decision",
    },
    "executive_navy": {
        "fa": "Executive Navy — مدیریتی",
        "title": "گزارش مدیریتی زنجیره تأمین",
        "subtitle": "استثناءها، تصمیم‌ها و اقدامات اولویت‌دار",
    },
    "minimal": {
        "fa": "Minimal — مینیمال",
        "title": "GSI",
        "subtitle": "Global Sourcing Intelligence",
    },
}


def make_tab_id() -> str:
    """A short opaque id persisted in session/design JSON.

    The id, not the tab index/title, is used for Streamlit widget keys.  That
    keeps state stable when tabs are renamed, removed or reordered.
    """
    return "tab_" + uuid4().hex[:10]


def _legacy_tab_id(i: int, title: str) -> str:
    token = sha1(f"{i}|{title}".encode("utf-8")).hexdigest()[:10]
    return "tab_" + token


def normalize_blocks(value: Iterable[str] | None, persona: str = "expert") -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in list(value or DEFAULT_BLOCKS.get(persona, DEFAULT_BLOCKS["expert"])):
        k = str(x).strip()
        if k in BLOCKS and k not in seen:
            seen.add(k)
            out.append(k)
    return out or list(DEFAULT_BLOCKS.get(persona, DEFAULT_BLOCKS["expert"]))


def _pick_known(value: Iterable[str] | None, catalog: Dict[str, str], default: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in list(value or default):
        k = str(x).strip()
        if k in catalog and k not in seen:
            seen.add(k)
            out.append(k)
    return out or list(default)



def _normalize_size_map(value: Any, keys: Iterable[str], default: str) -> Dict[str, str]:
    raw = dict(value or {}) if isinstance(value, dict) else {}
    return {str(k): (str(raw.get(k)) if str(raw.get(k)) in SIZES else default) for k in keys}

def normalize_tabs(tabs: List[Dict[str, Any]] | None, fields: List[str], persona: str,
                   default_charts: Iterable[str] | None = None) -> List[Dict[str, Any]]:
    """Upgrade old design JSON and return isolated per-tab configuration."""
    src = tabs or [{"title": "نمای اصلی", "fields": list(fields)}]
    chart_default = list(default_charts or [])
    out: List[Dict[str, Any]] = []
    used_ids: set[str] = set()
    for i, raw in enumerate(src):
        t = dict(raw or {})
        title = str(t.get("title") or f"تب {i+1}")
        tid = str(t.get("id") or _legacy_tab_id(i, title)).strip()
        if tid in used_ids:
            tid = make_tab_id()
        used_ids.add(tid)
        t["id"] = tid
        t["title"] = title
        t["fields"] = list(t.get("fields") or fields)
        t["blocks"] = normalize_blocks(t.get("blocks"), persona)
        t["block_sizes"] = _normalize_size_map(t.get("block_sizes"), t["blocks"], "full")
        # New fields are tab-owned.  Old designs fall back to the global chart
        # list exactly once during migration, then persist independently.
        # Legacy global HTML charts are migrated to the first tab only.  Copying
        # them into every tab recreates the old global-state bug and makes tabs
        # appear identical even though their widget keys are independent.
        if "charts" in t:
            t["charts"] = list(dict.fromkeys(t.get("charts") or []))
        else:
            t["charts"] = list(dict.fromkeys(chart_default if i == 0 else []))
        t["chart_sizes"] = _normalize_size_map(t.get("chart_sizes"), t["charts"], "half")
        t["process_views"] = _pick_known(t.get("process_views"), PROCESS_VIEWS,
                                         DEFAULT_PROCESS_VIEWS)
        t["process_sizes"] = _normalize_size_map(t.get("process_sizes"), t["process_views"], "full")
        mode = str(t.get("kanban_mode") or "due_window")
        t["kanban_mode"] = mode if mode in KANBAN_MODES else "due_window"
        t["kanban_card_fields"] = _pick_known(t.get("kanban_card_fields"),
                                               KANBAN_CARD_FIELDS,
                                               DEFAULT_KANBAN_FIELDS)
        t["max_rows"] = int(t.get("max_rows") or 0)
        out.append(t)
    return out


def new_tab(title: str, fields: List[str], persona: str = "expert",
            charts: Iterable[str] | None = None) -> Dict[str, Any]:
    return normalize_tabs([{
        "id": make_tab_id(),
        "title": title,
        "fields": list(fields),
        "blocks": list(DEFAULT_BLOCKS.get(persona, DEFAULT_BLOCKS["expert"])),
        "block_sizes": {},
        "charts": list(charts or []),
        "chart_sizes": {},
        "process_views": list(DEFAULT_PROCESS_VIEWS),
        "process_sizes": {},
        "kanban_mode": "due_window",
        "kanban_card_fields": list(DEFAULT_KANBAN_FIELDS),
    }], fields, persona, charts)[0]

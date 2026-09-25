# -*- coding: utf-8 -*-
"""تخته کانبان / اسکرام — برای نمایش گلوگاه‌های فرآیند به‌صورت کارت‌های قابل‌پیمایش.

در تحلیل فرآیند، این تخته معمولاً «مرحلهٔ فعلی هر کیس» را نشان می‌دهد نه
وظایف توسعه؛ ولی ساختار همان کانبان استاندارد است، پس برای اسپرینت تیم
محصول هم قابل استفادهٔ مستقیم است.
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from typing import List, Optional, Sequence, TypedDict

from .. import tokens as T


class KanbanCard(TypedDict, total=False):
    title: str
    tag: str
    owner: str           # نام کوتاه؛ فقط حرف اول در آواتار نشان داده می‌شود
    priority: str         # یکی از "bottleneck" | "critical" | "watch" | "good"
    age_days: int          # چند روز در این ستون مانده — برای شناسایی رکود


class KanbanColumn(TypedDict, total=False):
    title: str
    status: str            # کلید STATUS برای رنگ سرستون
    wip_limit: Optional[int]
    cards: Sequence[KanbanCard]


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def _avatar(name: str, color: str) -> str:
    initial = (name or "؟").strip()[:1]
    return (f'<span class="av" style="background:{color}22;color:{color}">'
            f'{_esc(initial)}</span>')


def _card_html(card: KanbanCard) -> str:
    status = T.status_of(card.get("priority") or "good")
    age = card.get("age_days")
    age_html = ""
    if age is not None:
        stale = age >= 5
        age_html = (f'<span class="age{" stale" if stale else ""}">'
                    f'⏱ {_esc(age)} روز</span>')
    tag_html = f'<span class="tag">{_esc(card["tag"])}</span>' if card.get("tag") else ""
    owner_html = _avatar(card.get("owner", ""), status.ink) if card.get("owner") else ""
    return f"""
<div class="card" style="border-inline-start-color:{status.fill}">
  <div class="card-title">{_esc(card.get('title',''))}</div>
  <div class="card-meta">{tag_html}{age_html}</div>
  <div class="card-foot">{owner_html}<span class="owner-name">{_esc(card.get('owner',''))}</span></div>
</div>"""


def _column_html(col: KanbanColumn) -> str:
    status = T.status_of(col.get("status") or "good")
    cards = list(col.get("cards", []))
    wip = col.get("wip_limit")
    over = wip is not None and len(cards) > wip
    count_txt = f"{len(cards)}" + (f" / {wip}" if wip else "")
    cards_html = "".join(_card_html(c) for c in cards) or (
        '<div class="empty">موردی در این مرحله نیست</div>')
    return f"""
<div class="col">
  <div class="col-head">
    <span class="dot" style="background:{status.fill}"></span>
    <span class="col-title">{_esc(col.get('title',''))}</span>
    <span class="count{' over' if over else ''}">{_esc(count_txt)}</span>
  </div>
  <div class="col-body">{cards_html}</div>
</div>"""


def render_kanban_board(columns: Sequence[KanbanColumn], *, height: int = 460) -> None:
    """تختهٔ کانبان را با ``components.v1.html`` رندر می‌کند (اسکرول افقی روان)."""
    import streamlit.components.v1 as components

    cols_html = "".join(_column_html(c) for c in columns)
    html = f"""
<div class="board" dir="rtl">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{T.FONT_STACK}}}
  .board{{display:flex;gap:12px;overflow-x:auto;padding:4px 2px 10px}}
  .col{{flex:0 0 250px;background:{T.SURFACE_SUNKEN};border:1px solid {T.BORDER};
    border-radius:{T.RADIUS['lg']}px;padding:10px;max-height:{height}px;display:flex;flex-direction:column}}
  .col-head{{display:flex;align-items:center;gap:6px;padding:2px 4px 10px;
    border-bottom:1px solid {T.BORDER};margin-bottom:8px}}
  .dot{{width:9px;height:9px;border-radius:50%}}
  .col-title{{font-size:13px;font-weight:800;color:{T.INK};flex:1}}
  .count{{font-size:11px;color:{T.INK_MUTED};background:{T.SURFACE_RAISED};
    border-radius:999px;padding:1px 8px;border:1px solid {T.BORDER}}}
  .count.over{{color:{T.STATUS['critical'].ink};border-color:{T.STATUS['critical'].fill}}}
  .col-body{{overflow-y:auto;display:flex;flex-direction:column;gap:8px}}
  .card{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};
    border-inline-start:4px solid transparent;border-radius:{T.RADIUS['md']}px;
    padding:10px 12px;box-shadow:{T.SHADOW_CARD};transition:transform .18s, box-shadow .18s}}
  .card:hover{{transform:translateY(-2px);box-shadow:{T.SHADOW_CARD_HOVER}}}
  .card-title{{font-size:12.5px;font-weight:700;color:{T.INK};line-height:1.5}}
  .card-meta{{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap}}
  .tag{{font-size:10.5px;color:{T.AQUA_700};background:{T.AQUA_WASH};
    border-radius:999px;padding:2px 8px}}
  .age{{font-size:10.5px;color:{T.INK_MUTED}}}
  .age.stale{{color:{T.STATUS['watch'].ink};font-weight:700}}
  .card-foot{{display:flex;align-items:center;gap:6px;margin-top:8px}}
  .av{{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;
    justify-content:center;font-size:10px;font-weight:800}}
  .owner-name{{font-size:11px;color:{T.INK_MUTED}}}
  .empty{{font-size:11px;color:{T.INK_MUTED};text-align:center;padding:16px 4px}}
</style>
{cols_html}
</div>"""
    components.html(html, height=height + 24, scrolling=True)

# -*- coding: utf-8 -*-
"""نمودار جریان سیستمی — خط لولهٔ معماری (منبع → پردازش → انبار داده → BI).

برخلاف :mod:`process_flow` که یک گراف چندشاخه با شدت جریان است، این یک
خط لولهٔ خطی/ساده با انشعاب محدود است — برای نمایش معماری سیستم یا مسیر
تأیید یک فرآیند اداری به مدیران غیرفنی.
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from typing import Sequence, TypedDict

from .. import tokens as T


class SystemStage(TypedDict, total=False):
    label: str
    icon: str
    sub: str
    status: str      # کلید STATUS؛ پیش‌فرض "good"


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def render_system_flow(stages: Sequence[SystemStage], *, height: int = 150) -> None:
    """خط لولهٔ سیستمی را افقی و راست‌به‌چپ رندر می‌کند."""
    import streamlit.components.v1 as components

    cards = []
    for i, s in enumerate(stages):
        status = T.status_of(s.get("status") or "good")
        icon = s.get("icon", "◆")
        sub = f'<div class="sub">{_esc(s.get("sub",""))}</div>' if s.get("sub") else ""
        cards.append(f"""
<div class="stage">
  <div class="card" style="border-top-color:{status.fill}">
    <div class="icon">{_esc(icon)}</div>
    <div class="label">{_esc(s.get('label',''))}</div>
    {sub}
  </div>
</div>""")
        if i < len(stages) - 1:
            cards.append('<div class="arrow">←</div>')

    html = f"""
<div class="pipeline" dir="rtl">
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{T.FONT_STACK}}}
  .pipeline{{display:flex;align-items:stretch;gap:4px;overflow-x:auto;padding:6px 2px}}
  .stage{{flex:0 0 auto;display:flex}}
  .card{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};border-top:3px solid;
    border-radius:{T.RADIUS['lg']}px;box-shadow:{T.SHADOW_CARD};padding:14px 18px;
    min-width:132px;text-align:center;transition:transform .2s, box-shadow .2s}}
  .card:hover{{transform:translateY(-3px);box-shadow:{T.SHADOW_CARD_HOVER}}}
  .icon{{font-size:22px;color:{T.AQUA_700}}}
  .label{{font-size:12.5px;font-weight:800;color:{T.INK};margin-top:6px}}
  .sub{{font-size:10.5px;color:{T.INK_MUTED};margin-top:3px}}
  .arrow{{align-self:center;color:{T.BORDER_STRONG};font-size:20px;padding:0 4px}}
</style>
<div style="display:flex;align-items:center">{''.join(cards)}</div>
</div>"""
    components.html(html, height=height, scrolling=True)

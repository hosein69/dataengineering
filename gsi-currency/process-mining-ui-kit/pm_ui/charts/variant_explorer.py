# -*- coding: utf-8 -*-
"""کاوشگر واریانت — بازگرداندهٔ همان قابلیتی که در تب فرآیندِ نسخهٔ قدیمی
(``aibl/stages/s85_conformance.py``) بود ولی روی سامانهٔ طراحی/توکن تازه
پیاده‌سازی نشده بود (یافتهٔ اصلی بررسی UX v2).

هر واریانت یک توالی کامل فعالیت (trace signature) است. کارت واریانت با
``st.markdown`` (HTML بصری، غیرتعاملی) رندر می‌شود و بلافاصله زیرش یک
``st.button`` واقعی Streamlit می‌آید — عمداً دو تکه، نه یک ادعای «کل کارت
کلیک‌پذیر است»: HTML تزریق‌شده با ``unsafe_allow_html`` نمی‌تواند خودش
مقدار را به پایتون برگرداند مگر با یک کامپوننت دوطرفهٔ سفارشی (نمونه‌اش
:mod:`pm_ui.layout.dragdrop`)؛ برای یک فهرست انتخاب ساده، ``st.button``
واقعی و تضمین‌شده بهتر از یک کامپوننت اضافه است.
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from typing import List, Optional, Sequence, Set, Tuple, TypedDict

from .. import tokens as T


def _esc(v: object) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


class VariantSpec(TypedDict, total=False):
    id: str
    label: str                          # مثلاً «مسیر غالب» یا «با بازگشت اصلاح مدارک»
    route: str                           # توالی خوانا، با فلش جدا شده
    share_pct: float
    case_count: int
    mean_cycle_days: float
    conformant: bool                       # False یعنی این واریانت انحراف از انطباق است
    conformance_note: str
    pinned: bool                            # مسیر مرجع/غالب — با نشان ★ جدا نمایش داده می‌شود
    path_edges: List[Tuple[str, str]]         # یال‌های (source, target) این واریانت — برای برجسته‌سازی روی نقشه


#: پیشوند کلید ``st.session_state`` — بین بلوک نقشهٔ جریان و بلوک کاوشگر
#: واریانت مشترک است تا دو بلوک مستقل بتوانند بی‌آن‌که مستقیماً هم را
#: صدا بزنند، روی «واریانت انتخاب‌شدهٔ جاری» هماهنگ بمانند.
STATE_KEY_PREFIX = "_pm_selected_variant__"


def default_variant_id(variants: Sequence[VariantSpec]) -> Optional[str]:
    """شناسهٔ واریانت پیش‌فرض — ``pinned`` (مسیر غالب) یا اولین مورد."""
    pinned = next((v["id"] for v in variants if v.get("pinned")), None)
    return pinned or (variants[0]["id"] if variants else None)


def selected_path_edges(variants: Sequence[VariantSpec], variant_id: Optional[str]) -> Set[Tuple[str, str]]:
    """یال‌های واریانت انتخاب‌شده — برای دادن به ``highlight_edges`` نقشهٔ جریان.

    ``variant_id`` خالی/نامعتبر یعنی «هنوز چیزی انتخاب نشده»، نه «همه چیز
    را کم‌رنگ کن»؛ فراخوان باید در این حالت ``None`` را به نقشه بدهد، نه
    خروجی این تابع را — همان قاعده در :func:`pm_ui.blocks._process_flow`
    رعایت شده.
    """
    for v in variants:
        if v.get("id") == variant_id:
            return set(v.get("path_edges", []))
    return set()


def _card_html(v: VariantSpec, *, rank: int, selected: bool) -> str:
    pinned = bool(v.get("pinned"))
    conformant = v.get("conformant", True)
    border = T.BRAND_GOLD if pinned else (T.BRAND_TEAL if selected else T.BORDER)
    bg = T.GOLD_WASH if pinned else (T.TEAL_WASH if selected else T.SURFACE_RAISED)
    badge = (f'<span style="background:{T.STATUS["good"].wash};color:{T.STATUS["good"].ink};'
             f'border-radius:999px;padding:2px 9px;font-size:10px;font-weight:800">منطبق</span>'
             if conformant else
             f'<span style="background:{T.STATUS["critical"].wash};color:{T.STATUS["critical"].ink};'
             f'border-radius:999px;padding:2px 9px;font-size:10px;font-weight:800">انحراف</span>')
    rank_html = "★" if pinned else str(rank)
    rank_bg = T.BRAND_GOLD if pinned else T.BRAND_NAVY
    rank_color = T.GOLD_INK if pinned else "#fff"
    note = v.get("conformance_note", "")
    note_html = f'<div style="font-size:10.5px;color:{T.INK_MUTED};margin-top:4px">{_esc(note)}</div>' if note else ""
    share = float(v.get("share_pct", 0))
    return f"""
<div style="border:1.5px solid {border};background:{bg};border-radius:{T.RADIUS['md']}px;
            padding:10px 12px 8px;margin-top:8px 0 0" dir="rtl">
  <div style="display:flex;align-items:center;gap:8px">
    <span style="width:22px;height:22px;border-radius:7px;background:{rank_bg};color:{rank_color};
                 font-weight:800;font-size:11px;display:inline-flex;align-items:center;justify-content:center;
                 flex:none">{rank_html}</span>
    <strong style="font-size:12px;color:{T.INK};flex:1">{_esc(v.get('label',''))}</strong>
    <span style="font-weight:800;font-size:14px;color:{T.INK};font-variant-numeric:tabular-nums">
      {_esc(f'{share:.0f}٪')}</span>
  </div>
  <div style="font-size:10.5px;color:{T.INK_MUTED};margin-top:5px;line-height:1.7">{_esc(v.get('route',''))}</div>
  <div style="height:6px;background:{T.SURFACE_SUNKEN};border-radius:999px;overflow:hidden;margin-top:7px">
    <div style="height:100%;width:{max(0,min(100,share)):.0f}%;
                background:linear-gradient(90deg,{T.BRAND_TEAL},{T.AQUA_500})"></div>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:7px">
    {badge}
    <span style="font-size:10.5px;color:{T.INK_MUTED}">میانگین چرخه: {_esc(f"{v.get('mean_cycle_days', 0):.1f} روز")}</span>
  </div>
  {note_html}
</div>"""


def render_variant_explorer(variants: Sequence[VariantSpec], *, key: str = "variant_explorer") -> Optional[str]:
    """فهرست واریانت‌ها را رندر می‌کند و شناسهٔ واریانتِ انتخاب‌شدهٔ جاری را برمی‌گرداند.

    انتخاب در ``st.session_state`` نگه داشته می‌شود (پیش‌فرض: واریانت
    ``pinned``، یعنی مسیر غالب). فراخوان (:mod:`pm_ui.blocks`) این مقدار را
    به ``mark_edges``ی می‌دهد که نقشهٔ جریان برای برجسته‌سازی مسیر می‌گیرد.
    """
    import streamlit as st

    state_key = f"{STATE_KEY_PREFIX}{key}"
    if state_key not in st.session_state or st.session_state[state_key] not in {v.get("id") for v in variants}:
        st.session_state[state_key] = default_variant_id(variants)

    for rank, v in enumerate(variants, start=1):
        selected = st.session_state[state_key] == v.get("id")
        st.markdown(_card_html(v, rank=rank, selected=selected), unsafe_allow_html=True)
        if st.button(f"نمایش این مسیر روی نقشه — {v.get('label','')}", key=f"{key}_pick_{v.get('id')}",
                    use_container_width=True, type="primary" if selected else "secondary"):
            st.session_state[state_key] = v.get("id")
            st.rerun()

    return st.session_state[state_key]

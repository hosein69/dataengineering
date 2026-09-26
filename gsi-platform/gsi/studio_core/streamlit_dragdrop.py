# -*- coding: utf-8 -*-
"""Offline Streamlit drag/drop list adapted from the supplied Process Explorer kit.

No npm/pip dependency is required.  This is presentation state only; it returns
an ordered list of stable ids and never mutates report data.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, TypedDict

try:
    import streamlit.components.v1 as components
except Exception:  # pragma: no cover - lets non-Streamlit audits import safely
    components = None

_FRONTEND_DIR = Path(__file__).parent / "dragdrop_frontend"
_component = (components.declare_component("gsi_report_dragdrop", path=str(_FRONTEND_DIR))
              if components is not None else None)


class DragItem(TypedDict, total=False):
    id: str
    label: str
    badge: str


def draggable_list(items: Sequence[DragItem], *, key: str) -> Optional[List[str]]:
    """Return the reordered ids after an actual drop; otherwise ``None``."""
    if _component is None:
        return None
    theme = {
        "ink": "#0b1f33", "inkMuted": "#5a6b79", "border": "#dbe3e7",
        "borderStrong": "#7d919e", "surfaceRaised": "#ffffff",
        "surfaceSunken": "#eef2f4", "teal": "#0a7c86", "tealWash": "#e7f1f2",
        "radius": 10,
        "font": ("'IRANSansWeb','IRANSansX','IRANSans','YekanBakh','Yekan Bakh',"
                 "'Vazirmatn',Tahoma,'Segoe UI',Arial,sans-serif"),
    }
    value = _component(items=list(items), theme=theme, key=key, default=None)
    if not value or not isinstance(value, list):
        return None
    return [str(v) for v in value]

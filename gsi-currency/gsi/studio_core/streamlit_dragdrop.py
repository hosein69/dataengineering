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
    # Colours/font come from the single design-token source (gsi.design.tokens);
    # hard-coded hex values here drifted from the rest of the product before.
    from ..design import tokens as T
    theme = {
        "ink": T.TEXT, "inkMuted": T.TEXT_MUTED, "border": T.BORDER,
        "borderStrong": T.BORDER_STRONG, "surfaceRaised": T.SURFACE_RAISED,
        "surfaceSunken": T.SURFACE_SUNKEN, "teal": T.BRAND_TEAL, "tealWash": T.TEAL_WASH,
        "radius": 10,
        "font": T.FONT_STACK,
    }
    value = _component(items=list(items), theme=theme, key=key, default=None)
    if not value or not isinstance(value, list):
        return None
    return [str(v) for v in value]

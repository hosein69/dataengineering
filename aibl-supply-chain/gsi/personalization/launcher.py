# -*- coding: utf-8 -*-
"""Local live-view launcher.

``gsi://personal`` opens this helper on Windows. It reads encrypted files from
GSI_PROFILE_ROOT directly, renders a fresh local HTML cache and opens it with
the default browser. No HTTP server or IP data transport is involved.
"""
from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from .personal_html import build_personal_html
from .identity import resolve_employee_code


def local_cache_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "GSI" / "cache"
    return Path(os.environ.get("GSI_HOME", os.path.join(os.path.expanduser("~"), ".gsi"))) / "cache"


def render_live(employee_code: Optional[str] = None, *, output: Optional[str | Path] = None) -> Path:
    emp = resolve_employee_code(employee_code)
    out = Path(output) if output else local_cache_dir() / f"GSI_{emp}_Live.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(build_personal_html(emp, title="GSI · وضعیت زنده من"), encoding="utf-8")
    os.replace(tmp, out)
    return out


def render_and_open(employee_code: Optional[str] = None) -> Path:
    out = render_live(employee_code)
    webbrowser.open(out.resolve().as_uri(), new=2)
    return out

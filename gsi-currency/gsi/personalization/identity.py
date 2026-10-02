# -*- coding: utf-8 -*-
"""Local identity resolution for the personal workspace.

Identity is deliberately resolved without IP addresses, HTTP requests or remote
identity APIs. Production can set ``GSI_EMP_CODE`` per workstation/user session,
or pass an explicit employee code from the already-loaded HR mapping.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..core.text import clean_employee_code

EMP_ENV = "GSI_EMP_CODE"
IDENTITY_FILE_ENV = "GSI_IDENTITY_FILE"


class IdentityError(RuntimeError):
    pass


def _from_identity_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.is_file():
        raise IdentityError(f"فایل هویت GSI پیدا نشد: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as ex:
        raise IdentityError(f"فایل هویت GSI قابل خواندن نیست: {ex}") from ex
    if not isinstance(data, dict):
        raise IdentityError("ساختار فایل هویت معتبر نیست.")
    return clean_employee_code(data.get("employee_code", ""))


def resolve_employee_code(explicit: Optional[str] = None, *, required: bool = True) -> str:
    """Resolve the current employee code without any IP/network lookup.

    Priority: explicit argument → ``GSI_EMP_CODE`` → optional local identity file.
    The identity file is expected to be local/configuration state, not the shared
    profile root. The shared root is data storage, not an authentication source.
    """
    emp = clean_employee_code(explicit or "")
    if explicit is not None and not emp:
        raise IdentityError("کد پرسنلی صریح معتبر نیست.")
    if not emp:
        emp = clean_employee_code(os.environ.get(EMP_ENV, ""))
    if not emp:
        identity_file = os.environ.get(IDENTITY_FILE_ENV, "").strip()
        if not identity_file:
            # An explicit GSI_HOME is the operator-selected local configuration
            # root on every OS. Only fall back to LOCALAPPDATA on Windows when
            # GSI_HOME was not supplied.
            gsi_home = os.environ.get("GSI_HOME", "").strip()
            if gsi_home:
                candidate = Path(gsi_home) / "identity.json"
            elif os.name == "nt":
                base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
                candidate = Path(base) / "GSI" / "identity.json"
            else:
                candidate = Path(os.path.join(os.path.expanduser("~"), ".gsi")) / "identity.json"
            identity_file = str(candidate) if candidate.is_file() else ""
        if identity_file:
            emp = _from_identity_file(identity_file)
    if not emp and required:
        raise IdentityError(
            "کد پرسنلی کاربر مشخص نیست. GSI_EMP_CODE را برای این Session/سیستم تنظیم کنید "
            "یا employee_code را صریحاً به برنامه بدهید."
        )
    return emp

# -*- coding: utf-8 -*-
"""High-level personal workspace facade shared by Streamlit and email renderers."""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

from .. import audience as _audience
from .identity import resolve_employee_code
from .store import EncryptedUserStore

_DEFAULTS = {
    "table_rows": 40,
    "audience": "expert",
    "email_density": "compact",
    "calendar": "jalali",
    "show_critical_only": False,
    "show_causes": True,
    "compact_mode": False,
    "email_charts": ["criticality", "low_resistance", "stock_vs_total"],
    "dashboard_widgets": ["my_actions", "deadlines", "allocation_queue", "inventory_position"],
    "email_widgets": ["my_actions", "deadlines", "critical_cases", "inventory_position"],
}


def _valid(k, v):
    enums = {"audience": {"expert", "manager", "executive", "analyst"}, "calendar": {"jalali", "gregorian"}, "email_density": {"compact", "comfortable", "detailed"}}
    if k in enums:
        return isinstance(v, str) and v in enums[k]
    if k == "table_rows":
        # upper bound comes from the audience profile at read time, so the stored
        # preference only has to be sane; the analyst profile allows 1000.
        return type(v) is int and 1 <= v <= 2000
    if k not in _DEFAULTS:
        return False
    if isinstance(_DEFAULTS[k], bool):
        return type(v) is bool
    return isinstance(v, list) and len(v) <= 40 and all(isinstance(x, str) and len(x) < 100 for x in v)


@dataclass
class PersonalWorkspace:
    employee_code: str
    store: EncryptedUserStore

    @classmethod
    def from_env(cls, employee_code: Optional[str] = None) -> "PersonalWorkspace":
        emp = resolve_employee_code(employee_code)
        return cls(emp, EncryptedUserStore.from_env(emp))

    def preferences(self) -> Dict[str, Any]:
        """Preferences with the audience profile resolved.

        ``gsi.audience`` is the single definition of how much each audience sees.
        A saved ``table_rows`` may only narrow that profile, never widen it, so
        the renderer and the profile can never drift apart.
        """
        saved = self.store.namespace("preferences")
        prefs = {**deepcopy(_DEFAULTS), **{k: v for k, v in saved.items() if _valid(k, v)}}
        profile = _audience.get(str(prefs.get("audience") or ""))
        prefs["audience"] = profile.key
        prefs["max_findings"] = int(profile.max_findings)
        prefs["audience_sections"] = list(profile.sections)
        chosen = saved.get("table_rows")
        prefs["table_rows"] = (min(int(chosen), int(profile.table_rows))
                               if _valid("table_rows", chosen) else int(profile.table_rows))
        return prefs

    def save_preferences(self, values: Mapping[str, Any]) -> Dict[str, Any]:
        allowed = set(_DEFAULTS)
        clean = {k: v for k, v in values.items() if k in allowed}
        if any(not _valid(k, v) for k, v in clean.items()):
            raise ValueError("تنظیمات انتخاب‌شده معتبر نیست.")
        self.store.merge("preferences", clean, audit_event="preferences_saved")
        return self.preferences()

    def ui_state(self) -> Dict[str, Any]:
        return self.store.namespace("ui_state")

    def save_ui_state(self, values: Mapping[str, Any]) -> None:
        self.store.merge("ui_state", values, audit_event="ui_state_saved")

    def current_data(self) -> Dict[str, Any]:
        return self.store.current_snapshot()

    def publish_current_data(self, payload: Mapping[str, Any], *, source_run_id: str = "") -> None:
        self.store.replace_snapshot(payload, source_run_id=source_run_id)

    def context(self) -> Dict[str, Any]:
        current, meta = self.store.snapshot_context()
        return {
            "employee_code": self.employee_code,
            "preferences": self.preferences(),
            "ui_state": self.ui_state(),
            "current": current,
            "snapshot_meta": meta,
        }

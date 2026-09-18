# -*- coding: utf-8 -*-
"""High-level personal workspace facade shared by Streamlit and email renderers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from .. import audience as _audience
from .identity import resolve_employee_code
from .store import EncryptedUserStore

_DEFAULTS = {
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


@dataclass
class PersonalWorkspace:
    employee_code: str
    store: EncryptedUserStore

    @classmethod
    def from_env(cls, employee_code: Optional[str] = None) -> "PersonalWorkspace":
        emp = resolve_employee_code(employee_code)
        return cls(emp, EncryptedUserStore.from_env(emp))

    def preferences(self) -> Dict[str, Any]:
        """Preferences, with the caps of the selected audience profile resolved.

        ``table_rows`` and ``max_findings`` are derived from ``gsi.audience`` rather
        than stored, so the renderers cannot drift from the profile definitions.
        """
        saved = self.store.namespace("preferences")
        prefs = {**_DEFAULTS, **saved}
        profile = _audience.get(str(prefs.get("audience") or ""))
        prefs["audience"] = profile.key
        prefs["table_rows"] = int(profile.table_rows)
        prefs["max_findings"] = int(profile.max_findings)
        prefs["audience_sections"] = list(profile.sections)
        return prefs

    def save_preferences(self, values: Mapping[str, Any]) -> Dict[str, Any]:
        allowed = set(_DEFAULTS)
        clean = {k: v for k, v in values.items() if k in allowed}
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
        return {
            "employee_code": self.employee_code,
            "preferences": self.preferences(),
            "ui_state": self.ui_state(),
            "current": self.current_data(),
            "snapshot_meta": self.store.metadata(kind="snapshot") if self.store.paths.snapshot.exists() else {},
        }

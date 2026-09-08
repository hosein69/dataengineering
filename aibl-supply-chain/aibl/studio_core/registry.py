# -*- coding: utf-8 -*-
"""Registry for visual modules used by AIBL Studio."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

@dataclass(frozen=True)
class ModuleSpec:
    key: str
    title: str
    description: str
    icon: str
    category: str
    default: bool = True
    exportable: bool = True

MODULES: Dict[str, ModuleSpec] = {
    "kpi": ModuleSpec("kpi", "Executive KPI", "Criticality, exposure and operating KPIs", "◈", "Executive"),
    "criticality": ModuleSpec("criticality", "Criticality Mix", "Critical / warning / watch / safe / inactive distribution", "🚦", "Risk"),
    "resistance": ModuleSpec("resistance", "Lowest Resistance", "Materials closest to a production stop", "⏱", "Risk"),
    "process": ModuleSpec("process", "Process Bottlenecks", "Event-log bottlenecks and variants", "⛓", "Process"),
    "org": ModuleSpec("org", "Organization Load", "Workload and risk by management", "🏢", "Organization"),
    "expert": ModuleSpec("expert", "Expert Workload", "Cases, critical cases and resistance by expert", "👤", "Organization"),
    "commitment": ModuleSpec("commitment", "Commitment Exposure", "Outstanding commitments and overdue cases", "💰", "Finance"),
    "case_alerts": ModuleSpec("case_alerts", "Critical Case Causes", "Why a BL/order became critical and which material caused it", "🔴", "Risk"),
    "table": ModuleSpec("table", "Live Case Table", "Searchable live filtered records", "▦", "Detail"),
    "email": ModuleSpec("email", "Executive Email", "Build and send the existing Outlook executive email pack", "✉", "Delivery"),
}

DEFAULT_ORDER: List[str] = [
    "kpi", "criticality", "case_alerts", "resistance", "process", "org", "commitment", "table", "email"
]

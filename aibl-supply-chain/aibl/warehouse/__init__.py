# -*- coding: utf-8 -*-
"""SQLite warehouse for AIBL.

Excel/HTML are presentation artifacts.  The durable analytical state lives here:
run snapshots, immutable events, per-run transitions, KPI history and audit logs.
"""
from .sqlite_store import Warehouse, WarehouseSnapshot, warehouse_from_settings

__all__ = ["Warehouse", "WarehouseSnapshot", "warehouse_from_settings"]

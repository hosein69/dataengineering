# -*- coding: utf-8 -*-
"""Lifecycle bridge between Pipeline and the durable Warehouse.

Keeps orchestration concerns out of ``pipeline.py`` while ensuring that every
runtime log, successful snapshot and failed execution shares one ``run_id``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

import pandas as pd

from ..config.settings import SETTINGS
from ..dataio.logging_setup import log, set_run_id
from ..version import PACKAGE_VERSION
from .sqlite_store import Warehouse, warehouse_from_settings


@dataclass
class WarehouseRun:
    ref_date: date | str
    package_version: str = PACKAGE_VERSION
    warehouse: Optional[Warehouse] = None
    run_id: str = ""
    required: bool = False

    def __enter__(self) -> "WarehouseRun":
        self.required = os.environ.get("AIBL_WAREHOUSE_REQUIRED", "0").strip().lower() in ("1", "true", "yes", "on")
        if not SETTINGS.WAREHOUSE_ENABLED:
            return self
        try:
            self.warehouse = warehouse_from_settings()
            self.run_id = self.warehouse.begin_run(self.ref_date, package_version=self.package_version)
            set_run_id(self.run_id)
        except Exception as ex:
            log.error("❌ SQLite Warehouse شروع نشد: %s", ex)
            self.warehouse = None
            self.run_id = ""
            if self.required:
                raise
        return self

    def persist(self, result: Any, sources: Optional[Dict[str, Dict[str, pd.DataFrame]]] = None) -> str:
        if self.warehouse is None:
            return ""
        try:
            rid = self.warehouse.persist_pipeline(
                result, self.ref_date, package_version=self.package_version,
                sources=sources or {}, run_id=self.run_id or None)
            self.run_id = rid
            result.warehouse_run_id = rid
            result.extras["warehouse_run_id"] = rid
            result.extras["warehouse_path"] = str(self.warehouse.path)
            return rid
        except Exception as ex:
            log.error("❌ SQLite Warehouse ذخیره نشد: %s", ex)
            try:
                if self.run_id:
                    self.warehouse.fail_run(self.run_id, self.ref_date, f"warehouse persist: {ex}", package_version=self.package_version)
            except Exception:
                pass
            if self.required:
                raise
            return ""

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc is not None and self.warehouse is not None and self.run_id:
                self.warehouse.fail_run(self.run_id, self.ref_date, str(exc), package_version=self.package_version)
        except Exception:
            pass
        finally:
            set_run_id(None)
        return False


def warehouse_run(ref_date: date | str, package_version: str = PACKAGE_VERSION) -> WarehouseRun:
    return WarehouseRun(ref_date=ref_date, package_version=package_version)

# -*- coding: utf-8 -*-
"""مرحله‌های خط لوله — هر فایل یک مرحله مستقل.

افزودن قابلیت = یک فایل جدید اینجا.  حذف = حذف همان فایل.
هیچ فایل دیگری (pipeline.py، dashboard.py) تغییر نمی‌کند.
"""
from __future__ import annotations

from .base import (ColumnSpec, PipelineContext, Stage, StageContractError,
                   collect_columns, describe, discover, log_plan, register,
                   validate_graph)

__all__ = ["Stage", "PipelineContext", "ColumnSpec", "StageContractError",
           "register", "discover", "validate_graph", "collect_columns",
           "describe", "log_plan"]

# -*- coding: utf-8 -*-
"""مرحله ۳۰ — تطبیق سازمانی HR."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ..adapters.base import KEY_EMP
from ..core.text import is_empty_val
from ..dataio.logging_setup import log
from ..resolve.org_mapper import DynamicOrgMapper
from .base import (ColumnSpec, GROUP_MAIN, PipelineContext, Stage, register)


@register
class OrgStage(Stage):
    name = "org"
    title = "اتصال کارشناس به سلسله‌مراتب سازمانی"
    order = 30
    requires = ["CANONICAL_EXPERT", KEY_EMP]
    provides = ["ORG_VICE", "ORG_DEPT", "ORG_MANAGER", "ORG_HEAD",
                "ORG_MATCH", "ORG_CHAIN"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        mapper = DynamicOrgMapper(ctx.sheet("hr"))
        rows = [mapper.map(e, c) for e, c in zip(df["CANONICAL_EXPERT"], df[KEY_EMP])]
        for col, key in (("ORG_VICE", "vice"), ("ORG_DEPT", "dept"),
                         ("ORG_MANAGER", "manager"), ("ORG_HEAD", "head"),
                         ("ORG_MATCH", "match_type")):
            df[col] = [p[key] for p in rows]
        df["CANONICAL_EXPERT"] = [p["expert"] if is_empty_val(e) else e
                                  for e, p in zip(df["CANONICAL_EXPERT"], rows)]
        df["ORG_CHAIN"] = [DynamicOrgMapper.format_chain(p) for p in rows]
        matched = sum(1 for p in rows if p["match_type"] != "پیش‌فرض")
        log.info(f"🏢 تطبیق سازمانی: {matched} از {len(rows)} ردیف به HR وصل شد.")
        ctx.extras["org_matched"] = matched
        return df

    def columns(self) -> List[ColumnSpec]:
        return [ColumnSpec("ORG_CHAIN", "مسئولیت سازمانی", 45, GROUP_MAIN,
                           wrap=True, order=23)]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        n = int((df.get("ORG_MATCH", pd.Series(dtype=str)) != "پیش‌فرض").sum())
        return {"ردیف‌های متصل به HR": (n, "تطبیق کد پرسنلی / نام / فازی")}

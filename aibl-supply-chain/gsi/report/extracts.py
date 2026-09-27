# -*- coding: utf-8 -*-
"""فایل اکسل مجزا برای هر کارشناس + گزارش ممیزی تعارضات (§۱۰).

نسخه ۲۰.۱ هیچ‌کدام را نداشت (پوشه expert_extracts اصلاً ساخته نمی‌شد).
گروه‌بندی بر اساس **کد پرسنلی** انجام می‌شود، نه نام — چون نام‌ها تکراری و
پرنویز هستند.
"""
from __future__ import annotations

import os
import re
from typing import List

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from ..dataio.logging_setup import log
from .palette import LuxuryPalette as P, NUM_FORMAT_CURRENCY

_SAFE = re.compile(r"[^\w\u0600-\u06FF\-]+")


def _safe_name(s: str) -> str:
    return _SAFE.sub("_", str(s)).strip("_")[:60] or "unknown"


def write_expert_extracts(df: pd.DataFrame, out_dir: str,
                          columns: List[str] | None = None) -> List[str]:
    if df.empty:
        log.warning("⚠️ داده‌ای برای استخراج کارشناسان وجود ندارد.")
        return []
    os.makedirs(out_dir, exist_ok=True)
    cols = columns or [c for c in df.columns if not c.startswith(("RAW_", "MOGH_RAW_"))]
    paths: List[str] = []

    key = "KEY_EMP" if "KEY_EMP" in df.columns else "CANONICAL_EXPERT"
    for emp, g in df.groupby(key, dropna=False):
        expert = str(g["CANONICAL_EXPERT"].iloc[0]) if "CANONICAL_EXPERT" in g else ""
        fname = f"{_safe_name(emp) or 'no_code'}__{_safe_name(expert)}.xlsx"
        path = os.path.join(out_dir, fname)

        wb = Workbook()
        ws = wb.active
        ws.title = "پرونده کارشناس"
        ws.sheet_view.rightToLeft = True

        ws.cell(row=1, column=1, value=f"پرونده کارشناس: {expert} (کد {emp})").font = P.font_title(13)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=min(len(cols), 8))

        for i, h in enumerate(cols, start=1):
            c = ws.cell(row=3, column=i, value=h)
            c.font = P.font_header(1)
            c.fill = P.fill_header()
            c.alignment = P.align("center", wrap=True)
            ws.column_dimensions[get_column_letter(i)].width = 24
        ws.freeze_panes = "A4"
        ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}3"

        for r, (_, row) in enumerate(g.iterrows(), start=4):
            crit = "بحرانی" in str(row.get("وضعیت هوشمند", ""))
            for i, col in enumerate(cols, start=1):
                v = row.get(col, "")
                cell = ws.cell(row=r, column=i, value=v if isinstance(v, (int, float, str)) else str(v))
                cell.font = P.font_body()
                cell.border = P.thin_border()
                cell.fill = P.fill(P.CRITICAL_FILL if crit else P.GREEN_L4)
                if col in ("مانده تعهد", "جریمه برآوردی"):
                    cell.number_format = NUM_FORMAT_CURRENCY
        wb.save(path)
        paths.append(path)

    log.info(f"📁 {len(paths)} فایل اختصاصی کارشناس در {out_dir} ساخته شد.")
    return paths


def write_audit_report(audit_df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "ممیزی تعارضات"
    ws.sheet_view.rightToLeft = True

    if audit_df.empty:
        ws["A1"] = "هیچ تعارضی میان سورس‌ها شناسایی نشد."
        ws["A1"].font = P.font_title(13)
        wb.save(path)
        return path

    headers = list(audit_df.columns)
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = P.font_header(1)
        c.fill = P.fill_header()
        c.alignment = P.align("center", wrap=True)
        ws.column_dimensions[get_column_letter(i)].width = 30 if i > 2 else 20
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

    for r, (_, row) in enumerate(audit_df.iterrows(), start=2):
        critical = str(row.get("نوع اهمیت")) == "CRITICAL"
        for i, h in enumerate(headers, start=1):
            cell = ws.cell(row=r, column=i, value=str(row[h]))
            cell.font = P.font_body()
            cell.border = P.thin_border()
            cell.alignment = P.align("right", wrap=True)
            cell.fill = P.fill(P.CRITICAL_FILL if critical else P.GREEN_L4)
    wb.save(path)
    log.info(f"📋 گزارش ممیزی تعارضات ذخیره شد: {path} ({len(audit_df)} مورد)")
    return path

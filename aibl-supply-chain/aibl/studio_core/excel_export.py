# -*- coding: utf-8 -*-
"""Custom Excel export for AIBL Studio."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from ..report import narrative as _NR

FONT = "IRANSans Light"

#: نام پیش‌فرض خروجی سفارشی Studio — عمداً با گزارش رسمی روزانه فرق دارد.
#: تست رگرسیون همین ثابت را با نام گزارش رسمی می‌سنجد (نه با grep روی UI).
DEFAULT_CUSTOM_NAME = "AIBL Studio"


class OfficialReportOverwrite(Exception):
    """تلاش برای بازنویسی گزارش رسمی روزانه با یک خروجی فیلترشده.

    خروجی Studio همیشه *زیرمجموعه* داده است (فیلتر کاربر + چند شیت). گزارش
    رسمی خط لوله ۱۷ شیت کامل دارد و ایمیل مدیریتی به همان فایل لینک می‌دهد.
    اگر نام پیش‌فرض یکی شود، یک کلیک روی «ساخت Excel سفارشی» گزارش رسمی را
    بی‌صدا نابود می‌کند. این استثنا جلوی آن را می‌گیرد.
    """
COLORS = {
    "critical": "C0392B", "warning": "F39C12", "watch": "F1C40F",
    "good": "27AE60", "inactive": "95A5A6", "header": "406057",
    "header_fill": "406057", "white": "FFFFFF", "grid": "D8E5E1"
}


def _status_color(value: str) -> str:
    s = str(value).lower()
    if "توقف" in s or "بحرانی" in s or "critical" in s: return COLORS["critical"]
    if "در حال" in s or "warning" in s or "becoming" in s: return COLORS["warning"]
    if "نظر" in s or "watch" in s: return COLORS["watch"]
    if "ایمن" in s or "safe" in s: return COLORS["good"]
    return COLORS["inactive"] if "مصرف" in s or "unknown" in s else COLORS["good"]


def _style_sheet(ws):
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    thin = Side(style="thin", color=COLORS["grid"])
    for cell in ws[1]:
        cell.font = Font(name=FONT, size=10, bold=True, color=COLORS["white"])
        cell.fill = PatternFill("solid", fgColor=COLORS["header_fill"])
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=thin)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name=FONT, size=9, color="111917")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        max_len = max([len(str(c.value or "")) for c in col[:80]] + [8])
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 32)
    ws.row_dimensions[1].height = 30


def _official_report_paths(ref_date: str) -> set:
    """مسیرهای گزارش رسمی روزانه که هرگز نباید با خروجی Studio بازنویسی شوند."""
    from ..config.settings import SETTINGS
    out = set()
    try:
        from datetime import date as _date
        day = _date.fromisoformat(str(ref_date)[:10])
    except Exception:
        day = None
    for p in ([SETTINGS.daily_report_path(day)] if day else []) + [SETTINGS.daily_report_path()]:
        out.add(os.path.normcase(os.path.abspath(p)))
    return out


def build_custom_excel(df: pd.DataFrame, output_path: str | Path, modules: Iterable[str], ref_date: str, max_rows: int = 10000, selected_fields=None, allow_official_overwrite: bool = False, field_labels: Optional[dict] = None, process_tables: Optional[dict] = None) -> str:
    path = Path(output_path)
    if not allow_official_overwrite and os.path.normcase(os.path.abspath(path)) in _official_report_paths(ref_date):
        raise OfficialReportOverwrite(
            f"نام انتخابی دقیقاً همان گزارش رسمی روزانه است:\n    {path}\n"
            f"این فایل ۱۷ شیت کامل خط لوله را دارد و ایمیل مدیریتی به آن لینک می‌دهد؛ "
            f"خروجی Studio فیلترشده است و جایگزین آن نمی‌شود.\n"
            f"یک نام دیگر بگذارید (مثلاً «AIBL Studio»).")
    path.parent.mkdir(parents=True, exist_ok=True)
    modules = list(modules)
    selected_fields = [c for c in list(selected_fields or []) if c in df.columns]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # ── روایت، اولین شیت ─────────────────────────────────────────
        # کسی که فایل را باز می‌کند باید در همان ثانیهٔ اول بداند دربارهٔ
        # چیست. بدون این، هر خواننده داستان خودش را می‌سازد.
        _crit = 0
        if "کد طبقه بحرانی" in df.columns:
            _crit = int(df["کد طبقه بحرانی"].astype(str)
                        .isin(["STOCKOUT", "CRITICAL"]).sum())
        _blind = 0
        for _c in ("PART_OWNER_SOURCE_GAP", "PART_OWNER_DATA_GAP"):
            if _c in df.columns:
                _blind = int(df[_c].astype(str).str.strip().ne("").sum())
                break
        _med = None
        if "مقاومت (روز)" in df.columns:
            _m = pd.to_numeric(df["مقاومت (روز)"], errors="coerce").median()
            _med = None if pd.isna(_m) else float(_m)
        _facts = _NR.Facts(total=int(len(df)), subject="پرونده",
                           ref_date=str(ref_date), critical=_crit,
                           blind=_blind, median=_med)
        pd.DataFrame().to_excel(writer, sheet_name="روایت")
        _NR.excel_cover(writer.book["روایت"], _facts,
                        title="IKCO · Global Sourcing — روایتِ این گزارش",
                        chapters_=_NR.chapters(), numbered=True,
                        coda_text=_NR.CODA, lead=_NR.LEAD_OPENING)

        # Always provide a compact executive sheet.
        k = []
        if "کد طبقه بحرانی" in df.columns:
            for code, label in [("STOCKOUT", "Stop Line"), ("CRITICAL", "Critical"), ("BECOMING_CRITICAL", "Becoming Critical"), ("WATCH", "Watch"), ("SAFE", "Safe")]:
                k.append((label, int((df["کد طبقه بحرانی"] == code).sum())))
        if "BL_CRITICAL" in df.columns and "CANONICAL_BL" in df.columns:
            k.append(("Critical BLs", int(df.loc[df["BL_CRITICAL"].fillna(False).astype(bool), "CANONICAL_BL"].replace("", pd.NA).nunique())))
        if "ORDER_CRITICAL" in df.columns and "CANONICAL_ORDER" in df.columns:
            k.append(("Critical Orders", int(df.loc[df["ORDER_CRITICAL"].fillna(False).astype(bool), "CANONICAL_ORDER"].replace("", pd.NA).nunique())))
        pd.DataFrame(k, columns=["KPI", "Value"]).to_excel(writer, sheet_name="Executive", index=False)
        if "criticality" in modules and "بحرانی (کوتاه)" in df.columns:
            cols = [c for c in ["KEY_MATERIAL", "بحرانی (کوتاه)", "مقاومت (روز)", "BL_CRITICAL", "BL_CRITICAL_MATERIALS", "BL_CRITICAL_REASON"] if c in df.columns]
            df[cols].head(max_rows).to_excel(writer, sheet_name="Criticality", index=False)
        if "case_alerts" in modules:
            cols = [c for c in ["CANONICAL_BL", "CANONICAL_ORDER", "BL_CRITICAL", "ORDER_CRITICAL", "BL_CRITICAL_MATERIALS", "ORDER_CRITICAL_MATERIALS", "BL_CRITICAL_REASON", "ORDER_CRITICAL_REASON"] if c in df.columns]
            df[cols].drop_duplicates().head(max_rows).to_excel(writer, sheet_name="Case Causes", index=False)
        if "resistance" in modules and "مقاومت (روز)" in df.columns:
            cols = [c for c in ["KEY_MATERIAL", "مقاومت (روز)", "بحرانی (کوتاه)", "نیاز روزانه", "موجودی کل قابل احتساب"] if c in df.columns]
            x = df[cols].copy(); x["مقاومت (روز)"] = pd.to_numeric(x["مقاومت (روز)"], errors="coerce")
            x = x.sort_values("مقاومت (روز)").head(max_rows)
            x.to_excel(writer, sheet_name="Lowest Resistance", index=False)
        if "commitment" in modules:
            cols = [c for c in ["CANONICAL_ORDER", "مانده تعهد", "روزهای تأخیر", "جریمه برآوردی", "طبقه ریسک"] if c in df.columns]
            df[cols].head(max_rows).to_excel(writer, sheet_name="Commitment", index=False)
        if "org" in modules and "ORG_DEPT" in df.columns:
            x = df.groupby("ORG_DEPT", dropna=False).size().reset_index(name="Cases").sort_values("Cases", ascending=False)
            x.to_excel(writer, sheet_name="Organization", index=False)
        if "expert" in modules and "CANONICAL_EXPERT" in df.columns:
            x = df.groupby("CANONICAL_EXPERT", dropna=False).agg(Cases=("CANONICAL_EXPERT", "size"))
            if "بحرانی (کوتاه)" in df.columns:
                crit = df["بحرانی (کوتاه)"].isin(["بحرانی", "توقف خط"]).groupby(df["CANONICAL_EXPERT"]).sum()
                x["Critical Cases"] = crit
            if "مقاومت (روز)" in df.columns:
                resistance = pd.to_numeric(df["مقاومت (روز)"], errors="coerce").groupby(df["CANONICAL_EXPERT"]).min()
                x["Min Resistance"] = resistance
            x.reset_index().sort_values("Cases", ascending=False).to_excel(writer, sheet_name="Expert Workload", index=False)
        if "process" in modules:
            # جدول‌های فرآیندکاوی که خط لوله می‌سازد — قبلاً فقط یک یادداشت بود.
            wrote_any = False
            for key, sheet in (("eventlog", "Event Log"), ("case_table", "Cases"),
                               ("bottlenecks", "Bottlenecks"), ("variants", "Variants"),
                               ("conformance_cases", "Conformance"),
                               ("conformance_root_causes", "Root Causes")):
                t = (process_tables or {}).get(key)
                if t is not None and hasattr(t, "empty") and not t.empty:
                    t.head(max_rows).to_excel(writer, sheet_name=sheet, index=False)
                    wrote_any = True
            if not wrote_any:
                pd.DataFrame({"Note": [
                    "لاگ رویداد برای این اجرا ساخته نشده است.",
                    f"Reference date: {ref_date}"]}).to_excel(
                        writer, sheet_name="Process", index=False)
        if "table" in modules:
            default_cols = [
                "KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG", "CANONICAL_EXPERT",
                "ORG_DEPT", "روش حمل", "بحرانی (کوتاه)", "مقاومت (روز)", "BL_CRITICAL",
                "BL_CRITICAL_MATERIALS", "BL_CRITICAL_REASON", "ORDER_CRITICAL",
                "ORDER_CRITICAL_MATERIALS", "ORDER_CRITICAL_REASON"
            ]
            cols = [c for c in (selected_fields or default_cols) if c in df.columns]
            if not cols: cols = list(df.columns[:20])
            live = df[cols].head(max_rows)
            if field_labels:
                # سرستون فارسی — نگاشت باید یکتا باشد وگرنه pandas ستون تکراری می‌سازد
                ren = {c: field_labels[c] for c in cols if c in field_labels}
                if len(set(ren.values())) == len(ren):
                    live = live.rename(columns=ren)
            live.to_excel(writer, sheet_name="Live Data", index=False)
    wb = load_workbook(path)
    for ws in wb.worksheets:
        _style_sheet(ws)
        # Status-aware fills on common status columns.
        for col_idx, cell in enumerate(ws[1], start=1):
            if str(cell.value) in {"بحرانی (کوتاه)", "طبقه بحرانی"}:
                for row in range(2, ws.max_row + 1):
                    c = ws.cell(row=row, column=col_idx)
                    color = _status_color(c.value)
                    c.fill = PatternFill("solid", fgColor=color)
                    c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
    wb.save(path)
    return str(path)

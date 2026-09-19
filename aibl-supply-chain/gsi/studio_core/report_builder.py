# -*- coding: utf-8 -*-
"""سازنده گزارش — یک قالب + فیلدهای انتخابی → Excel / HTML / PDF.

هر سه خروجی از **یک منبع** ساخته می‌شوند: همان دیتافریم فیلترشده، همان
فهرست فیلد، همان قالب. پس عددی که در Excel است با عددی که در HTML و PDF
است یکی می‌ماند.

قاعده صحت: هر جمع عددی از ``grain.safe_agg`` می‌آید (یکتاسازی بر کلید
دانه‌ی همان ستون)، و برگه/بخش «صحت محاسبات» جمع ساده و جمع درست را کنار
هم می‌گذارد تا هیچ عددی بدون ردپا نماند.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from . import templates as tpl
from .excel_export import OfficialReportOverwrite, build_custom_excel
from .grain import fanout, integrity_report, summarize
from .html_export import build_dynamic_html
from .pdf_export import html_to_pdf


@dataclass
class ReportSpec:
    """درخواست ساخت گزارش."""
    template: str = tpl.DEFAULT_TEMPLATE
    fields: List[str] = field(default_factory=list)
    ref_date: str = ""
    title: str = "GSI"
    formats: List[str] = field(default_factory=lambda: ["html"])
    visuals: bool = True
    tables: bool = True
    max_rows: int = 0                 # صفر یعنی از قالب بخوان
    file_stem: str = "GSI Report"
    # تب‌های سفارشی مشترک بین HTML و Excel:
    # [{"title": "...", "fields": [...], "max_rows": 5000}]
    tabs: List[Dict] = field(default_factory=list)
    # نام نمودارهای ایمیل که از کاتالوگ نمودار مشترک انتخاب شده‌اند.
    email_charts: List[str] = field(default_factory=list)


@dataclass
class ReportResult:
    files: Dict[str, Path] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)
    integrity: Optional[pd.DataFrame] = None
    fanout: Optional[pd.DataFrame] = None
    html: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.files)


def _section_frames(df: pd.DataFrame, extras: Dict, sections: List[str],
                    fields: List[str], labels: Dict[str, str],
                    max_rows: int) -> Dict[str, pd.DataFrame]:
    """جدول‌های هر بخش قالب — همان‌هایی که به برگه‌های Excel می‌روند."""
    out: Dict[str, pd.DataFrame] = {}
    cols = [c for c in fields if c in df.columns]

    if "table" in sections and cols:
        t = df[cols].head(max_rows)
        ren = {c: labels.get(c, c) for c in cols}
        if len(set(ren.values())) == len(ren):
            t = t.rename(columns=ren)
        out["جدول تفصیلی"] = t

    if "integrity" in sections:
        rep = integrity_report(df, cols, labels)
        if not rep.empty:
            out["صحت محاسبات"] = rep
        fo = fanout(df)
        if not fo.empty:
            out["دانه‌بندی"] = fo
        summ = summarize(df, cols, labels)
        if not summ.empty:
            out["خلاصه عددی"] = summ

    # دفترکل FX یک جدول شیءمحور مستقل است و نباید با ردیف‌های BL fan-out شود.
    if "integrity" in sections:
        for src, sheet in (("fx_ledger", "رهگیری مالی-ارزی"),
                           ("fx_control_summary", "برج کنترل پول"),
                           ("fx_stage_timeline", "مراحل جریان پول"),
                           ("fx_rate_bridge", "پل نرخ و تبدیل ارز"),
                           ("fx_reallocations", "جابجایی بین پرونده‌ها"),
                           ("fx_anomalies", "مغایرت‌های FX"),
                           ("fx_eventlog", "رویدادهای FX")):
            t = (extras or {}).get(src)
            if t is not None and hasattr(t, "empty") and not t.empty:
                out[sheet] = t.head(max_rows)

    if "quality" in sections:
        rows = []
        for c in cols:
            s = df[c]
            filled = (s.notna() & (s.astype(str).str.strip() != "")).sum()
            rows.append({"فیلد": labels.get(c, c), "ستون": c,
                         "پرشدگی (٪)": round(100 * filled / max(len(df), 1), 1),
                         "نوع": str(s.dtype)})
        if rows:
            out["کیفیت داده"] = pd.DataFrame(rows).sort_values("پرشدگی (٪)")

    for key, sheet in (("bottlenecks", "گلوگاه"), ("variants", "مسیرها"),
                       ("conformance", "انطباق"), ("eventlog", "لاگ رویداد")):
        if key not in sections:
            continue
        src = {"bottlenecks": "bottlenecks", "variants": "variants",
               "conformance": "conformance_cases", "eventlog": "eventlog"}[key]
        t = (extras or {}).get(src)
        if t is not None and hasattr(t, "empty") and not t.empty:
            out[sheet] = t.head(max_rows)
        if key == "conformance":
            rc = (extras or {}).get("conformance_root_causes")
            if rc is not None and not rc.empty:
                out["ریشه‌یابی"] = rc

    return out


def _filtered_process_extras(extras: Dict, df: pd.DataFrame) -> Dict:
    out=dict(extras or {}); keys=set()
    for c in ("CASE_KEY","_CASE_KEY"):
        if c in df.columns: keys.update(df[c].dropna().astype(str).str.strip().replace("",pd.NA).dropna().tolist())
    if not keys:return out
    for name in ("eventlog","case_table","conformance_cases"):
        t=out.get(name)
        if isinstance(t,pd.DataFrame) and not t.empty:
            kc="_CASE_KEY" if "_CASE_KEY" in t.columns else ("CASE_KEY" if "CASE_KEY" in t.columns else None)
            if kc:out[name]=t[t[kc].astype(str).isin(keys)].copy()
    ev=out.get("eventlog")
    if isinstance(ev,pd.DataFrame) and not ev.empty and {"_CASE_KEY","ACTIVITY_FA","EVENTTIME"}.issubset(ev.columns):
        e=ev.copy();e["EVENTTIME"]=pd.to_datetime(e["EVENTTIME"],errors="coerce");e=e.sort_values(["_CASE_KEY","EVENTTIME"]);e["_NEXT"]=e.groupby("_CASE_KEY")["ACTIVITY_FA"].shift(-1);e["_NEXT_TIME"]=e.groupby("_CASE_KEY")["EVENTTIME"].shift(-1);x=e.dropna(subset=["_NEXT","EVENTTIME","_NEXT_TIME"]).copy();x["WAIT"]=(x["_NEXT_TIME"]-x["EVENTTIME"]).dt.total_seconds()/86400
        if not x.empty:
            # همان قرارداد ستونی مرحله ۸۰: میانه و صدک ۹۰، نه میانگین.
            # دو تولیدکننده با دو نام ستون، دقیقاً همان باگی بود که ستون
            # «پرونده» را در جدول گلوگاه همیشه خالی نگه می‌داشت.
            out["bottlenecks"] = (
                x[x["ACTIVITY_FA"] != x["_NEXT"]]
                .groupby(["ACTIVITY_FA", "_NEXT"])
                .agg(**{"میانه روز": ("WAIT", "median"),
                        "صدک ۹۰ روز": ("WAIT", lambda s: float(s.quantile(0.9))),
                        "بیشینه روز": ("WAIT", "max"),
                        "تعداد پرونده": ("_CASE_KEY", "nunique")})
                .reset_index()
                .rename(columns={"ACTIVITY_FA": "از فعالیت", "_NEXT": "به فعالیت"})
                .sort_values("میانه روز", ascending=False))
    return out

def build(df: pd.DataFrame, extras: Dict, spec: ReportSpec,
          labels: Optional[Dict[str, str]] = None,
          out_dir: str | Path = ".") -> ReportResult:
    """گزارش را در قالب‌های خواسته‌شده می‌سازد."""
    t = tpl.get(spec.template)
    labels = labels or {}
    sections = t.active_sections(spec.visuals, spec.tables)
    fields = [c for c in (spec.fields or t.default_fields) if c in df.columns]
    if not fields:
        fields = [c for c in t.default_fields if c in df.columns] or list(df.columns[:10])
    max_rows = spec.max_rows or t.max_rows
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = (spec.file_stem or "GSI Report").strip() or "GSI Report"

    res = ReportResult()
    res.integrity = integrity_report(df, fields, labels)
    res.fanout = fanout(df)

    frames = _section_frames(df, extras, sections, fields, labels, max_rows)

    # ── HTML (پایه‌ی PDF هم هست، تا هر دو یک سند باشند) ──
    subtitle = f"{len(df):,} ردیف · {len(fields):,} فیلد"
    res.html = build_dynamic_html(
        df, spec.ref_date, title=spec.title, max_rows=max_rows,
        selected_fields=fields, labels=labels,
        template_title=f"{t.icon} {t.title}", subtitle=subtitle,
        show_visuals=spec.visuals and ("criticality" in sections),
        tabs=spec.tabs, charts=spec.email_charts, process_extras=_filtered_process_extras(extras, df))

    if "html" in spec.formats:
        p = out_dir / f"{spec.ref_date}_{stem}.html"
        p.write_text(res.html, encoding="utf-8")
        res.files["html"] = p
        res.messages.append(f"HTML: {p.name}")

    # ── Excel ──
    if "excel" in spec.formats:
        p = out_dir / f"{spec.ref_date}_{stem}.xlsx"
        try:
            modules = ["kpi"]
            if "criticality" in sections:
                modules.append("criticality")
            if "table" in sections:
                modules.append("table")
            build_custom_excel(df, p, modules, spec.ref_date,
                               max_rows=max_rows, selected_fields=fields,
                               field_labels=labels, email_charts=spec.email_charts)
            _append_sheets(p, frames)
            _append_tab_sheets(p, df, spec.tabs, labels, max_rows)
            res.files["excel"] = p
            res.messages.append(f"Excel: {p.name}")
        except OfficialReportOverwrite as ex:
            res.messages.append(f"⚠️ {ex}")
        except Exception as ex:
            res.messages.append(f"⚠️ ساخت Excel ناموفق بود: {ex}")

    # ── PDF (از همان HTML) ──
    if "pdf" in spec.formats:
        p = out_dir / f"{spec.ref_date}_{stem}.pdf"
        r = html_to_pdf(res.html, p, landscape=True)
        if r.ok and r.path:
            res.files["pdf"] = r.path
            res.messages.append(f"PDF: {r.path.name}")
        else:
            res.messages.append(f"⚠️ {r.message}")
            if "html" not in res.files:      # دست‌کم HTML آماده چاپ بماند
                ph = out_dir / f"{spec.ref_date}_{stem}.html"
                ph.write_text(res.html, encoding="utf-8")
                res.files["html"] = ph

    return res


def _append_sheets(path: Path, frames: Dict[str, pd.DataFrame]) -> None:
    """برگه‌های قالب را به فایل Excel موجود اضافه می‌کند."""
    if not frames:
        return
    with pd.ExcelWriter(path, engine="openpyxl", mode="a",
                        if_sheet_exists="replace") as w:
        for name, t in frames.items():
            if t is None or t.empty:
                continue
            t.to_excel(w, sheet_name=str(name)[:31], index=False)


def _append_tab_sheets(path: Path, df: pd.DataFrame, tabs: List[Dict],
                       labels: Dict[str, str], max_rows: int) -> None:
    """هر تب سفارشی HTML یک شیت هم‌نام در Excel دارد."""
    if not tabs:
        return
    with pd.ExcelWriter(path, engine="openpyxl", mode="a",
                        if_sheet_exists="replace") as w:
        used = set()
        for tab in tabs:
            title = str(tab.get("title") or "تب")
            sheet = title[:31] or "Tab"
            # Excel نام شیت تکراری را نمی‌پذیرد.
            base_name, n = sheet, 2
            while sheet in used:
                suffix = f" {n}"
                sheet = (base_name[:31-len(suffix)] + suffix)
                n += 1
            used.add(sheet)
            cols = [c for c in tab.get("fields", []) if c in df.columns]
            if not cols:
                cols = list(df.columns[:12])
            cap = int(tab.get("max_rows") or max_rows)
            out = df[cols].head(cap).copy()
            ren = {c: labels.get(c, c) for c in cols}
            if len(set(ren.values())) == len(ren):
                out = out.rename(columns=ren)
            out.to_excel(w, sheet_name=sheet, index=False)
    # شیت‌های تازه‌افزوده‌شده هم باید همان استاندارد خوانایی خروجی Studio را داشته باشند.
    from .excel_export import _style_sheet
    from openpyxl import load_workbook
    wb = load_workbook(path)
    for tab in tabs:
        name = str(tab.get("title") or "تب")[:31]
        # ممکن است به علت تکرار، نام نهایی suffix گرفته باشد؛ نزدیک‌ترین نام را style می‌کنیم.
    for ws in wb.worksheets:
        _style_sheet(ws)
    wb.save(path)

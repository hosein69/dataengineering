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
from .access_control import AccessScope, apply_row_scope, filter_fields
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
    # نمودارهای HTML مستقل از ایمیل؛ برای سازگاری نسخه‌های Studio قدیمی.
    html_charts: List[str] = field(default_factory=list)
    # Scope واقعی پیش از serialize شدن artifact اعمال می‌شود؛ فیلتر مرورگر امنیت نیست.
    persona: str = "expert"
    departments: List[str] = field(default_factory=list)
    experts: List[str] = field(default_factory=list)
    allowed_fields: List[str] = field(default_factory=list)
    deny_sensitive: bool = True
    # lineage اجرای warehouse برای audit.
    warehouse_run_id: str = ""
    html_header: str = ""
    html_subtitle: str = ""
    html_header_preset: str = "figma_aqua"
    learning_enabled: bool = False
    learning_lesson: Dict = field(default_factory=dict)
    anythingllm_embed: Dict = field(default_factory=dict)  # legacy compatibility
    knowledge_chat: Dict = field(default_factory=dict)


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
                           ("fx_money_ledger", "دفتر کل صفر تا صد پول"),
                           ("fx_money_reconciliation", "تطبیق مبالغ و تعهد"),
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
    """Scope all process/action artifacts to the already-authorized report frame.

    The main dataframe has already passed :func:`apply_row_scope`.  Process
    mining and Kanban must therefore be narrowed to exactly the same case/order/
    registration/material universe; otherwise a manager/expert export can leak
    organisation-wide process/action data even though its table is scoped.
    """
    def _values(frame: pd.DataFrame, names) -> set[str]:
        vals: set[str] = set()
        for c in names:
            if c in frame.columns:
                x = frame[c].dropna().astype(str).str.strip()
                vals.update(x[x.ne("")].tolist())
        return vals

    case_keys = _values(df, ("CASE_KEY", "_CASE_KEY"))
    regs = _values(df, ("KEY_REG", "CANONICAL_REG", "import_reg_no", "REGISTRATION_NO"))
    orders = _values(df, ("KEY_ORDER", "CANONICAL_ORDER", "order_no", "ORDER_NO"))
    mats = _values(df, ("KEY_MATERIAL", "CANONICAL_MATERIAL", "material_code", "MATERIAL"))

    groups = [(("CASE_KEY", "_CASE_KEY"), case_keys),
              (("KEY_ORDER", "CANONICAL_ORDER", "ORDER_NO", "order_no"), orders),
              (("KEY_REG", "CANONICAL_REG", "REGISTRATION_NO", "import_reg_no"), regs),
              (("KEY_MATERIAL", "CANONICAL_MATERIAL", "MATERIAL", "material_code"), mats)]
    def _scope(_name, frame: pd.DataFrame) -> pd.DataFrame:
        scoped = frame.iloc[0:0].copy()
        for names, allowed in groups:
            common = next((c for c in names if c in frame.columns), None)
            if common is not None and allowed:
                scoped = frame[frame[common].fillna("").astype(str).str.strip().isin(allowed)].copy()
                break
        return scoped

    # محدودکردن دامنه باید روی همهٔ فریم‌ها اعمال شود، ولی خواندن‌شان از SQLite
    # نباید همین‌جا اتفاق بیفتد. اگر extras تنبل باشد، همان قاعده به‌صورت تنبل
    # روی آن می‌نشیند و فقط فریمی که واقعاً خوانده می‌شود ساخته می‌شود.
    if hasattr(extras, "with_frame_transform"):
        out = extras.with_frame_transform(_scope)
    else:
        out = dict(extras or {})
        for name, frame in list(out.items()):
            if isinstance(frame, pd.DataFrame):
                out[name] = _scope(name, frame)

    # Rebuild every derived process view from the scoped case/event population.
    cases = out.get("case_table")
    if isinstance(cases, pd.DataFrame) and not cases.empty:
        if {"CASE_STATE", "LAST_ACTIVITY", "CURRENT_WAIT_DAYS", "CASE_KEY"}.issubset(cases.columns):
            openc = cases[cases["CASE_STATE"].astype(str).eq("OPEN")].copy()
            if openc.empty:
                out["stage_queue"] = pd.DataFrame(columns=["مرحله جاری", "تعداد پرونده", "میانه انتظار (روز)", "بیشترین انتظار (روز)"])
            else:
                q = (openc.groupby("LAST_ACTIVITY", as_index=False)
                     .agg(**{"تعداد پرونده": ("CASE_KEY", "size"),
                             "میانه انتظار (روز)": ("CURRENT_WAIT_DAYS", "median"),
                             "بیشترین انتظار (روز)": ("CURRENT_WAIT_DAYS", "max")})
                     .rename(columns={"LAST_ACTIVITY": "مرحله جاری"}))
                for c in ("میانه انتظار (روز)", "بیشترین انتظار (روز)"):
                    q[c] = pd.to_numeric(q[c], errors="coerce").round(1)
                out["stage_queue"] = q.sort_values("تعداد پرونده", ascending=False).reset_index(drop=True)
        if {"VARIANT", "CASE_KEY"}.issubset(cases.columns):
            v = (cases.groupby("VARIANT", as_index=False)
                 .agg(**{"تعداد پرونده": ("CASE_KEY", "size"),
                         "پرونده بسته": ("THROUGHPUT_DAYS", "count") if "THROUGHPUT_DAYS" in cases.columns else ("CASE_KEY", "size")}))
            if "THROUGHPUT_DAYS" in cases.columns:
                med = cases.groupby("VARIANT")["THROUGHPUT_DAYS"].median().rename("میانه چرخه")
                v = v.merge(med, on="VARIANT", how="left")
            else:
                v["میانه چرخه"] = pd.NA
            total = float(v["تعداد پرونده"].sum() or 1)
            v["سهم (٪)"] = (v["تعداد پرونده"] / total * 100).round(1)
            out["variants"] = v.sort_values("تعداد پرونده", ascending=False).reset_index(drop=True)

    ev = out.get("eventlog")
    if isinstance(ev, pd.DataFrame) and not ev.empty:
        case_col = "_CASE_KEY" if "_CASE_KEY" in ev.columns else ("CASE_KEY" if "CASE_KEY" in ev.columns else None)
        act_col = "ACTIVITY_FA" if "ACTIVITY_FA" in ev.columns else None
        time_col = "EVENTTIME" if "EVENTTIME" in ev.columns else ("EVENT_DATE" if "EVENT_DATE" in ev.columns else None)
        if case_col and act_col and time_col:
            e = ev.copy()
            e[time_col] = pd.to_datetime(e[time_col], errors="coerce")
            e = e.sort_values([case_col, time_col])
            e["_NEXT"] = e.groupby(case_col)[act_col].shift(-1)
            e["_NEXT_TIME"] = e.groupby(case_col)[time_col].shift(-1)
            x = e.dropna(subset=["_NEXT", time_col, "_NEXT_TIME"]).copy()
            x["WAIT"] = (x["_NEXT_TIME"] - x[time_col]).dt.total_seconds() / 86400
            x = x[x[act_col].astype(str) != x["_NEXT"].astype(str)]
            if not x.empty:
                out["bottlenecks"] = (
                    x.groupby([act_col, "_NEXT"])
                     .agg(**{"میانه روز": ("WAIT", "median"),
                             "صدک ۹۰ روز": ("WAIT", lambda z: float(z.quantile(0.9))),
                             "بیشینه روز": ("WAIT", "max"),
                             "تعداد پرونده": (case_col, "nunique")})
                     .reset_index()
                     .rename(columns={act_col: "از فعالیت", "_NEXT": "به فعالیت"})
                     .sort_values("میانه روز", ascending=False)
                     .reset_index(drop=True))
    return out

def build(df: pd.DataFrame, extras: Dict, spec: ReportSpec,
          labels: Optional[Dict[str, str]] = None,
          out_dir: str | Path = ".") -> ReportResult:
    """گزارش را در قالب‌های خواسته‌شده می‌سازد."""
    t = tpl.get(spec.template)
    labels = labels or {}
    scope = AccessScope(persona=spec.persona, departments=list(spec.departments),
                        experts=list(spec.experts), allowed_fields=list(spec.allowed_fields),
                        deny_sensitive=spec.deny_sensitive)
    df = apply_row_scope(df, scope)
    extras = _filtered_process_extras(extras, df)
    df = df[filter_fields(df.columns, scope)].copy()
    sections = t.active_sections(spec.visuals, spec.tables)
    requested_fields = filter_fields((spec.fields or t.default_fields), scope)
    fields = [c for c in requested_fields if c in df.columns]
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
        show_visuals=spec.visuals,
        show_tables=spec.tables,
        show_process=False,  # Process/Kanban are composed per-tab by Report Composer.
        tabs=[{**tab, "fields": filter_fields(tab.get("fields", fields), scope)} for tab in spec.tabs], charts=(spec.html_charts or spec.email_charts),
        process_extras=_filtered_process_extras(extras, df),
        lineage={"warehouse_run_id": spec.warehouse_run_id} if spec.warehouse_run_id else None,
        audience=spec.persona, header_title=spec.html_header,
        header_subtitle=spec.html_subtitle, header_preset=spec.html_header_preset,
        learning_lesson=(spec.learning_lesson if spec.learning_enabled else None),
        anythingllm_embed=(spec.anythingllm_embed if spec.learning_enabled else None),
        knowledge_chat=(spec.knowledge_chat if spec.learning_enabled else None),
        material_supply_view=None, include_material_view=not bool(scope.allowed_fields))

    html_bytes = len(res.html.encode("utf-8"))
    html_mb = html_bytes / (1024 * 1024)
    res.messages.append(f"HTML بهینه: {html_mb:.2f} MB · payload ردیفی فشرده بدون حذف داده")
    if html_mb > 8:
        res.messages.append("⚠️ HTML هنوز بزرگ است؛ برای فایل سبک‌تر، max_rows هر تب یا Block جدول/Timeline را کاهش دهید.")

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
                               field_labels=labels, email_charts=(spec.html_charts or spec.email_charts))
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

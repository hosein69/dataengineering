# -*- coding: utf-8 -*-
"""سازنده گزارش — یک قالب و یک اجرا → Excel / HTML / PDF / ایمیل.

هر چهار خروجی از **یک منبع** ساخته می‌شوند، پس عددی که در Excel است با
HTML و PDF و ایمیل یکی می‌ماند.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from . import templates as tpl
from .email import build_email_html, recipients
from .excel import build_excel
from .html import build_html
from .pdf import html_to_pdf


@dataclass
class ReportSpec:
    template: str = tpl.DEFAULT_TEMPLATE
    ref_date: str = ""
    title: str = "داشبورد عملکرد منابع انسانی"
    formats: List[str] = field(default_factory=lambda: ["html"])
    visuals: bool = True
    tables: bool = True
    max_rows: int = 0
    file_stem: str = "HR Performance"
    management: str = ""          # فیلتر اختیاری
    job_family: str = ""


@dataclass
class ReportResult:
    files: Dict[str, Path] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)
    html: str = ""
    email_html: str = ""
    #: تعداد گیرندگان حل‌شده — فقط شمارش، هرگز خودِ نشانی‌ها.
    email_recipients: int = 0

    @property
    def ok(self) -> bool:
        return bool(self.files)


def _filtered(lb: pd.DataFrame, spec: ReportSpec) -> pd.DataFrame:
    out = lb
    if spec.management and "مدیریت" in out.columns:
        out = out[out["مدیریت"].astype(str) == spec.management]
    if spec.job_family and "نوع کار" in out.columns:
        out = out[out["نوع کار"].astype(str) == spec.job_family]
    return out


def build(run, spec: ReportSpec, out_dir: str | Path = ".") -> ReportResult:
    """``run`` خروجی ``Pipeline.run`` است."""
    t = tpl.get(spec.template)
    sections = t.active_sections(spec.visuals, spec.tables)
    max_rows = spec.max_rows or t.max_rows
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = (spec.file_stem or "HR Performance").strip()
    res = ReportResult()

    lb = _filtered(run.leaderboard, spec)
    clusters = None
    if "clusters" in sections and not run.scores.cluster_scores.empty:
        cl = run.scores.cluster_scores.round(1).copy()
        cl.columns = [run.model.clusters[c].label if c in run.model.clusters else c
                      for c in cl.columns]
        cl.index.name = "person_key"
        clusters = cl.reset_index()
        if "کد" in lb.columns:
            clusters = clusters[clusters["person_key"].isin(lb["کد"])]

    weights = None
    if "weights" in sections:
        rows = []
        for k, m in run.model.metrics.items():
            rows.append({
                "شاخص": m.label, "کلاستر": run.model.clusters[m.cluster].label
                if m.cluster in run.model.clusters else m.cluster,
                "نقش": {"scored": "امتیازی", "context": "زمینه"}.get(m.role, m.role),
                "وزن داخل کلاستر": round(m.weight, 4),
                "وزن مؤثر (٪)": round(run.model.effective_weight(k) * 100, 2)})
        weights = pd.DataFrame(rows).sort_values("وزن مؤثر (٪)", ascending=False)

    effects = run.effects if "causal" in sections else None
    peers = run.peer_summary if "peers" in sections else None
    calib = run.calibration if "calibration" in sections else None

    # ── HTML (پایه PDF هم هست) ──
    res.html = build_html(
        lb, ref_date=spec.ref_date, title=spec.title,
        template_title=f"{t.icon} {t.title}", sections=sections,
        clusters=clusters, effects=effects, peers=peers,
        calibration=calib, weights=weights, max_rows=max_rows,
        show_visuals=spec.visuals)

    if "html" in spec.formats:
        p = out_dir / f"{spec.ref_date}_{stem}.html"
        p.write_text(res.html, encoding="utf-8")
        res.files["html"] = p
        res.messages.append(f"HTML: {p.name}")

    if "excel" in spec.formats:
        p = out_dir / f"{spec.ref_date}_{stem}.xlsx"
        sheets = {"عملکرد": lb.head(max_rows)}
        if clusters is not None:
            sheets["کلاسترها"] = clusters
        if weights is not None:
            sheets["وزن‌ها"] = weights
        if effects is not None and not effects.empty:
            sheets["اثر علّی"] = effects
        if peers is not None and not peers.empty:
            sheets["گروه همتا"] = peers
        if calib is not None and not calib.empty:
            sheets["کالیبراسیون"] = calib
        try:
            build_excel(p, sheets)
            res.files["excel"] = p
            res.messages.append(f"Excel: {p.name}")
        except Exception as ex:
            res.messages.append(f"⚠️ ساخت Excel ناموفق بود: {ex}")

    if "pdf" in spec.formats:
        p = out_dir / f"{spec.ref_date}_{stem}.pdf"
        r = html_to_pdf(res.html, p, landscape=True)
        if r.ok and r.path:
            res.files["pdf"] = r.path
            res.messages.append(f"PDF: {r.path.name}")
        else:
            res.messages.append(f"⚠️ {r.message}")

    # ── بسته ایمیل ──
    if "email" in spec.formats:
        perf = pd.to_numeric(lb.get("عملکرد"), errors="coerce")
        rows = [("نفرات", f"{len(lb):,}"),
                ("میانه عملکرد", f"{perf.median():.1f}" if perf.notna().any() else "—"),
                ("زیر ۴۵", f"{int((perf < 45).sum()):,}"),
                ("بالای ۷۵", f"{int((perf >= 75).sum()):,}")]
        res.email_html = build_email_html(
            spec.title, spec.ref_date, rows,
            "خلاصه عملکرد دوره. جزئیات کامل در فایل‌های پیوست است.")
        p = out_dir / f"{spec.ref_date}_{stem}_email.html"
        p.write_text(res.email_html, encoding="utf-8")
        res.files["email"] = p
        res.messages.append(f"بسته ایمیل: {p.name}")
        # فهرست گیرندگان از همان جدول پرسنلی این اجرا حل می‌شود
        # (HRP_EMAIL_FROM_HR=1). فقط تعداد ثبت می‌شود؛ نشانی‌ها نه.
        try:
            res.email_recipients = len(recipients(getattr(run, "people", None)))
        except Exception:
            res.email_recipients = 0
        res.messages.append(f"گیرندگان: {res.email_recipients}")

    return res

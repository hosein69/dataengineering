# -*- coding: utf-8 -*-
"""ثبت سلامت سیستم — سورس، مرحله، ادغام، زمان‌بندی، پوشش.

## چرا این ماژول

گزارش می‌گفت «۰ سفارش خارج از Commercial Expert Data» و مدیر آن را
«همه‌چیز مرتب است» می‌خواند. ولی همان عدد می‌توانست معنی دیگری بدهد:
**فایل اصلاً بارگذاری نشده بود.**

نقطه کور اینجاست: خروجی عددی درست، ولی *مبنای* آن نامعلوم. سیستمی که
روی آن تصمیم گرفته می‌شود باید بتواند بگوید این عدد از کجا آمده و در
لحظه تولیدش چه چیزی سالم و چه چیزی خراب بوده.

این ماژول یک دفتر ثبت ساده و درون‌فرآیندی است که هر بخش خط لوله در آن
وضعیت خودش را می‌نویسد، و در پایان یک شیت «۱۷. سلامت سیستم» و یک بخش در
داشبورد از آن ساخته می‌شود.

پنج دفتر:

    sources   هر سورس منطقی: وضعیت، الزامی/اختیاری، فایل، فریم، ردیف، زمان، خطا
    stages    هر مرحله: ردیف ورودی/خروجی، ستون افزوده، زمان، خطا
    joins     هر ادغام: کلید، ردیف قبل/بعد، رکورد منطبق
    schema    شکاف اسکیما: شیت یا ستونی که انتظارش را داشتیم و نبود
    findings  یافته‌های عمومی با شدت (info | warn | error)

## قاعده

هیچ‌کدام از این‌ها جریان داده را عوض نمی‌کنند — فقط ثبت می‌کنند. تنها
جایی که ثبت به تصمیم تبدیل می‌شود ``blocking()`` است که می‌گوید کدام
KPI‌ها امروز قابل اتکا نیستند.
"""
from __future__ import annotations

__contract__ = 1

import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

OK, DEGRADED, FAILED, SKIPPED = "سالم", "ناقص", "خراب", "رد شد"
INFO, WARN, ERROR = "info", "warn", "error"

_SEVERITY_FA = {INFO: "اطلاع", WARN: "هشدار", ERROR: "خطا"}


@dataclass
class SourceHealth:
    key: str
    title: str = ""
    required: bool = True
    status: str = SKIPPED
    files: int = 0
    file_name: str = ""
    frames: int = 0
    rows: int = 0
    elapsed_s: float = 0.0
    error: str = ""
    schema_gaps: List[str] = field(default_factory=list)


@dataclass
class StageHealth:
    name: str
    title: str = ""
    order: int = 0
    status: str = OK
    rows_in: int = 0
    rows_out: int = 0
    cols_added: int = 0
    elapsed_s: float = 0.0
    error: str = ""


@dataclass
class JoinHealth:
    label: str
    key: str = ""
    rows_before: int = 0
    rows_after: int = 0
    matched: int = 0
    status: str = OK
    note: str = ""


@dataclass
class Finding:
    area: str
    severity: str
    message: str
    detail: str = ""


class SystemHealth:
    """دفتر ثبت سلامت یک اجرا."""

    def __init__(self) -> None:
        self.sources: Dict[str, SourceHealth] = {}
        self.stages: List[StageHealth] = []
        self.joins: List[JoinHealth] = []
        self.findings: List[Finding] = []
        self.started = time.time()

    # ── ثبت ──────────────────────────────────────────────────────────────
    def source(self, key: str, **kw) -> SourceHealth:
        rec = self.sources.get(key) or SourceHealth(key=key)
        for k, v in kw.items():
            setattr(rec, k, v)
        self.sources[key] = rec
        return rec

    def schema_gap(self, source_key: str, what: str) -> None:
        """شیت یا ستونی که انتظارش را داشتیم و نبود."""
        rec = self.source(source_key)
        if what not in rec.schema_gaps:
            rec.schema_gaps.append(what)
        # شکاف اسکیما یعنی «فایل بود، ساختارش نبود» — این همیشه «ناقص»
        # است، از هر وضعیت اولیه‌ای. تنها چیزی که آن را بازنویسی نمی‌کند
        # خرابی کامل است، که خبر بدتری است.
        if rec.status != FAILED:
            rec.status = DEGRADED
        self.find("اسکیما", ERROR, f"[{source_key}] {what}")

    def stage(self, rec: StageHealth) -> None:
        self.stages.append(rec)

    def join(self, rec: JoinHealth) -> None:
        self.joins.append(rec)

    def find(self, area: str, severity: str, message: str, detail: str = "") -> None:
        self.findings.append(Finding(area, severity, message, detail))

    @contextmanager
    def timed_stage(self, name: str, title: str = "", order: int = 0,
                    rows_in: int = 0, cols_in: int = 0):
        """زمان، ردیف و ستونِ یک مرحله را می‌گیرد — حتی وقتی استثنا بدهد."""
        rec = StageHealth(name=name, title=title, order=order, rows_in=rows_in)
        t0 = time.time()
        box: Dict[str, Any] = {"df": None}
        try:
            yield box
        except Exception as ex:                     # noqa: BLE001 — ثبت و پرتاب دوباره
            rec.status = FAILED
            rec.error = f"{type(ex).__name__}: {ex}"
            rec.elapsed_s = round(time.time() - t0, 3)
            self.stage(rec)
            self.find("مرحله", ERROR, f"مرحله «{name}» شکست خورد", rec.error)
            raise
        rec.elapsed_s = round(time.time() - t0, 3)
        out = box.get("df")
        if out is not None:
            rec.rows_out = len(out)
            rec.cols_added = max(len(out.columns) - cols_in, 0)
        self.stage(rec)

    # ── جمع‌بندی ────────────────────────────────────────────────────────
    def blocking(self) -> List[str]:
        """کدام سورس‌های الزامی خرابند — یعنی کدام KPI امروز قابل اتکا نیست."""
        return sorted(k for k, s in self.sources.items()
                      if s.required and s.status in (FAILED, SKIPPED))

    def counts(self) -> Dict[str, int]:
        return {
            "سورس سالم": sum(1 for s in self.sources.values() if s.status == OK),
            "سورس ناقص": sum(1 for s in self.sources.values() if s.status == DEGRADED),
            "سورس خراب/ردشده": sum(1 for s in self.sources.values()
                                   if s.status in (FAILED, SKIPPED)),
            "مرحله شکست‌خورده": sum(1 for s in self.stages if s.status == FAILED),
            "خطا": sum(1 for f in self.findings if f.severity == ERROR),
            "هشدار": sum(1 for f in self.findings if f.severity == WARN),
        }

    def verdict(self) -> str:
        c = self.counts()
        if self.blocking() or c["مرحله شکست‌خورده"]:
            return FAILED
        if c["خطا"] or c["سورس ناقص"] or c["سورس خراب/ردشده"]:
            return DEGRADED
        return OK

    # ── جدول‌ها برای گزارش ──────────────────────────────────────────────
    def sources_table(self) -> pd.DataFrame:
        rows = [{
            "سورس": s.key,
            "شرح": s.title,
            "وضعیت": s.status,
            "الزامی": "بله" if s.required else "خیر",
            "فایل": s.file_name or ("—" if not s.files else str(s.files)),
            "تعداد فریم": s.frames,
            "تعداد ردیف": s.rows,
            "زمان (ثانیه)": s.elapsed_s,
            "شکاف اسکیما": "، ".join(s.schema_gaps),
            "خطا": s.error,
        } for s in sorted(self.sources.values(), key=lambda x: x.key)]
        return pd.DataFrame(rows)

    def stages_table(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "ترتیب": s.order, "مرحله": s.name, "شرح": s.title, "وضعیت": s.status,
            "ردیف ورودی": s.rows_in, "ردیف خروجی": s.rows_out,
            "ستون افزوده": s.cols_added, "زمان (ثانیه)": s.elapsed_s,
            "خطا": s.error,
        } for s in self.stages])

    def joins_table(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "ادغام": j.label, "کلید": j.key, "ردیف قبل": j.rows_before,
            "ردیف بعد": j.rows_after, "رکورد منطبق": j.matched,
            "وضعیت": j.status, "توضیح": j.note,
        } for j in self.joins])

    def findings_table(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "حوزه": f.area, "شدت": _SEVERITY_FA.get(f.severity, f.severity),
            "پیام": f.message, "جزئیات": f.detail,
        } for f in self.findings])

    def as_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict(),
            "counts": self.counts(),
            "blocking": self.blocking(),
            "sources": [asdict(s) for s in self.sources.values()],
            "stages": [asdict(s) for s in self.stages],
            "joins": [asdict(j) for j in self.joins],
            "findings": [asdict(f) for f in self.findings],
        }


#: کلیدهایی که باید در جدول اصلی یکتا بمانند. اگر مرحله‌ای آن‌ها را
#: تکراری کند، هر جمع و شمارشی پس از آن دوباره‌شماری می‌کند — بی‌صدا.
UNIQUE_KEYS = ("PARTITION_KEY",)


def check_key_integrity(stage_name: str, df, keys=UNIQUE_KEYS) -> None:
    """گارد یکتایی کلید — چیزی که گارد تعداد سطر نمی‌گیرد.

    تعداد سطر می‌تواند ثابت بماند ولی یک کلید یکتا تکراری شود (مثلاً با
    بازنویسی ستون کلید). آن‌وقت جمع‌ها درست به نظر می‌رسند و غلط‌اند.
    """
    for key in keys:
        if key not in getattr(df, "columns", ()):
            continue
        vals = df[key].astype(str).str.strip()
        vals = vals[vals.ne("")]
        dup = int(len(vals) - vals.nunique())
        if dup > 0:
            current().find(
                "مرحله", WARN,
                f"پس از مرحله «{stage_name}» کلید «{key}» {dup} مقدار تکراری دارد",
                "شمارش‌های مبتنی بر این کلید ممکن است دوباره‌شماری کنند.")


def log_slowest_stages(logger, top: int = 3) -> None:
    """گلوگاه زمانی اجرا — بدون آن، «کند شده» به حدس ختم می‌شود."""
    recs = sorted(current().stages, key=lambda s: s.elapsed_s, reverse=True)
    if not recs:
        return
    logger.info("⏱️ کندترین مرحله‌ها: "
                + " | ".join(f"{r.name} {r.elapsed_s:.2f}s" for r in recs[:top]))


HEALTH_FILE = "AIBL_System_Health.json"


def save(folder: str, hp: Optional["SystemHealth"] = None) -> str:
    """دفتر را کنار گزارش می‌نویسد.

    ``python -m aibl email`` و داشبورد Streamlit در فرآیند دیگری اجرا
    می‌شوند و دفترِ درون‌حافظه‌ای را نمی‌بینند. بدون این فایل، ایمیل
    مدیریتی نمی‌تواند بگوید «عدد امروز بر مبنای داده ناقص است» — و
    دقیقاً همان‌جاست که خواننده فرض می‌کند همه‌چیز سالم بوده.
    """
    import json
    import os
    hp = hp or HEALTH
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, HEALTH_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hp.as_dict(), f, ensure_ascii=False, indent=1)
    return path


def load(folder: str) -> Optional[Dict[str, Any]]:
    """دفتر ثبت‌شده آخرین اجرا؛ ``None`` اگر نبود."""
    import json
    import os
    path = os.path.join(folder, HEALTH_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


#: دفتر ثبت اجرای جاری. خط لوله در شروع هر اجرا آن را تازه می‌کند.
HEALTH = SystemHealth()


def reset() -> SystemHealth:
    global HEALTH
    HEALTH = SystemHealth()
    return HEALTH


def current() -> SystemHealth:
    return HEALTH

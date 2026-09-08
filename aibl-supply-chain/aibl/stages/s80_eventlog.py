# -*- coding: utf-8 -*-
"""مرحله ۸۰ — تولید لاگ رویداد (Event Log) مطابق استاندارد Celonis.

## چرا

تا اینجا سیستم «وضعیت» را گزارش می‌کرد: این پرونده الان کجاست. اما سؤال
مدیریتی واقعی علّی است: **چرا اینجاست و کجا زمان از دست می‌رود.**
پاسخ به آن نیازمند نگاه فرآیندی است، نه نگاه ردیفی.

## استاندارد

جدول فعالیت Celonis سه ستون الزامی دارد و یک ستون اختیاری:

    _CASE_KEY    شناسه پرونده
    ACTIVITY_EN  نام فعالیت
    EVENTTIME    زمان رویداد
    _SORTING     ترتیب، برای رویدادهایی که زمان یکسان دارند

ستون ``_SORTING`` اختیاری است ولی **حیاتی**: بسیاری از رویدادهای این فرآیند
فقط تاریخ دارند نه ساعت، پس چند فعالیت در یک روز زمان یکسان می‌گیرند. بدون
ستون ترتیب، گراف فرآیند نامعین می‌شود و مسیرها به‌صورت تصادفی یا الفبایی
مرتب می‌شوند. اینجا هر فعالیت یک عدد ترتیب ثابت دارد که از ترتیب منطقی
چرخه عمر در ``fx_governance.yaml`` می‌آید.

## خروجی‌ها

    ctx.extras["eventlog"]       جدول فعالیت (سطح رویداد)
    ctx.extras["case_table"]     جدول پرونده (سطح مورد) با throughput و variant
    ctx.extras["bottlenecks"]    میانگین زمان بین فعالیت‌های متوالی
    فایل AIBL_EventLog.csv       آماده بارگذاری مستقیم در Celonis
"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

import pandas as pd

from ..config.settings import SETTINGS
from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val
from ..dataio.logging_setup import log
from .base import (ColumnSpec, GROUP_ANALYTIC, PipelineContext, Stage, register)

#: (ستون تاریخ, نام انگلیسی فعالیت, نام فارسی, عدد ترتیب, مرحله چرخه عمر)
#: افزودن فعالیت جدید = یک سطر اینجا. هیچ فایل دیگری تغییر نمی‌کند.
ACTIVITIES: List[Tuple[str, str, str, int, str]] = [
    ("PO_SENT_DATE",       "PO Sent to Vendor",        "ابلاغ سفارش به تأمین‌کننده", 30, "PO"),
    ("NTSW_COMMIT_DATE",   "FX Commitment Created",     "ایجاد تعهد ارزی",           40, "ORDER_REG"),
    ("NTSW_ALLOC_DATE",    "FX Allocated",              "تخصیص ارز",                 50, "ALLOCATION"),
    ("BUY_DATE",           "FX Purchased",              "خرید ارز",                  60, "FX_SUPPLY"),
    ("BL_DATE",            "Goods Shipped",             "صدور بارنامه (حمل)",        70, "SHIPMENT"),
    ("ARRIVAL_DATE",       "Vessel Arrived",            "ورود محموله",               75, "SHIPMENT"),
    ("DISCHARGE_DATE",     "Cargo Discharged",          "تخلیه محموله",              80, "CUSTOMS"),
    ("DOC_SUBMIT_DATE",    "Documents Submitted",       "ارائه اسناد به بانک",       85, "DOCS"),
    ("COT_DATE",           "Customs Declaration Filed", "ثبت کوتاژ گمرکی",           90, "CUSTOMS"),
    ("SATA_DATE",          "SATA Code Issued",          "صدور کد ساتا",              95, "CUSTOMS"),
    ("PARTIAL_CLEAR_DATE", "Partially Cleared",         "ترخیص درصدی",              100, "CUSTOMS"),
    ("FULL_CLEAR_DATE",    "Fully Cleared",             "ترخیص کامل",               105, "CUSTOMS"),
    ("FIN_RECEIPT_DATE",   "Financial Receipt Booked",  "ثبت رسید مالی",            110, "RELEASE"),
]

#: صفت‌های پرونده که همراه هر رویداد حمل می‌شوند (Case attributes)
CASE_ATTRS = [
    ("CANONICAL_BL", "BL_NO"),
    ("CANONICAL_PART_NO", "PART_NO"),
    ("CANONICAL_EXPERT", "RESOURCE"),
    ("ORG_DEPT", "ORG_UNIT"),
    ("CURRENCY", "CURRENCY"),
    ("CB_VALUE", "CASE_VALUE"),
    ("کد طبقه بحرانی", "CRITICALITY"),
    ("نوع پرونده", "SEGMENT"),
    ("TRANSPORT_MODE", "TRANSPORT_MODE"),
]


@register
class EventLogStage(Stage):
    name = "eventlog"
    title = "لاگ رویداد فرآیند (استاندارد Celonis)"
    order = 80
    tolerant = True          # نبود بعضی تاریخ‌ها فقط رویداد کمتر می‌سازد، نه خطا
    requires = ["CANONICAL_ORDER", "BL_DATE"]
    provides = ["CASE_KEY", "THROUGHPUT_DAYS", "VARIANT", "EVENT_COUNT",
                "PROCESS_COMPLETENESS"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        df["CASE_KEY"] = [
            self._case_key(r) for r in df.to_dict("records")]

        events = self._build_events(df)
        ctx.extras["eventlog"] = events
        if events.empty:
            log.warning("⚠️ [eventlog] هیچ رویداد دارای تاریخ معتبری ساخته نشد.")
            for c in ("THROUGHPUT_DAYS", "VARIANT", "EVENT_COUNT", "PROCESS_COMPLETENESS"):
                df[c] = 0 if c != "VARIANT" else ""
            return df

        cases = self._build_case_table(events)
        ctx.extras["case_table"] = cases
        ctx.extras["bottlenecks"] = self._bottlenecks(events)
        ctx.extras["variants"] = self._variants(cases)

        # PerformanceWarning: به‌جای چهار انتساب جداگانه، یکجا concat می‌شود
        merged = df[["CASE_KEY"]].merge(cases, on="CASE_KEY", how="left")
        event_count = merged["EVENT_COUNT"].fillna(0).astype(int).values
        block = pd.DataFrame({
            "THROUGHPUT_DAYS": merged["THROUGHPUT_DAYS"].fillna(0).values,
            "VARIANT": merged["VARIANT"].fillna("").values,
            "EVENT_COUNT": event_count,
            "PROCESS_COMPLETENESS": (event_count / len(ACTIVITIES) * 100).round(1),
        }, index=df.index)
        df = pd.concat([df.drop(columns=block.columns, errors="ignore"), block], axis=1)

        self._export_csv(events, cases)
        log.info(f"🔄 لاگ رویداد: {len(events)} رویداد در {len(cases)} پرونده، "
                 f"{cases['VARIANT'].nunique()} مسیر متمایز، "
                 f"میانگین throughput {cases['THROUGHPUT_DAYS'].mean():.0f} روز.")
        return df

    # ── ساخت رویدادها ──
    @staticmethod
    def _case_key(row: Dict) -> str:
        for k in ("CANONICAL_ORDER", "CANONICAL_BL", "CANONICAL_REG"):
            v = row.get(k)
            if not is_empty_val(v):
                return str(v)
        return ""

    def _build_events(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for rec in df.to_dict("records"):
            case = rec.get("CASE_KEY", "")
            if not case:
                continue
            attrs = {dst: rec.get(src, "") for src, dst in CASE_ATTRS}
            for col, en, fa, sort, stage in ACTIVITIES:
                raw = rec.get(col)
                if is_empty_val(raw):
                    continue
                d = CalendarEngine.parse(raw)
                if d is None:
                    continue
                rows.append({
                    "_CASE_KEY": case,
                    "ACTIVITY_EN": en,
                    "ACTIVITY_FA": fa,
                    "EVENTTIME": pd.Timestamp(d),
                    "_SORTING": sort,
                    "LIFECYCLE_STAGE": stage,
                    **attrs,
                })
        if not rows:
            return pd.DataFrame(columns=["_CASE_KEY", "ACTIVITY_EN", "EVENTTIME", "_SORTING"])
        ev = pd.DataFrame(rows)
        # ترتیب قطعی: زمان، سپس ستون ترتیب — دقیقاً منطق Celonis
        return ev.sort_values(["_CASE_KEY", "EVENTTIME", "_SORTING"],
                              kind="mergesort").reset_index(drop=True)

    # ── جدول پرونده ──
    @staticmethod
    def _build_case_table(ev: pd.DataFrame) -> pd.DataFrame:
        g = ev.groupby("_CASE_KEY", sort=False)
        out = pd.DataFrame({
            "CASE_KEY": list(g.groups.keys()),
            "FIRST_EVENT": g["EVENTTIME"].min().values,
            "LAST_EVENT": g["EVENTTIME"].max().values,
            "EVENT_COUNT": g.size().values,
            "VARIANT": g["ACTIVITY_FA"].apply(lambda s: " ← ".join(s)).values,
            "FIRST_ACTIVITY": g["ACTIVITY_FA"].first().values,
            "LAST_ACTIVITY": g["ACTIVITY_FA"].last().values,
        })
        out["THROUGHPUT_DAYS"] = (
            (out["LAST_EVENT"] - out["FIRST_EVENT"]).dt.days).astype(float)
        # rework = فعالیت تکراری در یک پرونده
        rew = g["ACTIVITY_EN"].apply(lambda s: int(len(s) - s.nunique()))
        out["REWORK_COUNT"] = rew.values
        return out

    # ── گلوگاه: میانگین فاصله بین فعالیت‌های متوالی ──
    @staticmethod
    def _bottlenecks(ev: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for case, g in ev.groupby("_CASE_KEY", sort=False):
            g = g.reset_index(drop=True)
            for i in range(len(g) - 1):
                rows.append({
                    "از فعالیت": g.loc[i, "ACTIVITY_FA"],
                    "به فعالیت": g.loc[i + 1, "ACTIVITY_FA"],
                    "روز": (g.loc[i + 1, "EVENTTIME"] - g.loc[i, "EVENTTIME"]).days,
                })
        if not rows:
            return pd.DataFrame(columns=["از فعالیت", "به فعالیت", "میانگین روز", "تعداد"])
        t = pd.DataFrame(rows)
        out = (t.groupby(["از فعالیت", "به فعالیت"], as_index=False)
                 .agg(**{"میانگین روز": ("روز", "mean"),
                         "بیشینه روز": ("روز", "max"),
                         "تعداد": ("روز", "size")}))
        out["میانگین روز"] = out["میانگین روز"].round(1)
        return out.sort_values("میانگین روز", ascending=False).reset_index(drop=True)

    @staticmethod
    def _variants(cases: pd.DataFrame) -> pd.DataFrame:
        out = (cases.groupby("VARIANT", as_index=False)
                    .agg(**{"تعداد پرونده": ("CASE_KEY", "size"),
                            "میانگین throughput": ("THROUGHPUT_DAYS", "mean")}))
        out["میانگین throughput"] = out["میانگین throughput"].round(1)
        total = out["تعداد پرونده"].sum() or 1
        out["سهم (٪)"] = (out["تعداد پرونده"] / total * 100).round(1)
        return out.sort_values("تعداد پرونده", ascending=False).reset_index(drop=True)

    # ── خروجی CSV برای بارگذاری مستقیم در Celonis ──
    @staticmethod
    def _export_csv(events: pd.DataFrame, cases: pd.DataFrame) -> None:
        try:
            os.makedirs(SETTINGS.OUTPUT_DIR, exist_ok=True)
            ev_path = os.path.join(SETTINGS.OUTPUT_DIR, "AIBL_EventLog.csv")
            ca_path = os.path.join(SETTINGS.OUTPUT_DIR, "AIBL_CaseTable.csv")
            events.to_csv(ev_path, index=False, encoding="utf-8-sig")
            cases.to_csv(ca_path, index=False, encoding="utf-8-sig")
            log.info(f"📤 جدول فعالیت و جدول پرونده برای Celonis ذخیره شد: {ev_path}")
        except Exception as ex:
            log.warning(f"⚠️ [eventlog] ذخیره CSV ناموفق: {ex}")

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("THROUGHPUT_DAYS", "طول چرخه (روز)", 16, GROUP_ANALYTIC,
                       fmt="decimal", order=90, color_rule="scale_high_bad"),
            ColumnSpec("EVENT_COUNT", "تعداد رویداد", 14, GROUP_ANALYTIC,
                       fmt="int", order=91),
            ColumnSpec("PROCESS_COMPLETENESS", "تکمیل فرآیند (٪)", 16,
                       GROUP_ANALYTIC, fmt="decimal", order=92),
            ColumnSpec("VARIANT", "مسیر طی‌شده", 70, GROUP_ANALYTIC,
                       wrap=True, order=93),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        cases = ctx.extras.get("case_table")
        if cases is None or cases.empty:
            return {}
        bn = ctx.extras.get("bottlenecks")
        worst = ""
        if bn is not None and not bn.empty:
            top = bn.iloc[0]
            worst = f"{top['از فعالیت']} → {top['به فعالیت']} ({top['میانگین روز']:.0f} روز)"
        return {
            "میانگین طول چرخه (روز)": (round(float(cases["THROUGHPUT_DAYS"].mean()), 1),
                                        "از نخستین تا آخرین رویداد پرونده"),
            "تعداد مسیرهای متمایز فرآیند": (int(cases["VARIANT"].nunique()),
                                             "هرچه بیشتر، فرآیند بی‌انضباط‌تر"),
            "گلوگاه اصلی فرآیند": (worst, "طولانی‌ترین فاصله میان دو فعالیت متوالی"),
        }

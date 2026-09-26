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

## قاعده‌ای که V27 اضافه کرد: تکرار رکورد، دوباره‌کاری نیست

فریم اصلی در دانه «کالا × بارنامه × سفارش» است. یک سفارش با ده قلم کالا،
ده ردیف دارد و هر ده ردیف **همان** تاریخ ابلاغ سفارش را حمل می‌کنند.
نسخه قبلی برای هر ردیف یک رویداد می‌ساخت، پس:

    رویداد واقعی: ۲          رویدادی که ساخته می‌شد: ۲۰
    دوباره‌کاری واقعی: ۰      دوباره‌کاری گزارش‌شده: ۱۸
    تکمیل فرآیند: ۱۳۳٪        ← از ۱۰۰ رد می‌کرد
    مسیر: «ابلاغ سفارش ← ابلاغ سفارش ← ابلاغ سفارش ← …»

و جدول گلوگاه پر می‌شد از گذارهای «به خودش» با صفر روز، که وجود خارجی
ندارند. هر تحلیلی که روی این بنا می‌شد — واریانت، گلوگاه، انطباق — غلط
را با اطمینان نشان می‌داد.

حالا کلید یکتایی رویداد **(پرونده، فعالیت، تاریخ)** است. تعداد ردیف‌های
منبعی که به یک رویداد رسیده‌اند در ``SOURCE_ROWS`` نگه داشته می‌شود تا
چیزی پنهان نشود؛ ولی در تحلیل، یک رویداد یک بار شمرده می‌شود.

## خروجی‌ها

    ctx.extras["eventlog"]       جدول فعالیت (سطح رویداد، یکتاشده)
    ctx.extras["case_table"]     جدول پرونده با زمان چرخه، سن پرونده و انتظار جاری
    ctx.extras["bottlenecks"]    میانه/صدک۹۰ گذارها + صف جاری هر مرحله
    ctx.extras["stage_queue"]    پرونده‌هایی که همین حالا در هر مرحله منتظرند
    فایل GSI_EventLog.csv       آماده بارگذاری مستقیم در Celonis
"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

import numpy as np
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
    ("FUND_DATE",          "Bank Funding Recorded",     "ثبت تأمین وجه بانکی",       62, "FX_SUPPLY"),
    ("SWIFT_DATE",         "SWIFT Recorded",            "ثبت/دریافت سوئیفت",         65, "FX_SUPPLY"),
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

#: فعالیت‌هایی که «پایان مسیر» شمرده می‌شوند.
#:
#: این فهرست عمداً کوتاه است و عمداً **رسید مالی** را هم شامل می‌شود، نه فقط
#: ترخیص: پرونده‌ای که کالایش ترخیص شده ولی رسید مالی‌اش ثبت نشده، هنوز
#: بسته نیست. تعریف کامل‌تر «بستن پرونده» (پذیرش کیفی، تسویه، تکمیل اسناد)
#: هنوز داده‌اش در دسترس نیست؛ وقتی آمد، فقط همین چند سطر عوض می‌شود.
TERMINAL_ACTIVITIES = {"Financial Receipt Booked"}

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
    ("PAYMENT_METHOD", "PAYMENT_METHOD"),
    ("CANONICAL_REG", "REGISTRATION_NO"),
]


@register
class EventLogStage(Stage):
    name = "eventlog"
    title = "لاگ رویداد فرآیند (استاندارد Celonis)"
    order = 80
    tolerant = True          # نبود بعضی تاریخ‌ها فقط رویداد کمتر می‌سازد، نه خطا
    requires = ["CANONICAL_ORDER", "BL_DATE"]
    provides = ["CASE_KEY", "CASE_KEY_BASIS", "THROUGHPUT_DAYS", "CASE_AGE_DAYS",
                "CURRENT_WAIT_DAYS", "CASE_STATE", "VARIANT", "EVENT_COUNT",
                "SOURCE_ROW_COUNT", "REWORK_COUNT", "PROCESS_COMPLETENESS",
                "ORDER_CERTAIN"]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        keys, basis = self._case_keys(df)
        df["CASE_KEY"] = keys
        df["CASE_KEY_BASIS"] = basis

        events = self._build_events(df)
        ctx.extras["eventlog"] = events
        if events.empty:
            log.warning("⚠️ [eventlog] هیچ رویداد دارای تاریخ معتبری ساخته نشد.")
            for c in self.provides:
                if c in ("CASE_KEY", "CASE_KEY_BASIS"):
                    continue
                df[c] = "" if c in ("VARIANT", "CASE_STATE") else 0
            df["CASE_STATE"] = "NO_EVIDENCE"
            return df

        cases = self._build_case_table(events, ctx.today)
        ctx.extras["case_table"] = cases
        ctx.extras["stage_queue"] = self._stage_queue(cases)
        ctx.extras["bottlenecks"] = self._bottlenecks(events, cases)
        ctx.extras["variants"] = self._variants(cases)

        merged = (df[["CASE_KEY"]].merge(cases, on="CASE_KEY", how="left")
                  if "CASE_KEY" in cases.columns else pd.DataFrame(index=df.index))
        block = pd.DataFrame({
            "THROUGHPUT_DAYS": merged["THROUGHPUT_DAYS"].values,
            "CASE_AGE_DAYS": merged["CASE_AGE_DAYS"].values,
            "CURRENT_WAIT_DAYS": merged["CURRENT_WAIT_DAYS"].values,
            "CASE_STATE": merged["CASE_STATE"].fillna("NO_EVIDENCE").values,
            "VARIANT": merged["VARIANT"].fillna("").values,
            "EVENT_COUNT": merged["EVENT_COUNT"].fillna(0).astype(int).values,
            "SOURCE_ROW_COUNT": merged["SOURCE_ROWS"].fillna(0).astype(int).values,
            "REWORK_COUNT": merged["REWORK_COUNT"].fillna(0).astype(int).values,
            "PROCESS_COMPLETENESS": merged["PROCESS_COMPLETENESS"].values,
            # nullable boolean را صریح می‌کنیم تا pandas آینده رفتار
            # fillna(object) را بی‌صدا عوض نکند. پرونده بدون event evidence
            # طبق قرارداد موجود True می‌ماند.
            "ORDER_CERTAIN": merged["ORDER_CERTAIN"].astype("boolean").fillna(True).astype(bool).values,
        }, index=df.index)
        df = pd.concat([df.drop(columns=block.columns, errors="ignore"), block], axis=1)

        # Event/case history is persisted by the warehouse pipeline; CSV is an explicit UI export only.
        closed = cases[cases["CASE_STATE"] == "CLOSED"]
        dup = int(cases["SOURCE_ROWS"].sum() - cases["EVENT_COUNT"].sum())
        median_closed = (pd.to_numeric(closed["THROUGHPUT_DAYS"], errors="coerce").median()
                         if len(closed) else float("nan"))
        median_text = f"{median_closed:.0f} روز" if pd.notna(median_closed) else "N/A (شاهد کافی برای پرونده بسته نداریم)"
        log.info(
            f"🔄 لاگ رویداد: {len(events)} رویداد یکتا در {len(cases)} پرونده "
            f"({dup} ردیف تکراری منبع ادغام شد) · {cases['VARIANT'].nunique()} مسیر متمایز · "
            f"میانه چرخه پرونده‌های بسته {median_text}."
        )
        return df

    # ── ساخت رویدادها ──
    @staticmethod
    def _case_keys(df: pd.DataFrame):
        """کلید پرونده + **مبنایی که از آن آمده**.

        نسخه قبلی در نبود شماره سفارش به بارنامه و سپس ثبت سفارش می‌افتاد،
        بی‌آنکه جایی ثبت شود. نتیجه این بود که واحد تحلیل بین پرونده‌ها یکسان
        نبود و کسی نمی‌فهمید: «طول چرخه» یک ردیف، چرخهٔ سفارش است یا چرخهٔ
        یک محموله.

        سقوط به کلید بعدی همچنان انجام می‌شود — بدون آن، پرونده‌های بدون
        شماره سفارش کلاً از تحلیل بیرون می‌افتادند — ولی حالا مبنا در ستون
        ``CASE_KEY_BASIS`` اعلام می‌گردد و در خروجی دیده می‌شود.
        """
        order = ("CANONICAL_ORDER", "CANONICAL_BL", "CANONICAL_REG")
        keys = pd.Series("", index=df.index, dtype=object)
        basis = pd.Series("", index=df.index, dtype=object)
        for col in order:
            if col not in df.columns:
                continue
            v = df[col].astype(str).str.strip()
            ok = (keys == "") & v.ne("") & ~df[col].map(is_empty_val)
            keys = keys.mask(ok, v)
            basis = basis.mask(ok, col)
        return keys, basis

    def _build_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """رویدادهای یکتا در سطح (پرونده، فعالیت، تاریخ).

        «تکرار رکورد» با «تکرار فعالیت» یکی نیست. ده ردیف کالا زیر یک سفارش،
        ده بار «ابلاغ سفارش» نیستند؛ یک ابلاغ‌اند که ده ردیف آن را حمل
        می‌کنند. ``SOURCE_ROWS`` همان ده را نگه می‌دارد تا شفاف بماند.
        """
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

        # ── یکتاسازی: کلید طبیعی یک رویداد ──
        key = ["_CASE_KEY", "ACTIVITY_EN", "EVENTTIME"]
        ev["SOURCE_ROWS"] = ev.groupby(key)["_SORTING"].transform("size")
        ev = ev.drop_duplicates(subset=key, keep="first")

        ev = ev.sort_values(["_CASE_KEY", "EVENTTIME", "_SORTING"],
                            kind="mergesort").reset_index(drop=True)
        # شناسه پایدار رویداد — برای ارجاع، ممیزی و رهگیری تغییر
        ev.insert(0, "EVENT_ID",
                  ev["_CASE_KEY"].astype(str) + "|" + ev["ACTIVITY_EN"].astype(str)
                  + "|" + ev["EVENTTIME"].dt.strftime("%Y-%m-%d"))
        # ترتیب درون‌روز اثبات‌شده نیست: تاریخ داریم، ساعت نداریم.
        ev["ORDER_CERTAIN"] = (
            ev.groupby(["_CASE_KEY", "EVENTTIME"])["EVENT_ID"].transform("size") == 1)
        return ev

    # ── جدول پرونده ──
    @staticmethod
    def _build_case_table(ev: pd.DataFrame, today) -> pd.DataFrame:
        """یک ردیف برای هر پرونده — با سه زمان که عمداً از هم جدا شده‌اند.

        ``THROUGHPUT_DAYS`` فقط برای پرونده **بسته** معنا دارد: از نخستین تا
        آخرین رویداد. برای پرونده باز، این عدد «طول چرخه» نیست، «تا اینجا
        چقدر طول کشیده» است — و اگر با هم جمع شوند، میانگین چرخه به‌صورت
        مصنوعی کوتاه می‌شود، چون پرونده‌های کند هنوز تمام نشده‌اند و در
        مخرج می‌آیند ولی زمان کاملشان در صورت نیست.

        پس سه ستون جدا:
            THROUGHPUT_DAYS    زمان چرخه — فقط پرونده بسته
            CASE_AGE_DAYS      عمر پرونده — از نخستین رویداد تا امروز
            CURRENT_WAIT_DAYS  انتظار جاری — از آخرین رویداد تا امروز
        """
        now = pd.Timestamp(today)
        g = ev.groupby("_CASE_KEY", sort=False)
        last_act = g["ACTIVITY_EN"].last()
        out = pd.DataFrame({
            "CASE_KEY": list(g.groups.keys()),
            "FIRST_EVENT": g["EVENTTIME"].min().values,
            "LAST_EVENT": g["EVENTTIME"].max().values,
            "EVENT_COUNT": g.size().values,
            "SOURCE_ROWS": g["SOURCE_ROWS"].sum().values,
            "VARIANT": g["ACTIVITY_FA"].apply(lambda s: " ← ".join(s)).values,
            "FIRST_ACTIVITY": g["ACTIVITY_FA"].first().values,
            "LAST_ACTIVITY": g["ACTIVITY_FA"].last().values,
            "LAST_ACTIVITY_EN": last_act.values,
            "ORDER_CERTAIN": g["ORDER_CERTAIN"].all().values,
        })
        closed = out["LAST_ACTIVITY_EN"].isin(TERMINAL_ACTIVITIES)
        span = (out["LAST_EVENT"] - out["FIRST_EVENT"]).dt.days.astype(float)
        out["CASE_STATE"] = np.where(closed, "CLOSED", "OPEN")
        out["THROUGHPUT_DAYS"] = span.where(closed)
        out["CASE_AGE_DAYS"] = (now - out["FIRST_EVENT"]).dt.days.astype(float).where(~closed)
        out["CURRENT_WAIT_DAYS"] = (now - out["LAST_EVENT"]).dt.days.astype(float).where(~closed)

        # دوباره‌کاری واقعی: همان فعالیت در **تاریخ دیگر**. پس از یکتاسازی،
        # تکرارِ باقی‌مانده یعنی فعالیت دوباره اجرا شده، نه رکورد تکراری.
        out["REWORK_COUNT"] = g["ACTIVITY_EN"].apply(
            lambda s: int(len(s) - s.nunique())).values

        # تکمیل فرآیند = نقاط کنترل **متمایزِ** رسیده ÷ کل نقاط کنترل.
        # چون رویدادها یکتا شده‌اند، از ۱۰۰ رد نمی‌کند.
        reached = g["ACTIVITY_EN"].nunique().values
        out["PROCESS_COMPLETENESS"] = (
            np.minimum(reached / len(ACTIVITIES), 1.0) * 100).round(1)
        return out

    @staticmethod
    def _stage_queue(cases: pd.DataFrame) -> pd.DataFrame:
        """صف جاری: چند پرونده همین حالا در هر مرحله منتظرند و چقدر.

        این چیزی است که جدول گلوگاهِ مبتنی بر گذار **هرگز** نشان نمی‌داد:
        گذار وقتی ثبت می‌شود که پرونده از مرحله خارج شده باشد. پرونده‌ای که
        هشت ماه در «تخصیص ارز» گیر کرده و هنوز خارج نشده، در آن جدول هیچ
        ردیفی ندارد — یعنی بدترین گلوگاه دقیقاً همانی است که دیده نمی‌شد.
        """
        openc = cases[cases["CASE_STATE"] == "OPEN"]
        if openc.empty:
            return pd.DataFrame(columns=["مرحله جاری", "تعداد پرونده",
                                         "میانه انتظار (روز)", "بیشترین انتظار (روز)"])
        q = (openc.groupby("LAST_ACTIVITY", as_index=False)
                  .agg(**{"تعداد پرونده": ("CASE_KEY", "size"),
                          "میانه انتظار (روز)": ("CURRENT_WAIT_DAYS", "median"),
                          "بیشترین انتظار (روز)": ("CURRENT_WAIT_DAYS", "max")}))
        q = q.rename(columns={"LAST_ACTIVITY": "مرحله جاری"})
        for c in ("میانه انتظار (روز)", "بیشترین انتظار (روز)"):
            q[c] = q[c].round(0)
        return q.sort_values("تعداد پرونده", ascending=False).reset_index(drop=True)

    # ── گلوگاه: میانه و صدک ۹۰ گذارها، به‌اضافه صف جاری ──
    @staticmethod
    def _bottlenecks(ev: pd.DataFrame, cases: pd.DataFrame) -> pd.DataFrame:
        """گذارهای مشاهده‌شده با میانه، صدک ۹۰ و شمار **پرونده**.

        سه تغییر نسبت به نسخه قبلی:

        ۱) میانه به‌جای میانگین. توزیع مدت در این فرآیند دُم‌دار است؛ یک
           پرونده ۴۰۰ روزه میانگین را جابه‌جا می‌کند و گلوگاه کاذب می‌سازد.
        ۲) صدک ۹۰ هم می‌آید، چون تصمیم عملیاتی با «بدترین حالت معقول» گرفته
           می‌شود، نه با وسط توزیع.
        ۳) گذار «به خودش» حذف می‌شود. پس از یکتاسازی دیگر ساخته نمی‌شود، ولی
           فیلترش می‌ماند تا اگر روزی داده ساعت‌دار آمد، خطا برنگردد.
        """
        cols = ["از فعالیت", "به فعالیت", "میانه روز", "صدک ۹۰ روز",
                "بیشینه روز", "تعداد پرونده"]
        rows = []
        for case, g in ev.groupby("_CASE_KEY", sort=False):
            g = g.reset_index(drop=True)
            for i in range(len(g) - 1):
                a, b = g.loc[i, "ACTIVITY_FA"], g.loc[i + 1, "ACTIVITY_FA"]
                if a == b:
                    continue
                rows.append({"_CASE_KEY": case, "از فعالیت": a, "به فعالیت": b,
                             "روز": (g.loc[i + 1, "EVENTTIME"] - g.loc[i, "EVENTTIME"]).days})
        if not rows:
            return pd.DataFrame(columns=cols)
        t = pd.DataFrame(rows)
        out = (t.groupby(["از فعالیت", "به فعالیت"], as_index=False)
                 .agg(**{"میانه روز": ("روز", "median"),
                         "صدک ۹۰ روز": ("روز", lambda s: float(np.percentile(s, 90))),
                         "بیشینه روز": ("روز", "max"),
                         "تعداد پرونده": ("_CASE_KEY", "nunique")}))
        for c in ("میانه روز", "صدک ۹۰ روز"):
            out[c] = out[c].round(1)
        return out.sort_values("میانه روز", ascending=False).reset_index(drop=True)

    @staticmethod
    def _variants(cases: pd.DataFrame) -> pd.DataFrame:
        """مسیرهای مشاهده‌شده، با میانه و شمار پرونده‌های **بسته**.

        «واریانت بیشتر = فرآیند بدتر» نتیجه‌گیری غلطی است که نسخه قبلی در
        متن گزارش می‌گذاشت. تنوع مسیر می‌تواند سه علت کاملاً متفاوت داشته
        باشد: تفاوت مشروع خریدها (هوایی/دریایی، برات/دیداری)، نقص داده، یا
        بی‌انضباطی واقعی. تفکیک این سه کار خواننده است، نه گزارش — پس
        گزارش عدد می‌دهد و ستون «پرونده بسته» را کنارش می‌گذارد تا معلوم
        باشد میانه بر چند نمونه بنا شده است.
        """
        out = (cases.groupby("VARIANT", as_index=False)
                    .agg(**{"تعداد پرونده": ("CASE_KEY", "size"),
                            "پرونده بسته": ("THROUGHPUT_DAYS", "count"),
                            "میانه چرخه": ("THROUGHPUT_DAYS", "median")}))
        out["میانه چرخه"] = out["میانه چرخه"].round(1)
        total = out["تعداد پرونده"].sum() or 1
        out["سهم (٪)"] = (out["تعداد پرونده"] / total * 100).round(1)
        return out.sort_values("تعداد پرونده", ascending=False).reset_index(drop=True)

    # ── خروجی CSV برای بارگذاری مستقیم در Celonis ──
    @staticmethod
    def _export_csv(events: pd.DataFrame, cases: pd.DataFrame) -> None:
        try:
            os.makedirs(SETTINGS.OUTPUT_DIR, exist_ok=True)
            ev_path = os.path.join(SETTINGS.OUTPUT_DIR, "GSI_EventLog.csv")
            ca_path = os.path.join(SETTINGS.OUTPUT_DIR, "GSI_CaseTable.csv")
            events.to_csv(ev_path, index=False, encoding="utf-8-sig")
            cases.to_csv(ca_path, index=False, encoding="utf-8-sig")
            log.info(f"📤 جدول فعالیت و جدول پرونده برای Celonis ذخیره شد: {ev_path}")
        except Exception as ex:
            log.warning(f"⚠️ [eventlog] ذخیره CSV ناموفق: {ex}")

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("CASE_STATE", "وضعیت پرونده", 14, GROUP_ANALYTIC, order=89),
            ColumnSpec("THROUGHPUT_DAYS", "زمان چرخه — پرونده بسته (روز)", 20,
                       GROUP_ANALYTIC, fmt="decimal", order=90,
                       color_rule="scale_high_bad"),
            ColumnSpec("CURRENT_WAIT_DAYS", "انتظار جاری (روز)", 16, GROUP_ANALYTIC,
                       fmt="decimal", order=91, color_rule="scale_high_bad"),
            ColumnSpec("CASE_AGE_DAYS", "عمر پرونده باز (روز)", 17, GROUP_ANALYTIC,
                       fmt="decimal", order=92),
            ColumnSpec("EVENT_COUNT", "رویداد یکتا", 12, GROUP_ANALYTIC,
                       fmt="int", order=93),
            ColumnSpec("REWORK_COUNT", "تکرار واقعی فعالیت", 16, GROUP_ANALYTIC,
                       fmt="int", order=94),
            ColumnSpec("PROCESS_COMPLETENESS", "نقاط کنترل طی‌شده (٪)", 18,
                       GROUP_ANALYTIC, fmt="decimal", order=95),
            ColumnSpec("VARIANT", "مسیر طی‌شده", 70, GROUP_ANALYTIC,
                       wrap=True, order=96),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        cases = ctx.extras.get("case_table")
        if cases is None or cases.empty:
            return {}
        closed = cases[cases["CASE_STATE"] == "CLOSED"]
        openc = cases[cases["CASE_STATE"] == "OPEN"]

        q = ctx.extras.get("stage_queue")
        worst_q = ""
        if q is not None and not q.empty:
            top = q.iloc[0]
            worst_q = (f"{top['مرحله جاری']} — {int(top['تعداد پرونده'])} پرونده، "
                       f"میانه {top['میانه انتظار (روز)']:.0f} روز")

        out: Dict[str, tuple] = {}
        if len(closed):
            out["میانه زمان چرخه (روز)"] = (
                round(float(closed["THROUGHPUT_DAYS"].median()), 1),
                f"فقط {len(closed)} پرونده بسته — میانه، چون توزیع دُم‌دار است")
        if len(openc):
            out["بیشترین انتظار جاری (روز)"] = (
                round(float(openc["CURRENT_WAIT_DAYS"].max()), 0),
                "پرونده‌ای که بیشترین مدت بدون رویداد مانده است")
        if worst_q:
            out["بزرگ‌ترین صف فعلی"] = (worst_q, "کجا بیشترین پرونده منتظر است")
        return out

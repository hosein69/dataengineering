# -*- coding: utf-8 -*-
"""مرحله ۹۶ — ناهنجاری‌ها را پیدا کن و پیش از هر کاری، علتشان را بپرس.

داده پرت خبرچین مجانی است. این مرحله هیچ ردیفی را حذف، صاف یا اصلاح نمی‌کند؛
برای هر ناهنجاری یک جمله می‌گوید چه چیزی عجیب است، فرضیه‌های محتمل را **با
شاهد از خود داده** می‌سنجد، و اگر یکی از فرضیه‌ها اصلاح مشخصی را ایجاب کند،
آن را فقط **پیشنهاد** می‌کند. اعمالش با تأیید انسانی و در مرحله ۲۱ اجرای بعد
است (``gsi/trust/inquiry.py``).

چرا بعد از ۹۵: مقایسه با اجراهای قبل به «عکس اعتماد» همین اجرا تکیه دارد. این
مرحله اثر انگشت فشرده اجرا (حجم هر سورس، پوشش هر فیلد، واژگان هر فیلد
دسته‌ای) را به همان عکس اضافه می‌کند تا اجرای بعد بتواند «افت ناگهانی» و
«بیش از حد خوب» را تشخیص دهد.

tolerant است: شکست این مرحله نباید انتشار یک اجرای سالم را متوقف کند.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ..dataio.logging_setup import log
from ..trust import trend
from ..trust.anomaly import detect, observe
from ..trust.inquiry import headline_fa, inquiries_frame, summarize
from .base import PipelineContext, Stage, register
from .s21_heal import register_for

#: Anomalies kept in the stored snapshot (the command-line register reads them).
_SNAPSHOT_ANOMALIES = 100


@register
class AnomalyInquiryStage(Stage):
    name = "anomaly_inquiry"
    title = "ناهنجاری‌ها: پیش از حذف یا اصلاح، علت را بپرس"
    order = 96
    tolerant = True
    requires: List[str] = []
    provides: List[str] = []

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        observations = observe(df, sources=ctx.sources)
        history = ctx.extras.get("anomaly_history")
        if history is None:
            history = trend.load_payloads(limit=12)
        anomalies = detect(df, history=history, observations=observations)

        frame = inquiries_frame(anomalies, register_for(ctx), ctx.today)
        summary = summarize(frame)
        applied = ctx.extras.get("heal_applied")
        n_applied = len(applied) if isinstance(applied, pd.DataFrame) else 0
        ctx.extras["anomaly_inquiries"] = frame
        ctx.extras["anomaly_summary"] = summary
        ctx.extras["anomaly_headline"] = headline_fa(summary, n_applied)

        trust_summary = ctx.extras.get("trust_summary")
        if isinstance(trust_summary, dict):
            trust_summary["observations"] = observations
            trust_summary["anomaly_counts"] = summary
            trust_summary["anomalies"] = [a.as_dict() for a in anomalies[:_SNAPSHOT_ANOMALIES]]

        log.info(f"🕵️ [anomaly] {summary['total']} ناهنجاری | "
                 f"{summary['needs_answer']} منتظر پاسخ | {n_applied} ترمیم تأییدشده اعمال شد")
        return df

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        summary = ctx.extras.get("anomaly_summary") or {}
        if not summary.get("total"):
            return {}
        return {"ناهنجاری منتظر پاسخ": (
            int(summary.get("needs_answer", 0)),
            "هیچ‌کدام حذف نشده؛ پیش از هر اصلاحی علتش پرسیده می‌شود")}

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {"ناهنجاری‌ها": {
            "عدد پرت": "روی لگاریتم مقدار، در دانه موجودیت و درون گروه هم‌ارز: "
                       "z اصلاح‌شده (میانه/MAD) بیش از ۳٫۵ و دست‌کم ۳ برابر فاصله از میانه.",
            "فرضیه‌ها": "خطای واحد/ممیز (جابه‌جایی دقیق ۱ تا ۶ رقم)، ارز/گروه اشتباه، "
                        "ورودی محاسبه، یا واقعی — هر کدام با شاهد از داده.",
            "افت حجم": "کمتر از ۸۰٪ میانه ۶ اجرای قبل؛ تکرار منظمش نشانه مشکل ثبت است نه بازار.",
            "بیش از حد خوب": "جمع ۱٫۶ برابر یا پوشش ۳۰ واحد بیشتر در یک اجرا؛ اول دوباره‌شماری "
                             "و پرشدن با مقدار پیش‌فرض رد می‌شود.",
            "حذف": "هیچ. «نمی‌دانیم» پاسخ مجاز است ولی حداکثر ۳۰ روز.",
        }}

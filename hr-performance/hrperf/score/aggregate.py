# -*- coding: utf-8 -*-
"""تجمیع دو سطحی: آیتم → کلاستر → عملکرد.

هر سطح جداگانه روی **شاخص‌های موجود** بازنرمال می‌شود، پس نبودِ یک شاخص
باعث نمی‌شود امتیاز فرد بی‌صدا پایین بیاید؛ در عوض «پوشش» او پایین
گزارش می‌شود و خواننده می‌داند امتیاز روی چه سهمی از مدل ساخته شده است.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config.model import PerformanceModel


@dataclass
class ScoreResult:
    metric_scores: pd.DataFrame      # person × metric
    cluster_scores: pd.DataFrame     # person × cluster
    performance: pd.Series           # person → 0..100
    coverage: pd.Series              # person → 0..1 سهم وزنی موجود
    evidence: pd.Series              # person → 0..1 کیفیت شواهد
    confidence: pd.Series            # person → 0..1 = sqrt(coverage × evidence)
    cluster_coverage: pd.DataFrame


def _weighted(scores: pd.DataFrame, weights: Dict[str, float]) -> tuple:
    """میانگین وزنی روی ستون‌های موجود + سهم وزنی پوشش‌داده‌شده."""
    cols = [c for c in weights if c in scores.columns]
    if not cols:
        idx = scores.index
        return pd.Series(np.nan, index=idx), pd.Series(0.0, index=idx)
    w = pd.Series({c: weights[c] for c in cols}, dtype=float)
    sub = scores[cols]
    present = sub.notna().astype(float)
    avail = present.mul(w, axis=1).sum(axis=1)
    total = float(w.sum())
    num = sub.mul(w, axis=1).sum(axis=1, min_count=1)
    val = num / avail.replace(0.0, np.nan)
    return val, (avail / total if total > 0 else avail * 0.0)


def aggregate(metric_scores: pd.DataFrame, model: PerformanceModel,
              evidence: Optional[pd.DataFrame] = None) -> ScoreResult:
    """امتیاز نهایی از امتیازهای شاخصی."""
    idx = metric_scores.index
    cluster_scores = pd.DataFrame(index=idx)
    cluster_cov = pd.DataFrame(index=idx)

    for ck, cl in model.clusters.items():
        if not cl.scored:
            continue
        items = {m.key: m.weight for m in model.cluster_metrics(ck)}
        val, cov = _weighted(metric_scores, items)
        cluster_scores[ck] = val
        cluster_cov[ck] = cov

    cw = {k: c.weight for k, c in model.clusters.items()
          if c.scored and k in cluster_scores.columns}
    performance, _cluster_present = _weighted(cluster_scores, cw)

    # پوشش کل باید **پوشش درون کلاستر** را هم منتقل کند. اگر فقط حضورِ
    # نمرهٔ کلاستر را بشماریم، کسی که دو سوم شاخص‌های کیفیت را ندارد باز
    # «پوشش ۱۰۰٪» می‌گیرد و کمبود داده پنهان می‌ماند.
    if cw and not cluster_cov.empty:
        wser = pd.Series(cw, dtype=float)
        cols = [c for c in wser.index if c in cluster_cov.columns]
        if cols:
            w = wser[cols]
            coverage = (cluster_cov[cols].fillna(0.0).mul(w, axis=1).sum(axis=1)
                        / float(w.sum()))
        else:
            coverage = _cluster_present
    else:
        coverage = _cluster_present

    # ── کیفیت شواهد: میانگین وزنی evidence شاخص‌ها با وزن مؤثر ──
    if evidence is not None and not evidence.empty:
        eff = {m.key: model.effective_weight(m.key) for m in model.scored_metrics}
        eff = {k: v for k, v in eff.items() if v > 0 and k in evidence.columns}
        ev, _ = _weighted(evidence.reindex(columns=list(eff)), eff)
        ev = ev.reindex(idx)
    else:
        ev = pd.Series(np.nan, index=idx, dtype=float)

    conf = np.sqrt(coverage.clip(0, 1) * ev.fillna(0.0).clip(0, 1))
    return ScoreResult(metric_scores, cluster_scores, performance,
                       coverage, ev, conf, cluster_cov)


def contribution(metric_scores: pd.DataFrame, model: PerformanceModel,
                 person: str) -> pd.DataFrame:
    """سهم هر شاخص در امتیاز یک نفر — برای پاسخ به «چرا این عدد؟».

    سهم = وزن مؤثر × (امتیاز − ۵۰). عدد مثبت یعنی این شاخص فرد را بالای
    میانه برده، منفی یعنی پایین کشیده.
    """
    if person not in metric_scores.index:
        return pd.DataFrame()
    row = metric_scores.loc[person]
    rows = []
    for m in model.scored_metrics:
        if m.key not in row.index or pd.isna(row[m.key]):
            continue
        eff = model.effective_weight(m.key)
        rows.append({
            "شاخص": m.label, "کلید": m.key,
            "کلاستر": model.clusters[m.cluster].label,
            "امتیاز": round(float(row[m.key]), 1),
            "وزن مؤثر (٪)": round(eff * 100, 2),
            "سهم": round(eff * (float(row[m.key]) - 50.0), 2),
        })
    out = pd.DataFrame(rows)
    return out.sort_values("سهم", key=abs, ascending=False) if not out.empty else out

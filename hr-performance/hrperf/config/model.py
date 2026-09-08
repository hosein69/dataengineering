# -*- coding: utf-8 -*-
"""بارگذاری و اعتبارسنجی مدل دو سطحی."""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .settings import SETTINGS

MODEL_BASENAME = "model.yaml"


@dataclass(frozen=True)
class Cluster:
    key: str
    label: str
    weight: float
    scored: bool = True
    rationale: str = ""


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    cluster: str
    weight: float
    direction: str          # higher | lower
    kind: str               # quality_rate | duration | ratio | count | money
    entry: str              # direct | derived
    role: str               # scored | context | driver
    source: str = ""
    q_target: Optional[float] = None
    is_driver: bool = False
    formula: str = ""
    note: str = ""

    @property
    def scored(self) -> bool:
        return self.role == "scored"


class ModelError(ValueError):
    """مدل از نظر ساختاری معتبر نیست."""


@dataclass
class PerformanceModel:
    clusters: Dict[str, Cluster] = field(default_factory=dict)
    metrics: Dict[str, Metric] = field(default_factory=dict)
    model_version: str = ""

    # ── دسترسی ──
    def cluster_metrics(self, cluster: str, scored_only: bool = True) -> List[Metric]:
        return [m for m in self.metrics.values()
                if m.cluster == cluster and (m.scored or not scored_only)]

    @property
    def scored_metrics(self) -> List[Metric]:
        return [m for m in self.metrics.values() if m.scored]

    @property
    def drivers(self) -> List[Metric]:
        """شاخص‌هایی که «شرایط کار» را توصیف می‌کنند و در لایه علّی
        به‌عنوان تعدیل‌گر (confounder) استفاده می‌شوند."""
        return [m for m in self.metrics.values() if m.is_driver]

    def effective_weight(self, metric_key: str) -> float:
        """وزن مؤثر یک شاخص در امتیاز نهایی = وزن آیتم × وزن کلاسترش."""
        m = self.metrics.get(metric_key)
        if m is None or not m.scored:
            return 0.0
        c = self.clusters.get(m.cluster)
        if c is None or not c.scored:
            return 0.0
        return m.weight * c.weight

    # ── اعتبارسنجی ──
    def validate(self) -> List[str]:
        """فهرست ایرادها؛ خالی یعنی سالم."""
        issues: List[str] = []
        cw = sum(c.weight for c in self.clusters.values() if c.scored)
        if abs(cw - 1.0) > 1e-6:
            issues.append(f"مجموع وزن کلاسترهای امتیازی {cw:.6f} است، نه ۱.")
        for ck, c in self.clusters.items():
            if not c.scored:
                continue
            items = self.cluster_metrics(ck)
            if not items:
                issues.append(f"کلاستر «{c.label}» هیچ شاخص امتیازی ندارد.")
                continue
            s = sum(m.weight for m in items)
            if abs(s - 1.0) > 1e-6:
                issues.append(
                    f"مجموع وزن آیتم‌های کلاستر «{c.label}» {s:.6f} است، نه ۱.")
        for mk, m in self.metrics.items():
            if m.cluster not in self.clusters:
                issues.append(f"شاخص «{mk}» به کلاستر ناشناخته «{m.cluster}» ارجاع دارد.")
            if m.direction not in ("higher", "lower"):
                issues.append(f"جهت شاخص «{mk}» نامعتبر است: {m.direction}")
            if m.entry not in ("direct", "derived"):
                issues.append(f"نوع ورود شاخص «{mk}» نامعتبر است: {m.entry}")
        return issues

    def renormalize(self) -> "PerformanceModel":
        """وزن‌ها را به ۱ برمی‌گرداند — پس از ویرایش کاربر در داشبورد.

        بدون این، کاربر یک اسلایدر را جابه‌جا می‌کرد و مجموع از ۱ خارج
        می‌شد و امتیاز بی‌صدا مقیاسش عوض می‌شد.
        """
        cw = sum(c.weight for c in self.clusters.values() if c.scored)
        clusters = {}
        for k, c in self.clusters.items():
            w = (c.weight / cw) if (c.scored and cw > 0) else 0.0
            clusters[k] = Cluster(c.key, c.label, w, c.scored, c.rationale)
        metrics = dict(self.metrics)
        for ck in clusters:
            items = [m for m in metrics.values() if m.cluster == ck and m.scored]
            s = sum(m.weight for m in items)
            if s <= 0:
                continue
            for m in items:
                metrics[m.key] = Metric(**{**m.__dict__, "weight": m.weight / s})
        return PerformanceModel(clusters, metrics, self.model_version)


def load_model(path: str | Path | None = None) -> PerformanceModel:
    p = Path(path) if path else (SETTINGS.rules_dir / MODEL_BASENAME)
    if not p.exists():
        p = Path(__file__).resolve().parent / MODEL_BASENAME
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    clusters = {}
    for k, c in (raw.get("clusters") or {}).items():
        clusters[k] = Cluster(
            key=k, label=c.get("label", k), weight=float(c.get("weight", 0.0)),
            scored=bool(c.get("scored", True)), rationale=c.get("rationale", ""))

    metrics = {}
    for k, m in (raw.get("metrics") or {}).items():
        metrics[k] = Metric(
            key=k, label=m.get("label", k), cluster=m.get("cluster", ""),
            weight=float(m.get("weight", 0.0)),
            direction=m.get("direction", "higher"), kind=m.get("kind", "ratio"),
            entry=m.get("entry", "direct"), role=m.get("role", "scored"),
            source=m.get("source", ""),
            q_target=(float(m["q_target"]) if m.get("q_target") is not None else None),
            is_driver=bool(m.get("is_driver", False)),
            formula=m.get("formula", ""), note=m.get("note", ""))

    model = PerformanceModel(clusters, metrics, str(raw.get("model_version", "")))
    problems = model.validate()
    if problems:
        raise ModelError("مدل معتبر نیست:\n  - " + "\n  - ".join(problems))
    return model

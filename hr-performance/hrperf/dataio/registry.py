# -*- coding: utf-8 -*-
"""دفترچه سورس‌ها — سورس تازه، بدون تغییر کد.

## چرا این لایه لازم بود

افزودن یک سورس تازه تا امروز یعنی نوشتن یک reader در پایتون. یعنی هر
واحدی که فایل تازه‌ای می‌دهد، باید منتظر توسعه‌دهنده بماند — و در عمل
سورس هرگز اضافه نمی‌شود. مدلی که با واقعیت سازمان جلو نمی‌آید، به‌مرور
به ابزار توجیه تبدیل می‌شود نه سنجش.

حالا یک ورودی در ``sources.yaml`` کافی است:

```yaml
custom:
  bazresi:
    label: خروجی واحد بازرسی
    match: "*بازرسی*"
    person_key: کد پرسنلی
    metrics:
      نرخ تطابق: {metric: conformance_score, sample: تعداد پرونده}
```

## سه محافظ

* **شاخص ناشناخته رد می‌شود.** نگاشت به شاخصی که در `model.yaml` نیست،
  خطای صریح می‌دهد؛ وگرنه ستونی خوانده می‌شد که هیچ‌جا امتیاز نمی‌گیرد
  و کسی نمی‌فهمید چرا.
* **ستون نبود ⇒ سکوت نمی‌کنیم.** نامش در گزارش اجرا می‌آید.
* **مقدار غیرعددی صفر نمی‌شود.** کنار گذاشته می‌شود و شمرده می‌شود.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yaml

from ..identity import keys as keymod

BASENAME = "sources.yaml"


@dataclass
class MetricMap:
    column: str
    metric: str
    sample: str = ""
    scale: float = 1.0


@dataclass
class SourceSpec:
    key: str
    label: str
    match: str = "*"
    person_key: str = "person_key"
    person_name: str = ""
    metrics: List[MetricMap] = field(default_factory=list)
    note: str = ""

    def accepts(self, filename: str) -> bool:
        return fnmatch(str(filename), self.match)


class RegistryError(ValueError):
    """دفترچه سورس‌ها معتبر نیست."""


def path(explicit: Optional[Path] = None) -> Path:
    if explicit:
        return Path(explicit)
    from ..config.settings import SETTINGS
    p = SETTINGS.rules_dir / BASENAME
    return p if p.exists() else Path(__file__).resolve().parents[1] / "config" / BASENAME


def load(explicit: Optional[Path] = None) -> Dict[str, SourceSpec]:
    """سورس‌های تعریف‌شدهٔ کاربر (بخش ``custom``)."""
    p = path(explicit)
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: Dict[str, SourceSpec] = {}
    for key, cfg in (raw.get("custom") or {}).items():
        cfg = cfg or {}
        mm = []
        for col, spec in (cfg.get("metrics") or {}).items():
            spec = spec if isinstance(spec, dict) else {"metric": spec}
            mm.append(MetricMap(column=str(col), metric=str(spec.get("metric", "")),
                                sample=str(spec.get("sample", "") or ""),
                                scale=float(spec.get("scale", 1.0))))
        out[key] = SourceSpec(
            key=key, label=str(cfg.get("label", key)),
            match=str(cfg.get("match", "*")),
            person_key=str(cfg.get("person_key", "person_key")),
            person_name=str(cfg.get("person_name", "") or ""),
            metrics=mm, note=str(cfg.get("note", "") or ""))
    return out


def validate(specs: Dict[str, SourceSpec], model) -> List[str]:
    """ایرادها؛ خالی یعنی سالم."""
    issues: List[str] = []
    for key, sp in specs.items():
        if not sp.metrics:
            issues.append(f"سورس «{key}» هیچ نگاشت شاخصی ندارد.")
        for mm in sp.metrics:
            if mm.metric not in model.metrics:
                issues.append(
                    f"سورس «{key}»: ستون «{mm.column}» به شاخص ناشناخته "
                    f"«{mm.metric}» نگاشت شده. اول شاخص را در مدل بسازید.")
    return issues


def save(specs: Dict[str, SourceSpec], explicit: Optional[Path] = None) -> Path:
    """دفترچه را می‌نویسد و بخش داخلی را دست‌نخورده نگه می‌دارد."""
    p = path(explicit)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    raw = raw or {}
    raw["custom"] = {
        k: {"label": s.label, "match": s.match, "person_key": s.person_key,
            **({"person_name": s.person_name} if s.person_name else {}),
            **({"note": s.note} if s.note else {}),
            "metrics": {m.column: {"metric": m.metric,
                                   **({"sample": m.sample} if m.sample else {}),
                                   **({"scale": m.scale} if m.scale != 1.0 else {})}
                        for m in s.metrics}}
        for k, s in specs.items()}
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False,
                                  default_flow_style=False, width=88),
                   encoding="utf-8")
    tmp.replace(p)
    return p


def read(df: pd.DataFrame, spec: SourceSpec) -> Tuple[pd.DataFrame, List[str]]:
    """یک جدول را طبق نگاشت سورس، به قالب بلند تبدیل می‌کند."""
    notes: List[str] = []
    if spec.person_key not in df.columns:
        return (pd.DataFrame(), [f"سورس «{spec.label}»: ستون کلید فرد "
                                 f"«{spec.person_key}» نبود؛ فایل رد شد."])
    key = df[spec.person_key]
    rows = []
    for mm in spec.metrics:
        if mm.column not in df.columns:
            notes.append(f"سورس «{spec.label}»: ستون «{mm.column}» نبود؛ "
                         f"شاخص «{mm.metric}» ساخته نشد.")
            continue
        val = pd.to_numeric(df[mm.column], errors="coerce") * mm.scale
        bad = int(df[mm.column].notna().sum() - val.notna().sum())
        if bad:
            notes.append(f"سورس «{spec.label}»: {bad} مقدار «{mm.column}» عدد "
                         f"نبود و کنار گذاشته شد (صفر نشد).")
        smp = (pd.to_numeric(df[mm.sample], errors="coerce")
               if mm.sample and mm.sample in df.columns else None)
        rows.append(pd.DataFrame({
            "person_key": key.map(keymod.clean_person_key),
            "person_code": key.map(keymod.clean_text),
            "metric_key": mm.metric, "value": val,
            "sample_n": smp if smp is not None else float("nan"),
            "source": spec.key, "scope": "ANY"}))
    if not rows:
        return pd.DataFrame(), notes
    out = pd.concat(rows, ignore_index=True).dropna(subset=["value"])
    return out[out["person_key"].ne("")], notes

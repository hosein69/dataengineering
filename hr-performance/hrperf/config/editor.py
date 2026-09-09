# -*- coding: utf-8 -*-
"""ویرایش زندهٔ مدل — کلاستر تازه، شاخص تازه، وزن تازه.

## چرا مدل باید از داشبورد قابل تغییر باشد

مدل عملکرد یک قرارداد سازمانی است، نه یک ثابت مهندسی. وقتی تغییرش نیازمند
ویرایش فایل و اجرای مجدد باشد، در عمل هرگز تغییر نمی‌کند — و مدلی که با
واقعیت سازمان جلو نمی‌آید، به‌مرور به ابزار توجیه تبدیل می‌شود نه سنجش.

پس: افزودن کلاستر، افزودن شاخص و تغییر وزن باید از خودِ داشبورد ممکن
باشد، **ولی با سه محافظ**:

**۱) نسخه‌گذاری.** هر ذخیره، نسخه تازه‌ای می‌سازد و نسخه قبلی کنارش
می‌ماند. مقایسه دو دوره با دو مدل متفاوت، مقایسه نیست — و باید بشود
فهمید کدام عدد با کدام مدل ساخته شده.

**۲) اعتبارسنجی پیش از ذخیره.** وزن منفی، کلاستر بدون شاخص، شاخصی که به
کلاستر ناموجود ارجاع می‌دهد — هیچ‌کدام ذخیره نمی‌شوند.

**۳) دلیل اجباری.** هر کلاستر باید ``rationale`` داشته باشد. وزنی که
دلیلش نوشته نشده، فردا قابل دفاع نیست؛ و در سنجش آدم‌ها، وزنِ بی‌دلیل
همان اجحاف است.
"""
from __future__ import annotations

__contract__ = 1

import re
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from ..identity.scopes import ANY, BY_KEY
from .model import (MODEL_BASENAME, Cluster, Metric, ModelError,
                    PerformanceModel, load_model)
from .settings import SETTINGS

_KEY = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

#: شاخه‌های مجاز — همان‌هایی که موتور امتیاز می‌شناسد.
KINDS = ("quality_rate", "duration", "ratio", "count", "money")
DIRECTIONS = ("higher", "lower")
ROLES = ("scored", "context", "driver")
ENTRIES = ("direct", "derived")


class EditError(ValueError):
    """ویرایش نامعتبر — پیام، دقیقاً می‌گوید چه چیزی غلط است."""


def model_path() -> Path:
    p = SETTINGS.rules_dir / MODEL_BASENAME
    return p if p.exists() else Path(__file__).resolve().parent / MODEL_BASENAME


def _read_raw(path: Optional[Path] = None) -> dict:
    p = path or model_path()
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


#: حوزه‌های مجاز برای یک شاخص
_VALID_SCOPES = {ANY, *BY_KEY}


def to_dict(model: PerformanceModel) -> dict:
    """مدل ← ساختار YAML، با حفظ همه فیلدها."""
    return {
        "model_version": model.model_version,
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "clusters": {k: {"label": c.label, "weight": round(c.weight, 6),
                         "scored": c.scored, "rationale": c.rationale}
                     for k, c in model.clusters.items()},
        "metrics": {k: {kk: vv for kk, vv in asdict(m).items()
                        if kk != "key" and vv not in ("", None, False)}
                    for k, m in model.metrics.items()},
    }


# ═══════════ افزودن و تغییر ═══════════
def add_cluster(model: PerformanceModel, key: str, label: str, weight: float,
                rationale: str, scored: bool = True,
                renormalize: bool = True) -> PerformanceModel:
    """کلاستر تازه. کلید انگلیسی و یکتا، دلیل اجباری.

    ``renormalize`` پیش‌فرض روشن است: وزن کلاسترهای موجود **به نسبت**
    کوچک می‌شود تا مجموع دوباره ۱ شود. بدون آن، هر افزودنی با خطای
    «مجموع وزن‌ها ۱ نیست» رد می‌شد و قابلیت عملاً بی‌استفاده می‌ماند.

    این تغییر بی‌صدا نیست: ``diff()`` هر جابه‌جایی وزن را نشان می‌دهد و
    داشبورد آن را پیش از ذخیره به کاربر می‌گوید.
    """
    if not _KEY.match(key or ""):
        raise EditError("کلید کلاستر باید انگلیسی، با حرف کوچک شروع شود و "
                        "فقط حرف/عدد/زیرخط داشته باشد (مثل: `compliance`).")
    if key in model.clusters:
        raise EditError(f"کلاستر «{key}» از قبل هست.")
    if not str(label).strip():
        raise EditError("عنوان فارسی کلاستر لازم است.")
    if not str(rationale).strip():
        raise EditError("دلیل وزن اجباری است. وزنی که دلیلش نوشته نشده، "
                        "فردا در برابر کسی که با نتیجه مخالف است قابل دفاع نیست.")
    if not 0 <= float(weight) <= 1:
        raise EditError("وزن باید بین ۰ و ۱ باشد.")
    out = _clone(model)
    w = float(weight)
    if renormalize and scored and w < 1.0:
        room = 1.0 - w
        others = {k: c for k, c in out.clusters.items() if c.scored}
        total = sum(c.weight for c in others.values())
        if total > 0:
            for k, c in others.items():
                out.clusters[k] = Cluster(c.key, c.label,
                                          c.weight / total * room,
                                          c.scored, c.rationale)
    out.clusters[key] = Cluster(key=key, label=label.strip(), weight=w,
                                scored=scored, rationale=rationale.strip())
    return out


def add_metric(model: PerformanceModel, key: str, label: str, cluster: str,
               weight: float, direction: str = "higher", kind: str = "ratio",
               role: str = "scored", entry: str = "direct",
               source: str = "", note: str = "", citation: str = "",
               scope: str = ANY) -> PerformanceModel:
    """شاخص تازه داخل یک کلاستر موجود.

    ``citation`` برای شاخص امتیازی اجباری است — همان قاعده‌ای که برای
    ``rationale`` کلاستر برقرار است: عددی که دربارهٔ آدم‌ها تصمیم
    می‌گیرد و مبنایش نوشته نشده، فردا قابل دفاع نیست.

    ``scope`` تعیین می‌کند این شاخص برای چه حوزه‌ای معنا دارد؛ پیش‌فرض
    ``ANY`` یعنی مشترک میان همه.
    """
    if not _KEY.match(key or ""):
        raise EditError("کلید شاخص باید انگلیسی و یکتا باشد.")
    if role == "scored" and not str(citation).strip():
        raise EditError("شاخص امتیازی باید مبنای علمی (citation) داشته باشد.")
    if scope not in _VALID_SCOPES:
        raise EditError(f"حوزه نامعتبر: «{scope}». مجاز: "
                        + "، ".join(sorted(_VALID_SCOPES)))
    if key in model.metrics:
        raise EditError(f"شاخص «{key}» از قبل هست.")
    if cluster not in model.clusters:
        raise EditError(f"کلاستر «{cluster}» وجود ندارد؛ اول آن را بسازید.")
    for name, val, allowed in (("جهت", direction, DIRECTIONS), ("نوع", kind, KINDS),
                               ("نقش", role, ROLES), ("ورود", entry, ENTRIES)):
        if val not in allowed:
            raise EditError(f"{name} نامعتبر: «{val}». مجاز: {', '.join(allowed)}")
    if not 0 <= float(weight) <= 1:
        raise EditError("وزن باید بین ۰ و ۱ باشد.")
    out = _clone(model)
    w = float(weight)
    if role == "scored" and w < 1.0:
        sibs = {k: m for k, m in out.metrics.items()
                if m.cluster == cluster and m.role == "scored"}
        total = sum(m.weight for m in sibs.values())
        if total > 0:
            room = 1.0 - w
            for k, m in sibs.items():
                out.metrics[k] = Metric(**{**asdict(m),
                                           "weight": m.weight / total * room})
    out.metrics[key] = Metric(key=key, label=label.strip() or key, cluster=cluster,
                              weight=w, direction=direction, kind=kind,
                              entry=entry, role=role, source=source, note=note,
                              citation=citation, scope=scope)
    return out


def set_weights(model: PerformanceModel,
                clusters: Optional[Dict[str, float]] = None,
                metrics: Optional[Dict[str, float]] = None) -> PerformanceModel:
    """تغییر دسته‌جمعی وزن‌ها."""
    out = _clone(model)
    for k, w in (clusters or {}).items():
        if k not in out.clusters:
            raise EditError(f"کلاستر «{k}» وجود ندارد.")
        c = out.clusters[k]
        out.clusters[k] = Cluster(c.key, c.label, float(w), c.scored, c.rationale)
    for k, w in (metrics or {}).items():
        if k not in out.metrics:
            raise EditError(f"شاخص «{k}» وجود ندارد.")
        m = out.metrics[k]
        out.metrics[k] = Metric(**{**asdict(m), "weight": float(w)})
    return out


def remove_cluster(model: PerformanceModel, key: str) -> PerformanceModel:
    """حذف کلاستر — فقط وقتی هیچ شاخصی به آن وصل نیست."""
    if key not in model.clusters:
        raise EditError(f"کلاستر «{key}» وجود ندارد.")
    attached = [m.key for m in model.metrics.values() if m.cluster == key]
    if attached:
        raise EditError(f"این کلاستر {len(attached)} شاخص دارد "
                        f"({'، '.join(attached[:4])}…). اول آن‌ها را جابه‌جا "
                        f"یا حذف کنید — حذف بی‌صدای شاخص، امتیاز را عوض می‌کند.")
    out = _clone(model)
    del out.clusters[key]
    return out


def _clone(model: PerformanceModel) -> PerformanceModel:
    return PerformanceModel(dict(model.clusters), dict(model.metrics),
                            model.model_version)


# ═══════════ ذخیره ═══════════
def bump(version: str) -> str:
    """نسخه بعدی مدل: «1.0» → «1.1»."""
    try:
        major, minor = (version or "1.0").split(".")[:2]
        return f"{int(major)}.{int(minor) + 1}"
    except Exception:
        return "1.1"


def save(model: PerformanceModel, path: Optional[Path] = None,
         new_version: bool = True) -> Tuple[Path, Path]:
    """اعتبارسنجی، پشتیبان، سپس ذخیره.

    خروجی: (مسیر فایل، مسیر پشتیبان نسخه قبلی).
    """
    problems = model.validate()
    if problems:
        raise EditError("مدل معتبر نیست و ذخیره نشد:\n  • "
                        + "\n  • ".join(problems))
    p = Path(path) if path else model_path()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = p.with_name(f"{p.stem}_{stamp}{p.suffix}")
    if p.exists():
        shutil.copy2(p, backup)
    if new_version:
        model = PerformanceModel(model.clusters, model.metrics,
                                 bump(model.model_version))
    body = yaml.safe_dump(to_dict(model), allow_unicode=True, sort_keys=False,
                          default_flow_style=False, width=88)
    header = (f"# نسخه مدل {model.model_version} — ذخیره‌شده در "
              f"{datetime.now():%Y-%m-%d %H:%M}\n"
              f"# نسخه قبلی: {backup.name if p.exists() else '—'}\n"
              f"# هر تغییر وزن، نسخه مدل را جلو می‌برد؛ مقایسه دو دوره با دو\n"
              f"# مدل متفاوت، مقایسه نیست.\n")
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(header + body, encoding="utf-8")
    tmp.replace(p)
    return p, backup


def history(path: Optional[Path] = None) -> List[Tuple[str, str]]:
    """نسخه‌های پشتیبان موجود: (نام فایل، زمان)."""
    p = Path(path) if path else model_path()
    out = []
    for f in sorted(p.parent.glob(f"{p.stem}_*{p.suffix}"), reverse=True):
        m = re.search(r"_(\d{8})_(\d{6})", f.name)
        when = (f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]} "
                f"{m.group(2)[:2]}:{m.group(2)[2:4]}") if m else ""
        out.append((f.name, when))
    return out


def diff(a: PerformanceModel, b: PerformanceModel) -> List[str]:
    """تفاوت دو مدل، به زبان آدمیزاد — برای نمایش پیش از ذخیره."""
    lines: List[str] = []
    for k in sorted(set(b.clusters) - set(a.clusters)):
        lines.append(f"➕ کلاستر تازه: {b.clusters[k].label} "
                     f"(وزن {b.clusters[k].weight:.0%})")
    for k in sorted(set(a.clusters) - set(b.clusters)):
        lines.append(f"➖ کلاستر حذف‌شده: {a.clusters[k].label}")
    for k in sorted(set(a.clusters) & set(b.clusters)):
        if abs(a.clusters[k].weight - b.clusters[k].weight) > 1e-9:
            lines.append(f"⚖️ وزن «{a.clusters[k].label}»: "
                         f"{a.clusters[k].weight:.0%} ← {b.clusters[k].weight:.0%}")
    for k in sorted(set(b.metrics) - set(a.metrics)):
        lines.append(f"➕ شاخص تازه: {b.metrics[k].label}")
    for k in sorted(set(a.metrics) & set(b.metrics)):
        if abs(a.metrics[k].weight - b.metrics[k].weight) > 1e-9:
            lines.append(f"⚖️ وزن شاخص «{a.metrics[k].label}»: "
                         f"{a.metrics[k].weight:.2f} ← {b.metrics[k].weight:.2f}")
    return lines

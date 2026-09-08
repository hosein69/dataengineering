# -*- coding: utf-8 -*-
"""گروه همتا — چه کسی با چه کسی مقایسه می‌شود.

## چرا این ماژول هسته صحت است

مقایسه یک کارشناس ترخیص با یک کارشناس اعتبارات، چه با درصد چه با رتبه،
بی‌معناست: کار متفاوت، سختی متفاوت، مخرج متفاوت. در پکیج قبلی همه
«کارشناس + مسئول» در **یک جامعه واحد** رتبه می‌گرفتند و تنها تفکیک،
نقش بود — نه اداره، نه نوع کار.

اینجا گروه همتا سه‌تایی است: ``(مدیریت، اداره، نوع کار)``. اگر گروه از
حد نصاب کوچک‌تر باشد، **به‌جای مقایسه بی‌اعتبار**، یک پله در سلسله‌مراتب
بالا می‌رود و همین صعود در خروجی ثبت می‌شود تا خواننده بداند مقایسه در
چه سطحی انجام شده است.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..config.settings import SETTINGS

#: ستون‌های سلسله‌مراتب، از ریز به درشت
PEER_LEVELS: List[Tuple[str, ...]] = [
    ("management", "department", "job_family"),   # دقیق‌ترین
    ("management", "job_family"),
    ("department", "job_family"),
    ("job_family",),
    ("role",),                                    # آخرین سنگر
]

LEVEL_FA = {
    ("management", "department", "job_family"): "مدیریت + اداره + نوع کار",
    ("management", "job_family"): "مدیریت + نوع کار",
    ("department", "job_family"): "اداره + نوع کار",
    ("job_family",): "نوع کار",
    ("role",): "نقش",
}


@dataclass(frozen=True)
class PeerAssignment:
    person: str
    group_id: str
    level: Tuple[str, ...]
    size: int

    @property
    def level_fa(self) -> str:
        return LEVEL_FA.get(self.level, " + ".join(self.level))

    @property
    def is_fallback(self) -> bool:
        return self.level != PEER_LEVELS[0]


def _key(row: pd.Series, level: Tuple[str, ...]) -> str:
    return " | ".join(str(row.get(c, "") or "—").strip() for c in level)


def assign(people: pd.DataFrame,
           min_size: Optional[int] = None,
           allow_fallback: Optional[bool] = None) -> pd.DataFrame:
    """برای هر نفر، گروه همتا و سطح آن را تعیین می‌کند.

    ورودی باید ستون‌های ``person_key`` و ستون‌های سلسله‌مراتب را داشته باشد.
    خروجی: ``person_key, peer_group, peer_level, peer_level_fa, peer_size,
    peer_is_fallback``.
    """
    min_size = SETTINGS.MIN_PEER_GROUP if min_size is None else min_size
    allow_fallback = SETTINGS.PEER_FALLBACK if allow_fallback is None else allow_fallback

    df = people.copy()
    for c in ("management", "department", "job_family", "role"):
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    levels = PEER_LEVELS if allow_fallback else PEER_LEVELS[:1]
    out: List[dict] = []
    cols = ["person_key", "peer_group", "peer_level", "peer_level_fa",
            "peer_size", "peer_is_fallback"]
    if df.empty or "person_key" not in df.columns:
        # قالب ستون‌ها باید حفظ شود وگرنه merge بعدی با KeyError می‌افتد.
        return pd.DataFrame(columns=cols)

    for _, row in df.iterrows():
        chosen: Optional[PeerAssignment] = None
        for level in levels:
            k = _key(row, level)
            size = int((df.apply(lambda r: _key(r, level), axis=1) == k).sum())
            if size >= min_size or level == levels[-1]:
                chosen = PeerAssignment(str(row["person_key"]), k, level, size)
                break
        assert chosen is not None
        out.append({
            "person_key": chosen.person,
            "peer_group": f"{chosen.level_fa} :: {chosen.group_id}",
            "peer_level": "+".join(chosen.level),
            "peer_level_fa": chosen.level_fa,
            "peer_size": chosen.size,
            "peer_is_fallback": chosen.is_fallback,
        })
    return pd.DataFrame(out, columns=cols)


def summary(assignments: pd.DataFrame) -> pd.DataFrame:
    """خلاصه گروه‌ها — برای اینکه خواننده بداند مقایسه کجا رقیق شده."""
    if assignments.empty:
        return pd.DataFrame()
    g = (assignments.groupby(["peer_group", "peer_level_fa"], dropna=False)
         .agg(نفر=("person_key", "nunique"),
              صعود=("peer_is_fallback", "max"))
         .reset_index()
         .rename(columns={"peer_group": "گروه همتا", "peer_level_fa": "سطح"}))
    g["صعود"] = g["صعود"].map({True: "بله", False: "خیر"})
    return g.sort_values("نفر", ascending=False)

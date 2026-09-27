# -*- coding: utf-8 -*-
"""Anomalies as informants — find the odd case, and ask it why before anything else.

The usual reflex with an outlier is to clean it: clip it, smooth it, filter it
with a footnote. Sometimes that is right. But an anomaly is, by definition, the
data behaving in a way our picture of the business does not predict, so every
one of them carries a small message: *something in your model of the world is
missing here.* Three of the most useful things ever learned about this kind of
business arrived exactly that way:

* a recurring dip that was not the business at all, but a capture/export step
  that silently dropped part of the data every time;
* a "broken" segment that was not broken, but a new behaviour nobody had named
  yet;
* a number that looked too good, and turned out to be double counting — caught
  before it reached the board.

So this module never removes or alters anything. For each anomaly it produces:

``headline_fa``
    one sentence saying what is odd, in the owner's language;
``hypotheses``
    the candidate explanations, each **tested against evidence** in the data
    (not guessed), ranked by how well the evidence supports it;
``repair``
    only where one hypothesis implies a specific, reversible correction — and
    even then it is a *proposal*. Nothing is applied until a person approves it
    (``gsi/trust/inquiry.py``), and computed outputs are never "repaired" at
    all: the fix belongs in their inputs.

The detectors work at **entity grain**, exactly like the profiler: the mart has
one row per bill-of-lading × material, and counting per row would turn one odd
invoice into forty "anomalies".
"""
from __future__ import annotations

__contract__ = 1

import difflib
import hashlib
import math
import re
from dataclasses import dataclass, field as dc_field
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from ..core.numeric_parse import parse_decimal
from ..core.text import clean_key, normalize_persian_text
from .contracts import BL, ENTITY_FA, KEY_COLUMN, MATERIAL, REG, RULES
from .verdict import Evidence, Owner

# ── anomaly kinds ───────────────────────────────────────────────────────────
VALUE_OUTLIER = "VALUE_OUTLIER"
CATEGORY_VARIANT = "CATEGORY_VARIANT"
NEW_CATEGORY = "NEW_CATEGORY"
VOLUME_DROP = "VOLUME_DROP"
TOO_GOOD = "TOO_GOOD"

KIND_FA: Dict[str, str] = {
    VALUE_OUTLIER: "عدد پرت",
    CATEGORY_VARIANT: "دو املا برای یک چیز؟",
    NEW_CATEGORY: "مقدار تازه — بخش جدید یا خطا؟",
    VOLUME_DROP: "افت ناگهانی حجم داده",
    TOO_GOOD: "بیش از حد خوب برای باور",
}

# ── hypothesis codes ────────────────────────────────────────────────────────
SCALE_SLIP = "SCALE_SLIP"                # unit or decimal slip (×10^k)
OTHER_GROUP = "OTHER_GROUP"              # fits another currency/group, not its own
COMPUTED_INPUT = "COMPUTED_INPUT"        # a computed number: the cause is upstream
GENUINE_EXTREME = "GENUINE_EXTREME"      # real, just rare
SPELLING_VARIANT = "SPELLING_VARIANT"    # the same thing written two ways
NEW_SEGMENT = "NEW_SEGMENT"              # a genuinely new segment/behaviour
VOCABULARY_SHIFT = "VOCABULARY_SHIFT"    # the source changed its coding wholesale
CAPTURE_GAP = "CAPTURE_GAP"              # data was not captured/exported in full
REAL_DECLINE = "REAL_DECLINE"            # activity really went down
DOUBLE_COUNT = "DOUBLE_COUNT"            # the same fact counted twice
PLACEHOLDER_FILL = "PLACEHOLDER_FILL"    # cells "filled" with a default value
REAL_IMPROVEMENT = "REAL_IMPROVEMENT"    # a genuine clean-up or growth
MIXED_POPULATION = "MIXED_POPULATION"    # one field carrying two units/populations

STRONG, MEDIUM, WEAK = "strong", "medium", "weak"
STRENGTH_FA: Dict[str, str] = {STRONG: "شاهد قوی", MEDIUM: "شاهد متوسط", WEAK: "شاهد ضعیف"}
_STRENGTH_RANK: Dict[str, int] = {STRONG: 0, MEDIUM: 1, WEAK: 2}

# ── repair kinds (proposals only; see inquiry.apply_repairs) ─────────────────
RESCALE = "RESCALE"    # one entity's value ÷ 10^k
ALIAS = "ALIAS"        # one spelling → the established spelling

# ── thresholds ──────────────────────────────────────────────────────────────
#: Below this many peers a "typical value" is not a typical value.
MIN_PEERS = 8
#: Iglewicz–Hoaglin modified z-score limit on log10 values.
Z_LIMIT = 3.5
#: And at least this many times away from the median, so a tight distribution
#: does not turn every ordinary deviation into a question for a person.
MIN_FOLD = 3.0
#: Log10 slack around the peers' 10–90% band when testing "would this value be
#: ordinary after moving k digits?" — 0.3 ≈ a factor of two.
SCALE_SLACK = 0.3
#: An outlier is rare by definition. When at least this share of the peers
#: (and at least RARE_MIN of them) sit within RARE_BAND (log10, ≈ ±12%) of a
#: value, that value is a mode of the distribution, not an outlier — found by
#: A/B on scaled data, where a MAD collapsed by ties flagged a third of all
#: materials ("10" and "411" each shared by 41 of them).
RARE_SHARE = 0.05
RARE_MIN = 3
RARE_BAND = 0.05
#: More outliers than this in one field/group is not a list of odd cases — it
#: is one question about the field (mixed units or populations, or a model that
#: does not fit it). Same rule as VOCABULARY_SHIFT and FIELD_NEVER_POPULATED:
#: one cause, one question. Found by A/B on a 50k-row frame (880 questions).
FLOOD_SHARE = 0.02
FLOOD_MIN = 10
#: Runs of history needed before "unusual compared with before" means anything.
MIN_HISTORY = 3
#: Trailing window for the historical baseline.
BASELINE_WINDOW = 6
DROP_RATIO = 0.8
JUMP_RATIO = 1.6
MIN_VOLUME = 10
#: Coverage (percentage points) gained in one run that deserves a second look.
COVERAGE_JUMP = 30.0
SIMILARITY = 0.88
#: More new values than this in one field at once is a coding change, not
#: dozens of new segments.
MAX_NEW_PER_FIELD = 12
MAX_CATEGORIES_KEPT = 300
MAX_ANOMALIES = 200


# ═══════════════════════════════════════════════════════════════════════════
#  What to watch
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class NumericWatch:
    """A number whose unusual values are worth a question.

    ``heal_column`` is the column a correction may be written to. It must exist
    by stage 21 (after derivation, before any engine computes from it); empty
    means the number is *computed*, and a computed output is never overwritten
    — the question goes to its inputs instead.
    """
    column: str
    title_fa: str
    entity: str
    owner_column: str = ""
    owner_role_fa: str = ""
    group_by: str = ""
    heal_column: str = ""
    computed_from_fa: str = ""


@dataclass(frozen=True)
class CategoryWatch:
    """A categorical field whose vocabulary is worth watching."""
    column: str
    title_fa: str
    entity: str
    owner_column: str = ""
    owner_role_fa: str = ""
    heal_column: str = ""


NUMERIC_WATCHES: Tuple[NumericWatch, ...] = (
    NumericWatch("INVOICE_VALUE", "ارزش فاکتور", REG,
                 "EXPERT_CLEARANCE", "کارشناس ترخیص",
                 group_by="INVOICE_CURRENCY", heal_column="INVOICE_VALUE"),
    NumericWatch("مانده تعهد", "مانده تعهد ارزی", REG,
                 "EXPERT_SETTLEMENT", "کارشناس رفع تعهد ارزی",
                 group_by="FX_NTSW_CURRENCY",
                 computed_from_fa="تعهد اولیه و رفع‌شده‌های NTSW"),
    NumericWatch("DAILY_NEED", "نیاز روزانه", MATERIAL,
                 "EXPERT_COMMERCIAL", "کارشناس بازرگانی", heal_column="DAILY_NEED"),
    NumericWatch("STOCK_IKCO", "موجودی ایران‌خودرو", MATERIAL,
                 "EXPERT_COMMERCIAL", "کارشناس بازرگانی", heal_column="STOCK_IKCO"),
    NumericWatch("STOCK_SAPCO", "موجودی ساپکو", MATERIAL,
                 "EXPERT_COMMERCIAL", "کارشناس بازرگانی", heal_column="STOCK_SAPCO"),
)

CATEGORY_WATCHES: Tuple[CategoryWatch, ...] = (
    CategoryWatch("PART_GROUP", "گروه قطعه", MATERIAL,
                  "EXPERT_COMMERCIAL", "کارشناس بازرگانی", heal_column="PART_GROUP"),
    CategoryWatch("SUPPLY_GROUP", "گروه تأمین", MATERIAL,
                  "EXPERT_COMMERCIAL", "کارشناس بازرگانی", heal_column="SUPPLY_GROUP"),
    CategoryWatch("TRANSPORT_MODE", "شیوه حمل", BL,
                  "EXPERT_LOGISTICS", "کارشناس لجستیک", heal_column="TRANSPORT_MODE"),
    CategoryWatch("ENTRY_BORDER", "مرز ورودی", BL,
                  "EXPERT_CLEARANCE", "کارشناس ترخیص", heal_column="ENTRY_BORDER"),
    CategoryWatch("DEST_CUSTOMS", "گمرک مقصد", BL,
                  "EXPERT_CLEARANCE", "کارشناس ترخیص", heal_column="DEST_CUSTOMS"),
    CategoryWatch("BANK", "بانک", REG,
                  "EXPERT_SETTLEMENT", "کارشناس رفع تعهد ارزی", heal_column="BANK"),
)

#: Columns a repair may never touch. Keys decide which rows belong together;
#: changing one silently re-joins cases, which is a different, far larger act
#: than correcting a value.
NEVER_HEAL = frozenset(KEY_COLUMN.values()) | frozenset({
    "KEY_REG", "KEY_ORDER", "KEY_BL", "KEY_PR", "KEY_EMP", "CANONICAL_ORDER",
})


# ═══════════════════════════════════════════════════════════════════════════
#  Records
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Hypothesis:
    """One candidate explanation, with the evidence that supports it."""
    code: str
    title_fa: str
    evidence_fa: str
    strength: str = MEDIUM
    repair: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "title_fa": self.title_fa,
                "evidence_fa": self.evidence_fa, "strength": self.strength,
                "repair": dict(self.repair) if self.repair else None}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Hypothesis":
        return cls(code=str(d.get("code", "")), title_fa=str(d.get("title_fa", "")),
                   evidence_fa=str(d.get("evidence_fa", "")),
                   strength=str(d.get("strength", MEDIUM)),
                   repair=dict(d["repair"]) if d.get("repair") else None)


@dataclass
class Anomaly:
    """Something the data did that our picture of the business did not predict."""
    kind: str
    entity: str
    field: str
    field_fa: str
    key: str
    #: What exactly was observed. Part of the id, so an explanation stays bound
    #: to the value that was explained: if the value changes, the question is
    #: asked again instead of the old answer silently covering a new fact.
    signature: str
    headline_fa: str
    observed_fa: str = ""
    expected_fa: str = ""
    hypotheses: List[Hypothesis] = dc_field(default_factory=list)
    owner_name: str = ""
    owner_role: str = ""
    owner_dept: str = ""
    locator_fa: str = ""
    severity: float = 0.0

    @property
    def id(self) -> str:
        raw = "|".join((self.kind, self.entity, self.field, self.key, self.signature))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    @property
    def kind_fa(self) -> str:
        return KIND_FA.get(self.kind, self.kind)

    @property
    def leading(self) -> Optional[Hypothesis]:
        return self.hypotheses[0] if self.hypotheses else None

    @property
    def repair(self) -> Optional[Dict[str, Any]]:
        """The correction implied by the best-supported hypothesis that has one."""
        for h in self.hypotheses:
            if h.repair:
                return h.repair
        return None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind, "entity": self.entity,
            "field": self.field, "field_fa": self.field_fa, "key": self.key,
            "signature": self.signature, "headline_fa": self.headline_fa,
            "observed_fa": self.observed_fa, "expected_fa": self.expected_fa,
            "hypotheses": [h.as_dict() for h in self.hypotheses],
            "owner_name": self.owner_name, "owner_role": self.owner_role,
            "owner_dept": self.owner_dept, "locator_fa": self.locator_fa,
            "severity": round(float(self.severity), 3),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Anomaly":
        return cls(
            kind=str(d.get("kind", "")), entity=str(d.get("entity", "")),
            field=str(d.get("field", "")), field_fa=str(d.get("field_fa", "")),
            key=str(d.get("key", "")), signature=str(d.get("signature", "")),
            headline_fa=str(d.get("headline_fa", "")),
            observed_fa=str(d.get("observed_fa", "")),
            expected_fa=str(d.get("expected_fa", "")),
            hypotheses=[Hypothesis.from_dict(h) for h in d.get("hypotheses") or ()],
            owner_name=str(d.get("owner_name", "")), owner_role=str(d.get("owner_role", "")),
            owner_dept=str(d.get("owner_dept", "")), locator_fa=str(d.get("locator_fa", "")),
            severity=float(d.get("severity", 0.0) or 0.0),
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Small helpers
# ═══════════════════════════════════════════════════════════════════════════
def fmt_number(value: float) -> str:
    """Readable number: grouping for large values, no trailing noise for small."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    text = f"{value:,.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _factor_fa(k: int) -> str:
    n = f"{10 ** abs(k):,}"
    return f"÷{n}" if k > 0 else f"×{n}"


def _blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return not str(value).strip()


_NORM_STRIP = re.compile(r"[\s‌‍\-_./\\,،]+")


def category_norm(value: Any) -> str:
    """Spelling-insensitive identity of a category value.

    Persian glyph variants (ي/ی، ك/ک), digits, case, spaces and punctuation are
    folded, so «بندر عباس»، «بندرعباس» and «بندر-عباس» are recognised as one
    spelling problem rather than three segments.
    """
    return _NORM_STRIP.sub("", normalize_persian_text(value).lower())


def _numeric_series(values: pd.Series) -> pd.Series:
    """Numbers where the cell is a number; NaN otherwise (never a default)."""
    numeric = pd.to_numeric(values, errors="coerce")
    need = numeric.isna() & values.notna()
    if need.any():
        parsed = values[need].map(lambda v: parse_decimal(v, strict=False))
        numeric.loc[need] = parsed.map(lambda d: float(d) if d is not None else float("nan"))
    return numeric.astype(float)


def _normalizer_for_group(column: str):
    """Currency groups are normalised to ISO codes; anything else is folded text."""
    if "CURRENCY" in column.upper():
        try:
            from ..rulebook import get_rulebook
            rb = get_rulebook()
            return lambda v: (rb.normalize_currency(v) or normalize_persian_text(v).upper())
        except Exception:
            pass
    return lambda v: normalize_persian_text(v).upper()


def _owner_of(row: Mapping[str, Any], owner_column: str, role_fa: str) -> Owner:
    return Owner.from_row(row, prefer=owner_column, role_label=role_fa)


def _quantile(values: Sequence[float], q: float) -> float:
    return float(pd.Series(values, dtype=float).quantile(q))


# ═══════════════════════════════════════════════════════════════════════════
#  1) Numeric outliers — at entity grain, within peer group
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class _GroupStats:
    label: str
    n: int
    median: float
    scale: Optional[float]
    q10: float
    q25: float
    q75: float
    q90: float


def _group_stats(label: str, logs: Sequence[float]) -> _GroupStats:
    med = float(median(logs))
    deviations = [abs(x - med) for x in logs]
    mad = float(median(deviations))
    if mad > 0:
        scale: Optional[float] = mad / 0.6745
    else:
        mean_abs = sum(deviations) / len(deviations)
        scale = mean_abs * 1.2533 if mean_abs > 0 else None
    return _GroupStats(label, len(logs), med, scale,
                       _quantile(logs, .10), _quantile(logs, .25),
                       _quantile(logs, .75), _quantile(logs, .90))


def _entity_numbers(df: pd.DataFrame, key_col: str, watch: NumericWatch) -> pd.DataFrame:
    """One value per entity: its first usable number. Conflicts are the
    profiler's business (VALUE_CONFLICT), not an outlier question."""
    frame = pd.DataFrame({
        "key": df[key_col].map(clean_key),
        "value": _numeric_series(df[watch.column]),
        "idx": range(len(df)),
    })
    if watch.group_by and watch.group_by in df.columns:
        norm = _normalizer_for_group(watch.group_by)
        frame["group"] = df[watch.group_by].map(lambda v: "" if _blank(v) else norm(v))
    else:
        frame["group"] = ""
    frame = frame[(frame["key"] != "") & frame["value"].notna()]
    return frame.drop_duplicates("key", keep="first")


def _numeric_outliers(df: pd.DataFrame, watch: NumericWatch) -> List[Anomaly]:
    key_col = KEY_COLUMN.get(watch.entity, "")
    if not key_col or key_col not in df.columns or watch.column not in df.columns:
        return []
    values = _entity_numbers(df, key_col, watch)
    # Zero and negative values are meaningful (zero stock stops the line) or
    # already a validity defect; neither has a place on a log scale.
    values = values[values["value"] > 0]
    if watch.group_by:
        # No currency, no peers: comparing an unknown-currency amount with
        # others is the currency mix the trust layer refuses everywhere else.
        values = values[values["group"] != ""]
    if values.empty:
        return []
    values = values.assign(log=values["value"].map(math.log10))

    stats: Dict[str, _GroupStats] = {}
    peer_logs: Dict[str, pd.Series] = {}
    for group, part in values.groupby("group", sort=False):
        if len(part) >= MIN_PEERS:
            stats[group] = _group_stats(group, part["log"].tolist())
            peer_logs[group] = part["log"]

    found: Dict[str, List[Anomaly]] = {}
    min_distance = math.log10(MIN_FOLD)
    for rec in values.itertuples(index=False):
        st = stats.get(rec.group)
        if st is None:
            continue
        distance = rec.log - st.median
        if abs(distance) < min_distance:
            continue
        z = abs(distance) / st.scale if st.scale else float("inf")
        if z < Z_LIMIT:
            continue
        near = int((peer_logs[rec.group] - rec.log).abs().le(RARE_BAND).sum())
        if near >= max(RARE_MIN, RARE_SHARE * st.n):
            continue
        found.setdefault(rec.group, []).append(
            _outlier_anomaly(df, watch, key_col, rec, st, stats, distance))
    return _collapse_floods(found, watch, stats)


def _collapse_floods(found: Dict[str, List[Anomaly]], watch: NumericWatch,
                     stats: Dict[str, "_GroupStats"]) -> List[Anomaly]:
    """Replace a flood of per-case outliers in one group by a single question."""
    out: List[Anomaly] = []
    for group, items in found.items():
        n = stats[group].n
        if len(items) <= max(FLOOD_MIN, FLOOD_SHARE * n):
            out.extend(items)
            continue
        first = max(items, key=lambda a: a.severity)
        sample = "، ".join(a.key for a in sorted(items, key=lambda a: -a.severity)[:5])
        out.append(Anomaly(
            kind=VALUE_OUTLIER, entity=watch.entity, field=watch.column,
            field_fa=watch.title_fa, key=f"*{group}", signature=f"flood:{len(items)}/{n}",
            headline_fa=(f"{len(items)} از {n} مقدار «{watch.title_fa}» دور از معمول‌اند — "
                         "آن‌قدر زیاد که تک‌تک پرسیدنشان معنا ندارد."),
            observed_fa=f"{len(items)} مورد، مثل {sample}", expected_fa=first.expected_fa,
            hypotheses=[
                Hypothesis(MIXED_POPULATION, "دو واحد یا دو جمعیت در یک فیلد",
                           "وقتی ده‌ها مقدار هم‌زمان دور از معمول‌اند، معمولاً فیلد دو چیز را با "
                           "هم نگه می‌دارد (عدد و هزارگان، قطعه کم‌مصرف و پرمصرف) یا یک سورس "
                           "واحدش را عوض کرده است. چند نمونه بالا را در سورس ببینید.", MEDIUM),
                Hypothesis(GENUINE_EXTREME, "توزیع واقعی این فیلد پهن است",
                           "اگر این پراکندگی طبیعی است، در یک جمله بگویید تا از این به بعد "
                           "پرسیده نشود.", WEAK)],
            owner_name=first.owner_name, owner_role=first.owner_role,
            owner_dept=first.owner_dept, severity=first.severity + 1.0))
    return out


def _outlier_anomaly(df, watch: NumericWatch, key_col: str, rec, st: _GroupStats,
                     stats: Dict[str, _GroupStats], distance: float) -> Anomaly:
    value = float(rec.value)
    fold = 10 ** abs(distance)
    bigger = distance > 0
    group_fa = f"ارز {st.label}" if st.label and "CURRENCY" in watch.group_by.upper() \
        else (st.label or "همه پرونده‌ها")
    hyps: List[Hypothesis] = []

    # (a) unit / decimal slip — the number sits in the middle of its peers once
    # 1–6 digits are moved. A shift of 3 or 6 is the signature of a unit mix-up
    # (rial / thousand rial, kg / tonne); 1–2 of a lost decimal separator.
    k = int(round(distance))
    if k != 0 and abs(distance - k) <= 0.35:
        rescaled_log = rec.log - k
        # A slipped value was an ordinary value before the slip, and ordinary
        # includes the edges of the range: a large-but-normal invoice typed in
        # thousands sits near the top once corrected, not in the middle. So the
        # band is the 10–90% range widened by SCALE_SLACK on each side.
        # A shift of exactly 3 or 6 digits that lands inside that band is the
        # signature of a unit mix-up and counts as strong; 1–2 digits (a lost
        # decimal separator) is as often a genuinely large order, so medium.
        if st.q10 - SCALE_SLACK <= rescaled_log <= st.q90 + SCALE_SLACK:
            core = st.q25 <= rescaled_log <= st.q75
            strength = STRONG if k % 3 == 0 else MEDIUM
            rescaled = value / (10 ** k)
            repair = None
            if watch.heal_column and watch.heal_column not in NEVER_HEAL:
                repair = {"kind": RESCALE, "column": watch.heal_column,
                          "label": watch.title_fa,
                          "key_column": key_col, "key": rec.key,
                          "original": value, "factor": float(10 ** k),
                          "new": rescaled}
            kind_fa = ("جابه‌جایی واحد (مثل ریال/هزار ریال یا کیلو/تن)" if k % 3 == 0
                       else "جاافتادن یا جابه‌جایی ممیز")
            evidence = (f"اگر {_factor_fa(k)} شود، {fmt_number(rescaled)} می‌شود و "
                        f"{'درست وسط' if core else 'داخل بازه'} بقیه پرونده‌های {group_fa} "
                        f"می‌نشیند. جابه‌جایی دقیقاً {abs(k)} رقم، امضای {kind_fa} است.")
            if not watch.heal_column:
                evidence += (f" این عدد محاسبه‌شده است؛ اصلاح باید در ورودی‌اش "
                             f"({watch.computed_from_fa}) انجام شود — سامانه خودش آن را عوض نمی‌کند.")
            hyps.append(Hypothesis(SCALE_SLIP, f"خطای واحد یا ممیز ({_factor_fa(k)})",
                                   evidence, strength, repair))

    # (b) it belongs to another group — typically a wrong currency.
    for label, other in stats.items():
        if label == st.label or not label:
            continue
        if other.q25 <= rec.log <= other.q75:
            what = "ارز" if "CURRENCY" in watch.group_by.upper() else "گروه"
            hyps.append(Hypothesis(
                OTHER_GROUP, f"{what} اشتباه ثبت شده؟",
                f"این عدد دقیقاً در بازه معمول پرونده‌های «{label}» است، نه «{st.label}». "
                f"اگر {what} این پرونده «{label}» باشد، هیچ چیز عجیبی باقی نمی‌ماند.",
                MEDIUM))
            break

    # (c) a computed number: the cause is upstream by construction.
    if not watch.heal_column:
        hyps.append(Hypothesis(
            COMPUTED_INPUT, "ریشه در ورودی‌های محاسبه است",
            f"«{watch.title_fa}» را سامانه از {watch.computed_from_fa} می‌سازد. "
            "اگر عجیب است، یکی از ورودی‌ها عجیب است؛ همان را در سورس بررسی کنید.",
            MEDIUM))

    # (d) it is real. Always offered, never assumed.
    real_strength = WEAK if any(h.strength == STRONG for h in hyps) else MEDIUM
    hyps.append(Hypothesis(
        GENUINE_EXTREME, "واقعی است — یک مورد استثنایی",
        f"{fold:,.0f} برابر {'بزرگ‌تر' if bigger else 'کوچک‌تر'} از میانه {st.n} پرونده "
        f"هم‌گروه است، ولی ممکن است واقعاً همین باشد. اگر این‌طور است، در یک جمله بگویید "
        "چرا — این جمله خودش دانش کسب‌وکار است و دفعه بعد دوباره پرسیده نمی‌شود.",
        real_strength))
    # On equal evidence "it may be real" leads: the page must not put a
    # correction first unless the data favours it more than the value itself.
    hyps.sort(key=lambda h: (_STRENGTH_RANK.get(h.strength, 9), h.code != GENUINE_EXTREME))

    row = df.iloc[int(rec.idx)]
    owner = _owner_of(row, watch.owner_column, watch.owner_role_fa)
    return Anomaly(
        kind=VALUE_OUTLIER, entity=watch.entity, field=watch.column,
        field_fa=watch.title_fa, key=rec.key, signature=repr(round(value, 6)),
        headline_fa=(f"«{watch.title_fa}» در {ENTITY_FA.get(watch.entity, watch.entity)} "
                     f"{rec.key} برابر {fmt_number(value)} است — حدود {fold:,.0f} برابر "
                     f"{'بیشتر' if bigger else 'کمتر'} از معمولِ {group_fa}."),
        observed_fa=fmt_number(value),
        expected_fa=(f"میانه {fmt_number(10 ** st.median)} · بازه معمول "
                     f"{fmt_number(10 ** st.q25)} تا {fmt_number(10 ** st.q75)} ({st.n} پرونده)"),
        hypotheses=hyps,
        owner_name=owner.name, owner_role=owner.role, owner_dept=owner.dept,
        locator_fa=Evidence.from_row(row, column=watch.column).locator_fa,
        severity=abs(distance) + (1.0 if hyps and hyps[0].strength == STRONG else 0.0),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  2) Categories — spelling variants, and values never seen before
# ═══════════════════════════════════════════════════════════════════════════
def _category_counts(df: pd.DataFrame, key_col: str, column: str
                     ) -> Tuple[Dict[str, int], Dict[str, List[str]], Dict[str, int]]:
    """Per raw value: distinct entities, their keys, and one row index."""
    raw = df[column].map(lambda v: "" if _blank(v) else str(v).strip())
    keys = df[key_col].map(clean_key)
    frame = pd.DataFrame({"raw": raw, "key": keys, "idx": range(len(df))})
    frame = frame[(frame["raw"] != "") & (frame["key"] != "")]
    counts: Dict[str, int] = {}
    members: Dict[str, List[str]] = {}
    first_row: Dict[str, int] = {}
    for value, part in frame.groupby("raw", sort=False):
        uniq = list(dict.fromkeys(part["key"]))
        counts[value] = len(uniq)
        members[value] = uniq
        first_row[value] = int(part["idx"].iloc[0])
    return counts, members, first_row


def _alias_repair(watch: CategoryWatch, key_col: str, variant: str, canonical: str,
                  keys: Sequence[str]) -> Optional[Dict[str, Any]]:
    if not watch.heal_column or watch.heal_column in NEVER_HEAL:
        return None
    return {"kind": ALIAS, "column": watch.heal_column, "label": watch.title_fa,
            "key_column": key_col,
            "variant": variant, "canonical": canonical, "keys": list(keys)[:500]}


def _category_anomalies(df: pd.DataFrame, watch: CategoryWatch,
                        known_before: Optional[set]) -> List[Anomaly]:
    key_col = KEY_COLUMN.get(watch.entity, "")
    if not key_col or key_col not in df.columns or watch.column not in df.columns:
        return []
    counts, members, first_row = _category_counts(df, key_col, watch.column)
    if len(counts) < 2 and not known_before:
        return []

    out: List[Anomaly] = []
    flagged: set = set()

    def make(kind, value, signature, headline, hyps, severity) -> Anomaly:
        row = df.iloc[first_row[value]]
        owner = _owner_of(row, watch.owner_column, watch.owner_role_fa)
        return Anomaly(
            kind=kind, entity=watch.entity, field=watch.column, field_fa=watch.title_fa,
            key=value, signature=signature, headline_fa=headline,
            observed_fa=f"«{value}» — {counts[value]} {ENTITY_FA.get(watch.entity, '')}",
            hypotheses=hyps, owner_name=owner.name, owner_role=owner.role,
            owner_dept=owner.dept,
            locator_fa=Evidence.from_row(row, column=watch.column).locator_fa,
            severity=severity)

    # (a) spelling variants within this run
    by_norm: Dict[str, List[str]] = {}
    for value in counts:
        by_norm.setdefault(category_norm(value), []).append(value)
    for spellings in by_norm.values():
        if len(spellings) < 2:
            continue
        spellings.sort(key=lambda v: (-counts[v], v))
        canonical = spellings[0]
        for variant in spellings[1:]:
            flagged.add(variant)
            out.append(make(
                CATEGORY_VARIANT, variant, f"{variant}→{canonical}",
                f"«{variant}» و «{canonical}» در «{watch.title_fa}» فقط در املا فرق دارند.",
                [Hypothesis(SPELLING_VARIANT, f"همان «{canonical}» است",
                            f"با یکسان‌سازی حروف، فاصله و نشانه‌ها دقیقاً یکی می‌شوند. "
                            f"«{canonical}» {counts[canonical]} و «{variant}» {counts[variant]} "
                            f"{ENTITY_FA.get(watch.entity, 'پرونده')} دارد؛ تا یکی نشوند، هر "
                            "گزارش گروهی این بخش را دو تکه نشان می‌دهد.",
                            STRONG, _alias_repair(watch, key_col, variant, canonical,
                                                  members[variant])),
                 Hypothesis(NEW_SEGMENT, "واقعاً دو چیز متفاوت‌اند",
                            "اگر این دو املا عمداً دو بخش جدا را نشان می‌دهند، در یک جمله "
                            "تفاوتشان را بنویسید تا دیگر پرسیده نشود.", WEAK)],
                2.0 + counts[variant] / max(1, counts[canonical])))

    # (b) near-spellings: a rare value almost identical to a common one
    distinct = [v for v in counts if v not in flagged]
    if len(distinct) <= 400:
        for variant in distinct:
            n = counts[variant]
            best, best_ratio = "", 0.0
            vn = category_norm(variant)
            if len(vn) < 4:
                continue
            for other in distinct:
                if other == variant or counts[other] < max(3, 3 * n):
                    continue
                ratio = difflib.SequenceMatcher(None, vn, category_norm(other)).ratio()
                if ratio > best_ratio:
                    best, best_ratio = other, ratio
            if best and best_ratio >= SIMILARITY:
                flagged.add(variant)
                out.append(make(
                    CATEGORY_VARIANT, variant, f"{variant}→{best}",
                    f"«{variant}» ({n}) تقریباً همان «{best}» ({counts[best]}) است — غلط تایپی یا بخش جدا؟",
                    [Hypothesis(SPELLING_VARIANT, f"غلط تایپی «{best}»",
                                f"{best_ratio:.0%} شبیه است و «{best}» {counts[best]} برابر رایج‌تر. "
                                "غلط‌های تایپی تقریباً همیشه نادر و شبیه یک مقدار رایج‌اند.",
                                MEDIUM, _alias_repair(watch, key_col, variant, best,
                                                      members[variant])),
                     Hypothesis(NEW_SEGMENT, "یک بخش جدا با نام مشابه",
                                "اسم‌های شبیه گاهی واقعاً دو چیز متفاوت‌اند (دو گمرک، دو گروه). "
                                "اگر این‌طور است، در یک جمله بنویسید.", MEDIUM)],
                    1.5))

    # (c) values never seen in earlier runs
    if known_before:
        known_norm = {category_norm(v): v for v in known_before}
        new = [v for v in counts if v not in known_before and v not in flagged
               and category_norm(v) not in known_norm]
        if len(new) > MAX_NEW_PER_FIELD and len(new) > 0.5 * len(counts):
            sample = "، ".join(f"«{v}»" for v in new[:5])
            value = max(new, key=lambda v: counts[v])
            out.append(make(
                NEW_CATEGORY, value, f"vocab:{len(new)}/{len(counts)}",
                f"{len(new)} از {len(counts)} مقدار «{watch.title_fa}» در این اجرا تازه‌اند "
                f"(مثل {sample}) — کل واژگان این فیلد عوض شده است.",
                [Hypothesis(VOCABULARY_SHIFT, "قالب یا کدگذاری سورس عوض شده",
                            "وقتی بیشتر مقادیر یک‌باره تازه می‌شوند، تقریباً هیچ‌وقت کسب‌وکار "
                            "عوض نشده؛ سیستم مبدأ کدگذاری/زبان/ستون را تغییر داده است.", STRONG),
                 Hypothesis(NEW_SEGMENT, "واقعاً بخش‌های تازه‌اند",
                            "اگر کسب‌وکار واقعاً وارد این بخش‌ها شده، در یک جمله بنویسید.", WEAK)],
                3.0))
        else:
            for value in new:
                hyps: List[Hypothesis] = []
                vn = category_norm(value)
                best, best_ratio = "", 0.0
                if len(vn) >= 4:
                    for norm, old in known_norm.items():
                        ratio = difflib.SequenceMatcher(None, vn, norm).ratio()
                        if ratio > best_ratio:
                            best, best_ratio = old, ratio
                if best and best_ratio >= SIMILARITY:
                    hyps.append(Hypothesis(
                        SPELLING_VARIANT, f"همان «{best}» قبلی است",
                        f"{best_ratio:.0%} شبیه مقداری است که در اجراهای قبل بود.",
                        MEDIUM, _alias_repair(watch, key_col, value, best, members[value])))
                hyps.append(Hypothesis(
                    NEW_SEGMENT, "بخش یا رفتار تازه",
                    f"در هیچ اجرای قبلی نبود و حالا {counts[value]} "
                    f"{ENTITY_FA.get(watch.entity, 'پرونده')} دارد. بخش‌های «خراب» گاهی رفتار "
                    "تازه‌ای‌اند که هنوز کسی برایش اسم نگذاشته — اگر این‌طور است، نامش را بنویسید.",
                    MEDIUM))
                out.append(make(
                    NEW_CATEGORY, value, f"new:{value}",
                    f"«{value}» برای اولین بار در «{watch.title_fa}» دیده شد "
                    f"({counts[value]} {ENTITY_FA.get(watch.entity, 'پرونده')}).",
                    hyps, 1.0 + min(2.0, counts[value] / 10.0)))
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Observations — the compact fingerprint each run leaves for the next one
# ═══════════════════════════════════════════════════════════════════════════
def _coverage_fields() -> List[Tuple[str, str, str]]:
    """(column, entity, label) for every decision field and every watch."""
    out: Dict[str, Tuple[str, str, str]] = {}
    for entity, rules in RULES.items():
        for rule in rules:
            out.setdefault(rule.column, (rule.column, entity, rule.label))
    for w in NUMERIC_WATCHES:
        out.setdefault(w.column, (w.column, w.entity, w.title_fa))
    for c in CATEGORY_WATCHES:
        out.setdefault(c.column, (c.column, c.entity, c.title_fa))
    return list(out.values())


def observe(df: pd.DataFrame, *, sources: Optional[Mapping[str, Mapping[str, Any]]] = None
            ) -> Dict[str, Any]:
    """What this run looked like, in a form the next run can compare against.

    JSON-safe and small: counts, coverages, totals and category vocabularies —
    never cell values tied to a case.
    """
    obs: Dict[str, Any] = {"version": 1, "sources": {}, "entities": {},
                           "rows_per_entity": {}, "fields": {}, "categories": {}}
    for src, frames in (sources or {}).items():
        for name, frame in (frames or {}).items():
            if isinstance(frame, pd.DataFrame):
                obs["sources"][f"{src}/{name}"] = int(len(frame))
    if df is None or df.empty:
        return obs

    keys: Dict[str, pd.Series] = {}
    for entity, key_col in KEY_COLUMN.items():
        if key_col in df.columns:
            k = df[key_col].map(clean_key)
            keys[entity] = k
            n = int(k[k != ""].nunique())
            obs["entities"][entity] = n
            if n:
                obs["rows_per_entity"][entity] = round(int((k != "").sum()) / n, 4)

    for column, entity, _label in _coverage_fields():
        if column not in df.columns or entity not in keys:
            continue
        k = keys[entity]
        frame = pd.DataFrame({"key": k, "raw": df[column]})
        frame = frame[frame["key"] != ""]
        if frame.empty:
            continue
        filled = frame[~frame["raw"].map(_blank)].drop_duplicates("key")
        total_entities = frame["key"].nunique()
        info: Dict[str, Any] = {
            "coverage": round(100.0 * len(filled) / total_entities, 2) if total_entities else 0.0,
            "n": int(len(filled)),
        }
        if len(filled):
            top = filled["raw"].astype(str).str.strip().value_counts()
            info["top"] = str(top.index[0])[:60]
            info["top_share"] = round(float(top.iloc[0]) / len(filled), 4)
        obs["fields"][column] = info

    for w in NUMERIC_WATCHES:
        key_col = KEY_COLUMN.get(w.entity, "")
        if w.column not in df.columns or key_col not in df.columns:
            continue
        values = _entity_numbers(df, key_col, w)
        info = obs["fields"].setdefault(w.column, {})
        totals = values.groupby("group")["value"].sum()
        info["totals"] = {str(g): round(float(v), 4) for g, v in totals.items()}

    for c in CATEGORY_WATCHES:
        if c.column in df.columns:
            vals = df[c.column].map(lambda v: "" if _blank(v) else str(v).strip())
            vocab = sorted({v for v in vals if v})
            obs["categories"][c.column] = vocab[:MAX_CATEGORIES_KEPT]
    return obs


# ═══════════════════════════════════════════════════════════════════════════
#  3) Against history — volume drops and "too good"
# ═══════════════════════════════════════════════════════════════════════════
def _history_obs(history: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    out = []
    for summary in history or ():
        obs = (summary or {}).get("observations")
        if isinstance(obs, Mapping):
            out.append(obs)
    return out


def _series(history: Sequence[Mapping[str, Any]], *path: str) -> List[float]:
    out: List[float] = []
    for obs in history:
        node: Any = obs
        for p in path:
            node = node.get(p) if isinstance(node, Mapping) else None
            if node is None:
                break
        if isinstance(node, (int, float)) and math.isfinite(float(node)):
            out.append(float(node))
    return out


def _baseline(past: Sequence[float]) -> Optional[float]:
    if len(past) < MIN_HISTORY:
        return None
    return float(median(past[-BASELINE_WINDOW:]))


def _recurring_drops(past: Sequence[float]) -> int:
    """How often this same metric dipped below its own trailing baseline before."""
    hits = 0
    for i in range(MIN_HISTORY, len(past)):
        base = median(past[max(0, i - BASELINE_WINDOW):i])
        if base >= MIN_VOLUME and past[i] < DROP_RATIO * base:
            hits += 1
    return hits


def _volume_anomalies(obs: Mapping[str, Any], history: Sequence[Mapping[str, Any]]
                      ) -> List[Anomaly]:
    metrics: List[Tuple[str, str, str, float, List[float]]] = []
    for name, cur in (obs.get("sources") or {}).items():
        metrics.append(("source", name, f"سورس {name}", float(cur),
                        _series(history, "sources", name)))
    for entity, cur in (obs.get("entities") or {}).items():
        metrics.append(("entity", entity, f"تعداد {ENTITY_FA.get(entity, entity)}",
                        float(cur), _series(history, "entities", entity)))

    drops: Dict[str, Tuple[float, float, int]] = {}
    tracked_sources = 0
    for scope, name, _label, cur, past in metrics:
        base = _baseline(past)
        if base is None:
            continue
        if scope == "source":
            tracked_sources += 1
        if base >= MIN_VOLUME and cur < DROP_RATIO * base:
            drops[f"{scope}:{name}"] = (cur, base, _recurring_drops(past))

    source_drops = [k for k in drops if k.startswith("source:")]
    out: List[Anomaly] = []
    for scope, name, label, cur, past in metrics:
        hit = drops.get(f"{scope}:{name}")
        if not hit:
            continue
        cur, base, recurrences = hit
        pct = 100.0 * (1 - cur / base)
        isolated = scope == "source" and len(source_drops) == 1 and tracked_sources > 1
        broad = tracked_sources > 1 and len(source_drops) >= 0.6 * tracked_sources
        capture_bits = []
        if recurrences:
            capture_bits.append(f"این افت {recurrences} بار دیگر هم در سابقه همین سنجه رخ داده؛ "
                                "افتِ تکرارشونده و منظم تقریباً همیشه یک مرحله ثبت/استخراج است، نه بازار.")
        if isolated:
            capture_bits.append("فقط همین سورس افت کرده و بقیه عادی‌اند؛ فعالیت واقعی معمولاً "
                                "در چند سورس هم‌زمان دیده می‌شود.")
        capture_bits.append("قبل از هر تفسیری، تعداد ردیف فایل اصلی را با همین عدد مقایسه کنید.")
        capture = Hypothesis(CAPTURE_GAP, "بخشی از داده ثبت یا استخراج نشده",
                             " ".join(capture_bits),
                             STRONG if (recurrences or isolated) else MEDIUM)
        real = Hypothesis(REAL_DECLINE, "کاهش واقعی فعالیت",
                          ("چند سورس با هم افت کرده‌اند، که با کاهش واقعی سازگار است."
                           if broad else "فقط وقتی باور کنید که سورس‌های دیگر هم همین را نشان دهند."),
                          MEDIUM if broad else WEAK)
        hyps = sorted([capture, real], key=lambda h: _STRENGTH_RANK[h.strength])
        out.append(Anomaly(
            kind=VOLUME_DROP, entity=name if scope == "entity" else "", field=scope,
            field_fa=label, key=name, signature=f"{cur:.0f}|{base:.0f}",
            headline_fa=f"«{label}» در این اجرا {cur:,.0f} است؛ معمولاً حدود {base:,.0f} ({pct:.0f}٪ افت).",
            observed_fa=f"{cur:,.0f}", expected_fa=f"میانه {len(past[-BASELINE_WINDOW:])} اجرای قبل: {base:,.0f}",
            hypotheses=hyps, owner_name="تیم داده — نگاشت سورس", owner_role="مالک قرارداد سورس",
            severity=2.0 + pct / 25.0 + recurrences))
    return out


def _too_good_anomalies(obs: Mapping[str, Any], history: Sequence[Mapping[str, Any]]
                        ) -> List[Anomaly]:
    out: List[Anomaly] = []
    fields = obs.get("fields") or {}
    labels = {c: lbl for c, _e, lbl in _coverage_fields()}
    entity_of = {c: e for c, e, _l in _coverage_fields()}

    # (a) a total that jumped — first rule out counting the same thing twice
    for watch in NUMERIC_WATCHES:
        info = fields.get(watch.column) or {}
        for group, cur in (info.get("totals") or {}).items():
            past = _series(history, "fields", watch.column, "totals", group)
            base = _baseline(past)
            if not base or base <= 0 or cur <= JUMP_RATIO * base:
                continue
            ratio = cur / base
            ent = watch.entity
            rpe_now = (obs.get("rows_per_entity") or {}).get(ent)
            rpe_base = _baseline(_series(history, "rows_per_entity", ent))
            ent_now = (obs.get("entities") or {}).get(ent)
            ent_base = _baseline(_series(history, "entities", ent))
            grain_jump = bool(rpe_now and rpe_base and rpe_now >= 1.3 * rpe_base)
            growth = bool(ent_now and ent_base and ent_now >= 0.8 * ratio * ent_base)
            dc_text = (f"تعداد ردیف به‌ازای هر {ENTITY_FA.get(ent, ent)} هم از {rpe_base:.2f} به "
                       f"{rpe_now:.2f} رسیده — امضای کلاسیک دوباره‌شماری یا ادغام تکراری."
                       if grain_jump else
                       "عددی که ناگهان خیلی بزرگ‌تر یا بهتر شده، اول باید از نظر دوباره‌شماری "
                       "(یک فایل دو بار، یک پرونده با دو کلید) رد شود.")
            hyps = [
                Hypothesis(DOUBLE_COUNT, "دوباره‌شماری", dc_text, STRONG if grain_jump else MEDIUM),
                Hypothesis(REAL_IMPROVEMENT, "رشد واقعی",
                           (f"تعداد {ENTITY_FA.get(ent, ent)} هم هم‌پای جمع بالا رفته، که با رشد واقعی سازگار است."
                            if growth else "تعداد پرونده‌ها هم‌پای این جمع بالا نرفته؛ رشد واقعی کمتر محتمل است."),
                           MEDIUM if growth else WEAK),
            ]
            hyps.sort(key=lambda h: _STRENGTH_RANK[h.strength])
            gl = f" ({group})" if group else ""
            out.append(Anomaly(
                kind=TOO_GOOD, entity=ent, field=watch.column, field_fa=watch.title_fa,
                key=group or "*", signature=f"total:{cur:.2f}",
                headline_fa=f"جمع «{watch.title_fa}»{gl} در یک اجرا {ratio:.1f} برابر شد.",
                observed_fa=fmt_number(cur), expected_fa=f"میانه اجراهای قبل: {fmt_number(base)}",
                hypotheses=hyps, owner_name="تیم داده — نگاشت سورس",
                owner_role="مالک قرارداد سورس", severity=2.5 + math.log10(ratio)))

    # (b) coverage that jumped — first rule out cells filled with a default
    for column, info in fields.items():
        cur = info.get("coverage")
        past = _series(history, "fields", column, "coverage")
        base = _baseline(past)
        if cur is None or base is None or cur - base < COVERAGE_JUMP:
            continue
        top, share = info.get("top", ""), float(info.get("top_share") or 0.0)
        base_share = _baseline(_series(history, "fields", column, "top_share")) or 0.0
        filled_default = share >= 0.5 and share - base_share >= 0.25
        label = labels.get(column, column)
        hyps = [
            Hypothesis(PLACEHOLDER_FILL, "خانه‌ها با یک مقدار پیش‌فرض پر شده‌اند",
                       (f"{share:.0%} مقادیر پرشده یک مقدار تکراری‌اند («{top}») در حالی که قبلاً "
                        f"{base_share:.0%} بود. پرشدنِ واقعی معمولاً مقادیر متنوع می‌سازد."
                        if filled_default else
                        "پیش از جشن‌گرفتن، چند نمونه تازه‌پرشده را با سورس اصلی مقایسه کنید."),
                       STRONG if filled_default else MEDIUM),
            Hypothesis(REAL_IMPROVEMENT, "کارزار تکمیل داده نتیجه داده",
                       "اگر کسی این خانه‌ها را واقعاً پر کرده، اسمش را در توضیح بنویسید — "
                       "این بهبود باید دیده شود.", WEAK if filled_default else MEDIUM),
        ]
        hyps.sort(key=lambda h: _STRENGTH_RANK[h.strength])
        out.append(Anomaly(
            kind=TOO_GOOD, entity=entity_of.get(column, ""), field=column, field_fa=label,
            key="*", signature=f"coverage:{cur:.1f}",
            headline_fa=f"پوشش «{label}» در یک اجرا از {base:.0f}٪ به {cur:.0f}٪ رسید.",
            observed_fa=f"{cur:.0f}٪", expected_fa=f"میانه اجراهای قبل: {base:.0f}٪",
            hypotheses=hyps, owner_name="تیم داده — نگاشت سورس",
            owner_role="مالک قرارداد سورس", severity=2.0 + (cur - base) / 30.0))
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════
def detect(
    df: pd.DataFrame,
    *,
    history: Sequence[Mapping[str, Any]] = (),
    observations: Optional[Mapping[str, Any]] = None,
    numeric_watches: Sequence[NumericWatch] = NUMERIC_WATCHES,
    category_watches: Sequence[CategoryWatch] = CATEGORY_WATCHES,
    limit: int = MAX_ANOMALIES,
) -> List[Anomaly]:
    """Every anomaly in this run, most serious first. Reads; never writes.

    ``history`` is the list of earlier trust summaries (oldest first) as stored
    by ``bridge.trust_snapshot``; entries without ``observations`` are ignored,
    so the detector is correct on day one and gets sharper with every run.
    """
    past = _history_obs(history)
    obs = observations if observations is not None else observe(df)
    found: List[Anomaly] = []
    if df is not None and not df.empty:
        for w in numeric_watches:
            found.extend(_numeric_outliers(df, w))
        for c in category_watches:
            known: set = set()
            for o in past:
                known.update((o.get("categories") or {}).get(c.column) or ())
            found.extend(_category_anomalies(df, c, known or None))
    if past:
        found.extend(_volume_anomalies(obs, past))
        found.extend(_too_good_anomalies(obs, past))

    unique: Dict[str, Anomaly] = {}
    for a in found:
        unique.setdefault(a.id, a)
    ordered = sorted(unique.values(), key=lambda a: (-a.severity, a.kind, a.field, a.key))
    return ordered[:limit] if limit else ordered


__all__ = [
    "VALUE_OUTLIER", "CATEGORY_VARIANT", "NEW_CATEGORY", "VOLUME_DROP", "TOO_GOOD",
    "KIND_FA", "STRONG", "MEDIUM", "WEAK", "STRENGTH_FA", "RESCALE", "ALIAS",
    "NumericWatch", "CategoryWatch", "NUMERIC_WATCHES", "CATEGORY_WATCHES", "NEVER_HEAL",
    "Hypothesis", "Anomaly", "observe", "detect", "category_norm", "fmt_number",
]

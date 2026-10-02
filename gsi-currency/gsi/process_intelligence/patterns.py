# -*- coding: utf-8 -*-
"""Deterministic, auditable event-sequence pattern matching for GSI.

This module borrows *ideas* from clips/pattern's ``pattern.search`` layer:
composable constraints, alternatives/wildcards, optional/repeated constraints,
semantic taxonomies and captured groups.  It deliberately does **not** depend on
``pattern`` itself: that repository is archived, targets an older Python era,
and its NLP taggers do not provide a validated Persian model for GSI.

The matcher operates on already validated GSI event rows.  A match is an
*observation* with source-row lineage; it is never, by itself, a risk score,
violation, SLA breach or automated action.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
import fnmatch
import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

MAX_PATTERNS = 50
MAX_CONSTRAINTS = 12
MAX_TAXONOMY_TERMS = 1000
MAX_MATCHES = 10_000
_VALID_QUANTIFIERS = {"one", "optional", "one_or_more"}
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def _norm(value: object) -> str:
    """Conservative Unicode/whitespace normalization; does not invent synonyms."""
    s = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return " ".join(s.split()).casefold()


@dataclass(frozen=True)
class CompiledConstraint:
    activities: Tuple[str, ...] = ()
    taxonomy: str = ""
    any_activity: bool = False
    exclude_activities: Tuple[str, ...] = ()
    exclude_taxonomy: str = ""
    quantifier: str = "one"
    capture: str = ""


@dataclass(frozen=True)
class CompiledPattern:
    id: str
    label: str
    constraints: Tuple[CompiledConstraint, ...]
    anchor_start: bool = False
    anchor_end: bool = False


class ActivityTaxonomy:
    """Explicit activity taxonomy with optional ``@parent`` references.

    Example::

        {"FX": ["تخصیص ارز", "تامین ارز"],
         "FINANCE": ["@FX", "رفع تعهد"]}

    No classifier is inferred.  Terms only belong to categories that the config
    explicitly names.
    """

    def __init__(self, raw: Mapping[str, Sequence[object]] | None = None):
        self._raw: Dict[str, Tuple[str, ...]] = {}
        self._cache: Dict[str, frozenset[str]] = {}
        raw = raw or {}
        if not isinstance(raw, Mapping):
            raise ValueError("taxonomy must be an object")
        total = 0
        for key, values in raw.items():
            name = str(key).strip()
            if not name or len(name) > 80:
                raise ValueError("Invalid taxonomy name")
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                raise ValueError(f"Taxonomy {name!r} must be a list")
            vals = tuple(str(v).strip() for v in values if str(v).strip())
            total += len(vals)
            self._raw[_norm(name)] = vals
        if total > MAX_TAXONOMY_TERMS:
            raise ValueError("Taxonomy is too large")
        # Eagerly resolve all categories so cycles fail before any analysis.
        for name in list(self._raw):
            self.members(name)

    def members(self, name: object, _stack: Tuple[str, ...] = ()) -> frozenset[str]:
        key = _norm(name)
        if key in self._cache:
            return self._cache[key]
        if key not in self._raw:
            raise ValueError(f"Unknown taxonomy: {name}")
        if key in _stack:
            raise ValueError("Cyclic taxonomy: " + " -> ".join(_stack + (key,)))
        out: set[str] = set()
        for term in self._raw[key]:
            if term.startswith("@"):
                out.update(self.members(term[1:], _stack + (key,)))
            else:
                out.add(_norm(term))
        result = frozenset(out)
        self._cache[key] = result
        return result

    def contains(self, category: object, activity: object) -> bool:
        return _norm(activity) in self.members(category)

    def as_dict(self) -> Dict[str, List[str]]:
        return {k: sorted(self.members(k)) for k in sorted(self._raw)}


def _compile_constraint(raw: Mapping[str, Any]) -> CompiledConstraint:
    if not isinstance(raw, Mapping):
        raise ValueError("Each constraint must be an object")
    activities: List[str] = []
    if "activity" in raw:
        activities.append(str(raw["activity"]))
    if "activities" in raw:
        vals = raw["activities"]
        if not isinstance(vals, Sequence) or isinstance(vals, (str, bytes)):
            raise ValueError("constraint.activities must be a list")
        activities.extend(str(v) for v in vals)
    activities = [v.strip() for v in activities if v.strip()]
    taxonomy = str(raw.get("taxonomy") or "").strip()
    any_activity = bool(raw.get("any", False))
    positive = int(bool(activities)) + int(bool(taxonomy)) + int(any_activity)
    if positive != 1:
        raise ValueError("Constraint needs exactly one of activity/activities, taxonomy, or any=true")
    ex = raw.get("exclude_activities", [])
    if not isinstance(ex, Sequence) or isinstance(ex, (str, bytes)):
        raise ValueError("exclude_activities must be a list")
    quantifier = str(raw.get("quantifier") or "one").strip()
    if quantifier not in _VALID_QUANTIFIERS:
        raise ValueError(f"Unsupported quantifier: {quantifier}")
    capture = str(raw.get("capture") or "").strip()
    if capture and not _ID_RE.match(capture):
        raise ValueError("Invalid capture name")
    return CompiledConstraint(
        activities=tuple(activities),
        taxonomy=taxonomy,
        any_activity=any_activity,
        exclude_activities=tuple(str(v).strip() for v in ex if str(v).strip()),
        exclude_taxonomy=str(raw.get("exclude_taxonomy") or "").strip(),
        quantifier=quantifier,
        capture=capture,
    )


def compile_spec(spec: Mapping[str, Any] | None) -> Tuple[ActivityTaxonomy, Tuple[CompiledPattern, ...]]:
    """Validate and compile a JSON-compatible pattern specification."""
    spec = spec or {}
    if not isinstance(spec, Mapping):
        raise ValueError("Pattern spec must be an object")
    version = int(spec.get("version", 1))
    if version != 1:
        raise ValueError(f"Unsupported pattern spec version: {version}")
    taxonomy = ActivityTaxonomy(spec.get("taxonomy") or {})
    raw_patterns = spec.get("patterns") or []
    if not isinstance(raw_patterns, Sequence) or isinstance(raw_patterns, (str, bytes)):
        raise ValueError("patterns must be a list")
    if len(raw_patterns) > MAX_PATTERNS:
        raise ValueError(f"At most {MAX_PATTERNS} patterns are allowed")
    patterns: List[CompiledPattern] = []
    seen: set[str] = set()
    for raw in raw_patterns:
        if not isinstance(raw, Mapping):
            raise ValueError("Each pattern must be an object")
        pid = str(raw.get("id") or "").strip()
        if not _ID_RE.match(pid):
            raise ValueError("Pattern id must be 1..80 safe ASCII characters")
        if pid in seen:
            raise ValueError(f"Duplicate pattern id: {pid}")
        seen.add(pid)
        label = str(raw.get("label") or pid).strip()
        if not label or len(label) > 200:
            raise ValueError("Invalid pattern label")
        raw_constraints = raw.get("constraints") or []
        if not isinstance(raw_constraints, Sequence) or isinstance(raw_constraints, (str, bytes)):
            raise ValueError("Pattern constraints must be a list")
        if not 1 <= len(raw_constraints) <= MAX_CONSTRAINTS:
            raise ValueError(f"Each pattern needs 1..{MAX_CONSTRAINTS} constraints")
        constraints = tuple(_compile_constraint(c) for c in raw_constraints)
        # Resolve taxonomy references now, not midway through a production run.
        for c in constraints:
            if c.taxonomy:
                taxonomy.members(c.taxonomy)
            if c.exclude_taxonomy:
                taxonomy.members(c.exclude_taxonomy)
        patterns.append(CompiledPattern(
            id=pid,
            label=label,
            constraints=constraints,
            anchor_start=bool(raw.get("anchor_start", False)),
            anchor_end=bool(raw.get("anchor_end", False)),
        ))
    return taxonomy, tuple(patterns)


def load_spec(path: str) -> Dict[str, Any]:
    """Load a small UTF-8 JSON pattern spec from an authorized local path."""
    with open(path, "rb") as fh:
        raw = fh.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Pattern config exceeds 1 MiB")
    obj = json.loads(raw.decode("utf-8"))
    # Compile once here for early validation; caller may compile again in profile.
    compile_spec(obj)
    return obj


def _activity_matches(activity: str, c: CompiledConstraint, taxonomy: ActivityTaxonomy) -> bool:
    a = _norm(activity)
    if c.any_activity:
        ok = True
    elif c.taxonomy:
        ok = taxonomy.contains(c.taxonomy, a)
    else:
        ok = any(fnmatch.fnmatchcase(a, _norm(pattern)) for pattern in c.activities)
    if not ok:
        return False
    if c.exclude_activities and any(fnmatch.fnmatchcase(a, _norm(p)) for p in c.exclude_activities):
        return False
    if c.exclude_taxonomy and taxonomy.contains(c.exclude_taxonomy, a):
        return False
    return True


def _match_constraints(
    activities: Sequence[str],
    constraints: Sequence[CompiledConstraint],
    taxonomy: ActivityTaxonomy,
    ci: int,
    pos: int,
    captures: Mapping[str, Tuple[int, int]],
) -> Tuple[int, Dict[str, Tuple[int, int]]] | None:
    """Greedy recursive matcher over one case's contiguous activity sequence."""
    if ci >= len(constraints):
        return pos, dict(captures)
    c = constraints[ci]

    def with_capture(start: int, end: int, base: Mapping[str, Tuple[int, int]]):
        nxt = dict(base)
        if c.capture:
            nxt[c.capture] = (start, end)
        return nxt

    if c.quantifier == "optional":
        # Pattern-style greedy optional: consume first if it can still finish.
        if pos < len(activities) and _activity_matches(activities[pos], c, taxonomy):
            hit = _match_constraints(activities, constraints, taxonomy, ci + 1, pos + 1,
                                     with_capture(pos, pos + 1, captures))
            if hit is not None:
                return hit
        return _match_constraints(activities, constraints, taxonomy, ci + 1, pos, captures)

    if c.quantifier == "one_or_more":
        end = pos
        while end < len(activities) and _activity_matches(activities[end], c, taxonomy):
            end += 1
        # Greedy but backtrack if later constraints require a shorter run.
        for stop in range(end, pos, -1):
            hit = _match_constraints(activities, constraints, taxonomy, ci + 1, stop,
                                     with_capture(pos, stop, captures))
            if hit is not None:
                return hit
        return None

    if pos >= len(activities) or not _activity_matches(activities[pos], c, taxonomy):
        return None
    return _match_constraints(activities, constraints, taxonomy, ci + 1, pos + 1,
                              with_capture(pos, pos + 1, captures))


def match_cases(rows: Sequence[Mapping[str, Any]], spec: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Match configured patterns against validated event rows grouped by case.

    ``rows`` must contain ``_CASE_KEY``, ``ACTIVITY_FA`` and ``source_row`` and
    must already be in deterministic event order.
    """
    taxonomy, patterns = compile_spec(spec)
    if not patterns:
        return {
            "enabled": False,
            "status": "disabled",
            "pattern_count": 0,
            "summary": [],
            "matches": [],
            "note": "هیچ الگوی صریحی فعال نیست؛ سیستم از روی متن یا مسیر، ریسک/تخلف حدس نمی‌زند.",
        }

    by_case: MutableMapping[str, List[Mapping[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(str(row["_CASE_KEY"]), []).append(row)

    matches: List[Dict[str, Any]] = []
    summary: Dict[str, Dict[str, Any]] = {
        p.id: {"id": p.id, "label": p.label, "match_count": 0, "unique_cases": set()}
        for p in patterns
    }
    for case_key, seq in by_case.items():
        activities = [str(r["ACTIVITY_FA"]) for r in seq]
        for pattern in patterns:
            starts: Iterable[int] = (0,) if pattern.anchor_start else range(len(activities))
            for start in starts:
                hit = _match_constraints(activities, pattern.constraints, taxonomy, 0, start, {})
                if hit is None:
                    continue
                end, captures = hit
                if pattern.anchor_end and end != len(activities):
                    continue
                if end <= start:
                    continue
                captured = {}
                for name, (a, b) in captures.items():
                    captured[name] = {
                        "activities": activities[a:b],
                        "source_rows": [int(seq[i]["source_row"]) for i in range(a, b)],
                    }
                rec = {
                    "pattern_id": pattern.id,
                    "pattern_label": pattern.label,
                    "case_key": case_key,
                    "start_index": start,
                    "end_index": end - 1,
                    "activities": activities[start:end],
                    "source_rows": [int(seq[i]["source_row"]) for i in range(start, end)],
                    "captures": captured,
                }
                matches.append(rec)
                s = summary[pattern.id]
                s["match_count"] += 1
                s["unique_cases"].add(case_key)
                if len(matches) > MAX_MATCHES:
                    raise ValueError(f"Pattern matches exceed {MAX_MATCHES}; narrow the scope or rules")

    clean_summary = []
    for pattern in patterns:
        s = summary[pattern.id]
        clean_summary.append({
            "id": s["id"], "label": s["label"],
            "match_count": int(s["match_count"]),
            "unique_cases": len(s["unique_cases"]),
        })
    return {
        "enabled": True,
        "status": "observational_only",
        "pattern_count": len(patterns),
        "taxonomy": taxonomy.as_dict(),
        "summary": clean_summary,
        "matches": matches,
        "note": "تطبیق الگو فقط مشاهدهٔ قابل‌ردیابی است؛ به‌تنهایی هشدار، ریسک، تخلف یا SLA محسوب نمی‌شود.",
    }

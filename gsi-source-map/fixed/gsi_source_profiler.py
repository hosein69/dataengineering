#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GSI Source Profiler — reviewed build.

Drop-in replacement for the upstream tool: same CLI, same output filenames.
Changes are limited to the profiler itself; see MAP_DEFECTS.md for the evidence
behind each one (M-01 … M-14).

Design rules kept from upstream:
  * a co-observed pair is never presented as an authoritative join;
  * sampling is information-targeted, not statistical;
  * every emitted file is hashed into a manifest.

Design rules added here:
  * a column that carries a measure (date/amount/quantity/currency/status)
    can never also be a business key;
  * role families resolve most-specific-first, so a registration FILE number
    never wins the REG role and a purchasing document never wins ORDER;
  * Persian/Arabic text is normalised for comparison only — raw values are
    always what gets written out;
  * a source that fails to profile is loud, in every output, and the process
    exits non-zero.
"""
from __future__ import annotations

import argparse, hashlib, json, os, re, sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
try:
    import yaml
except ImportError:
    yaml = None

TOOL_VERSION = "2.0.0-reviewed"

# ─────────────────────────── text normalisation (M-04) ───────────────────────
# Comparison-only. Nothing written to the pack is rewritten by these.
_FA_CHARS = str.maketrans({
    "ي": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "آ": "ا",
    "ؤ": "و", "ئ": "ی", "\u200c": " ", "\u200f": "", "\u200e": "", "\u0640": "",
})
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
TEXT_NULLS = {"", "nan", "none", "null", "nat", "<na>", "n/a", "-", "--"}


def norm_text(v: Any) -> str:
    """Whitespace-collapsed display form. Keeps the original characters."""
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v).strip())


def norm_key(v: Any) -> str:
    """Comparison form: Persian/Arabic variants and digits folded together.

    ي/ی, ك/ک, ة/ه, ZWNJ, tatweel and Arabic-Indic digits all collapse, so one
    business status is one bucket and one key counts once.
    """
    s = norm_text(v)
    if not s:
        return ""
    return s.translate(_FA_CHARS).translate(_FA_DIGITS).casefold().strip()


def norm_col(v: Any) -> str:
    s = norm_key(v)
    return re.sub(r"[_()\[\]{}«»\"'،,]+", " ", s).strip()


def is_blank(v: Any) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return norm_key(v) in TEXT_NULLS


def blank_mask(s: pd.Series) -> pd.Series:
    """Vectorised is_blank over a Series (M-14)."""
    t = s.astype(object).map(norm_key)
    return s.isna() | t.isin(TEXT_NULLS)


# ─────────────────────────── role model (M-02) ───────────────────────────────
# Measures veto keys. A date, an amount, a quantity, a currency or a status is
# never a business key, however its header is spelled.
MEASURE_RULES: list[tuple[str, list[str], list[str]]] = [
    ("DATE", [r"\bdate\b", r"changed on", r"created on", r"تاریخ", r"مهلت", r"زمان"], []),
    ("STATUS", [r"\bstatus\b", r"\bstate\b", r"deletion indicator", r"overall release",
                r"release strategy", r"وضعیت", r"مرحله", r"فرآیند فعلی"],
     [r"\bdate\b", r"تاریخ"]),
    ("AMOUNT", [r"\bamount\b", r"\bvalue\b", r"\bprice\b", r"\bbalance\b",
                r"مبلغ", r"ارزش", r"بها", r"مانده", r"تعهد اولیه", r"نرخ"],
     [r"\bdate\b", r"تاریخ"]),
    ("QUANTITY", [r"\bquantity\b", r"\bqty\b", r"مقدار", r"تعداد", r"موجودی", r"نیاز روزانه"],
     [r"\bdate\b", r"تاریخ"]),
    ("CURRENCY", [r"\bcurrency\b", r"نوع ارز", r"ارز درخواست", r"^ارز$", r"کد ارز"], []),
]

# Key roles, most specific first. The first match wins, so REG_FILE cannot be
# taken for REG and a purchasing document cannot be taken for a commercial order.
KEY_RULES: list[tuple[str, list[str], list[str]]] = [
    ("PR_ITEM", [r"item of requisition", r"\bpr[ _]?item\b", r"آیتم درخواست"], []),
    ("PO_ITEM", [r"purchase order item", r"\bpo[ _.]?item\b", r"\bdocument item\b"],
     [r"item of requisition"]),
    ("PR", [r"purchase requisition", r"\bpurch\.? req", r"\bpr\b",
            r"درخواست خرید", r"شماره درخواست"], [r"item", r"قلم", r"آیتم"]),
    ("PO", [r"purchasing document", r"purchase order", r"\bpo\b", r"سفارش خرید"],
     [r"item", r"\bvalue\b", r"\bprice\b", r"\bdate\b", r"\bcurrency\b",
      r"\bquantity\b", r"\bqty\b", r"\bunit\b", r"material", r"supplier",
      r"پرونده", r"تاریخ", r"مبلغ", r"ارزش"]),
    # Registration FILE number is 9+ digits and is NOT the 8-digit registration
    # code. gsi/config/sources.yaml records that confusing the two is why NTSW
    # never connected in an earlier release.
    ("REG_FILE", [r"شماره پرونده ثبت سفارش", r"پرونده ثبت سفارش", r"reg[ _]?file",
                  r"registration file"], [r"ترخیص", r"clearance"]),
    ("CUSTOMS_FILE", [r"پرونده ترخیص", r"clearance file"], []),
    ("REG", [r"کد ثبت سفارش", r"شماره ثبت سفارش", r"ثبت سفارش", r"\breg\b",
             r"registration"], [r"پرونده", r"file", r"\bdate\b", r"تاریخ"]),
    ("ORDER", [r"order no", r"order number", r"our reference", r"شماره سفارش",
               r"سفارش خارجی", r"\border\b"],
     [r"purchase order", r"purchasing", r"^po[ _.]", r"\bvalue\b", r"\bprice\b",
      r"\bamount\b", r"\bquantity\b", r"\bqty\b", r"\bunit\b", r"\bdate\b",
      r"\btype\b", r"\bstatus\b", r"سفارش خرید", r"ثبت سفارش", r"مقدار",
      r"تعداد", r"ارزش", r"مبلغ"]),
    ("BL", [r"bill of lading", r"شماره بارنامه", r"بارنامه", r"\bbl\b", r"\bawb\b"],
     [r"\bdate\b", r"تاریخ", r"\bstatus\b", r"وضعیت"]),
    ("COTTAGE", [r"\bcottage\b", r"\bcotage\b", r"کوتاژ", r"اظهارنامه"],
     [r"\bdate\b", r"تاریخ"]),
    ("MATERIAL", [r"\bmaterial\b", r"material code", r"کد کالا", r"کد قطعه",
                  r"شماره فنی", r"part no", r"part number", r"\bmpn\b"],
     [r"description", r"\bdesc\b", r"\bgroup\b", r"\btext\b", r"\bprofile\b",
      r"شرح", r"گروه", r"supplier", r"\bstatus\b"]),
    ("SUPPLIER", [r"\bsupplier\b", r"\bvendor\b", r"فروشنده", r"تامین کننده"],
     [r"\bmat\b", r"material", r"\bcode\b", r"\bno\.?$", r"کد", r"\bname\b", r"نام"]),
    ("WORKFLOW", [r"workflow", r"work flow", r"گردش کار"], [r"\bstatus\b", r"وضعیت"]),
    ("COMPARISON", [r"comparision id", r"comparison id", r"شماره مقایسه"], []),
    # Native line identifiers: the obligation/request line the business names.
    # Whether a repeated one means a new obligation or the same one re-observed
    # in a later snapshot is the open question these columns exist to answer,
    # so they must never be confused with a plain export sequence number.
    ("NATIVE_ROW_ID", [r"شماره ردیف تعهد", r"ردیف درخواست", r"\bline no\b"], []),
    # A bare sequence number is export metadata, not a business identifier.
    # Kept as its own role so it is visible but never joins or defines a grain.
    ("EXPORT_ROW_NO", [r"^ردیف$", r"^row$", r"\brow no\b", r"\bseq\b",
                       r"^#$", r"^no$", r"^ردیف ?$"], []),
]
#: Roles that identify a row inside one export but carry no business meaning.
NON_BUSINESS_KEY_ROLES = {"EXPORT_ROW_NO"}
KEY_ROLES = [r[0] for r in KEY_RULES]
MEASURE_ROLES = [r[0] for r in MEASURE_RULES]


def _matches(name_norm: str, positives: Iterable[str], negatives: Iterable[str]) -> bool:
    if any(re.search(p, name_norm, flags=re.I) for p in negatives):
        return False
    return any(re.search(p, name_norm, flags=re.I) for p in positives)


def column_side(name: str) -> str:
    """Which grain of a multi-grain export a column belongs to.

    A completed SAP row can carry PR-item, package and PO-item attributes at
    once; the prefix is the only thing that says which is which.
    """
    n = norm_col(name)
    if n.startswith("po ") or n.startswith("po."):
        return "po"
    if n.startswith("pack ") or n.startswith("pack."):
        return "pack"
    return "header"


def classify_column(name: str) -> dict[str, Any]:
    n = norm_col(name)
    measures = [role for role, pos, neg in MEASURE_RULES if _matches(n, pos, neg)]
    key_role = None
    if not measures:                       # a measure is never a key (M-02)
        for role, pos, neg in KEY_RULES:
            if _matches(n, pos, neg):
                key_role = role
                break
    roles = ([key_role] if key_role else []) + measures
    return {"key_role": key_role, "measure_roles": measures, "roles": roles,
            "side": column_side(name)}


def semantic_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for c in df.columns:
        for role in classify_column(str(c))["roles"]:
            out.setdefault(role, []).append(str(c))
    return out


# ─────────────────────────── stats & key selection ───────────────────────────
@dataclass
class SourceSpec:
    name: str
    path: str
    sheets: Any = "all"
    domain: str = ""
    authority: str = ""
    required: bool = False
    notes: str = ""


def load_config(path: Path) -> list[SourceSpec]:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    allowed = set(SourceSpec.__dataclass_fields__)
    specs, seen = [], set()
    for i, x in enumerate(data.get("sources", []), 1):
        if not isinstance(x, dict):
            raise ValueError(f"sources[{i}] must be a mapping, got {type(x).__name__}")
        unknown = sorted(set(x) - allowed)                                    # M-12
        if unknown:
            raise ValueError(f"sources[{i}] ({x.get('name','?')}): unknown key(s) "
                             f"{unknown}; allowed: {sorted(allowed)}")
        if "name" not in x or "path" not in x:
            raise ValueError(f"sources[{i}]: 'name' and 'path' are required")
        key = str(x["name"]).strip().casefold()
        if key in seen:                                                        # M-11
            raise ValueError(f"duplicate source name {x['name']!r}; output files "
                             f"would overwrite each other")
        seen.add(key)
        specs.append(SourceSpec(**x))
    if not specs:
        raise ValueError("config declares no sources")
    return specs


def safe_slug(s: str) -> str:
    return (re.sub(r"[^\w\-.]+", "_", s, flags=re.UNICODE).strip("_") or "unnamed")[:120]


def read_table(path: Path, sheet: Optional[str] = None) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xlsm", ".xls"}:
        df = pd.read_excel(path, sheet_name=sheet, dtype=object)
        if isinstance(df, dict):            # sheet_name=None returns a mapping
            df = next(iter(df.values())) if df else pd.DataFrame()
        return df
    if ext == ".csv":
        last = None
        for enc in ("utf-8-sig", "utf-8", "cp1256", "latin1"):
            try:
                return pd.read_csv(path, dtype=object, encoding=enc, low_memory=False)
            except Exception as e:
                last = e
        raise last
    if ext in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def workbook_sheets(path: Path) -> list[Optional[str]]:
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        with pd.ExcelFile(path) as xl:
            return list(xl.sheet_names)
    return [None]


def selected_sheets(spec: SourceSpec, path: Path) -> tuple[list[Optional[str]], list[str]]:
    available = workbook_sheets(path)
    if spec.sheets in (None, "all", ["all"]):
        return available, []
    wanted = spec.sheets if isinstance(spec.sheets, list) else [spec.sheets]
    chosen = [x for x in available if x in wanted]
    missing = [str(w) for w in wanted if w not in available]   # never silent
    return chosen, missing


def series_stats(s: pd.Series) -> dict[str, Any]:
    n = len(s)
    non_null = s[~blank_mask(s)]
    nunique = int(non_null.map(norm_key).nunique()) if len(non_null) else 0
    return {"rows": int(n), "non_null": int(len(non_null)), "nulls": int(n - len(non_null)),
            "null_pct": round((n - len(non_null)) / n * 100, 2) if n else 0,
            "unique": nunique,
            "unique_pct_of_non_null": round(nunique / len(non_null) * 100, 2) if len(non_null) else 0,
            "examples": [norm_text(x) for x in non_null.head(5).tolist()]}


def candidate_key_score(s: pd.Series) -> float:
    st = series_stats(s)
    if not st["non_null"]:
        return 0.0
    return round(0.65 * (st["unique_pct_of_non_null"] / 100)
                 + 0.35 * (st["non_null"] / max(st["rows"], 1)), 4)


def representative_key_columns(df: pd.DataFrame, sem: dict[str, list[str]]) -> dict[str, str]:
    """Best key column per role, by evidence rather than by column order (M-03).

    Ranked on coverage first (a key you can actually join on) then uniqueness,
    so a sparse-but-unique column cannot displace the real key.
    """
    chosen: dict[str, str] = {}
    for role in KEY_ROLES:
        best, best_rank = None, None
        for c in sem.get(role, []):
            if c not in df.columns:
                continue
            st = series_stats(df[c])
            cov = st["non_null"] / max(st["rows"], 1)
            rank = (round(cov, 3), st["unique_pct_of_non_null"], -len(str(c)))
            if best_rank is None or rank > best_rank:
                best, best_rank = c, rank
        if best is not None:
            chosen[role] = best
    return chosen


def status_profile(df: pd.DataFrame, cols: list[str], topn: int = 20) -> dict[str, Any]:
    """Frequency per status column, grouped on the normalised form (M-04).

    The raw spellings that fold together are listed, so a Persian/Arabic variant
    is visible as a data-entry fact instead of silently becoming two statuses.
    """
    out: dict[str, Any] = {}
    for c in cols:
        if c not in df.columns:
            continue
        s = df[c][~blank_mask(df[c])]
        if s.empty:
            out[c] = []
            continue
        raw = s.map(norm_text)
        key = s.map(norm_key)
        rows = []
        for k, cnt in key.value_counts().head(topn).items():
            variants = sorted(set(raw[key.eq(k)].tolist()))
            rows.append({"value": variants[0], "normalised": str(k), "count": int(cnt),
                         "raw_variants": variants if len(variants) > 1 else []})
        out[c] = rows
    return out


# ─────────────────────────── sampling ────────────────────────────────────────
def _info_scores(df: pd.DataFrame, sem: dict[str, list[str]]) -> pd.Series:
    """Vectorised replacement for the per-row apply (M-14)."""
    score = pd.Series(0.0, index=df.index)
    for role in KEY_ROLES:
        cols = [c for c in sem.get(role, []) if c in df.columns]
        if not cols:
            continue
        present = pd.Series(False, index=df.index)
        for c in cols:
            present |= ~blank_mask(df[c])
        score += present.astype(float) * 3.0
    for c in (c for c in sem.get("STATUS", []) if c in df.columns):
        score += (~blank_mask(df[c])).astype(float) * 2.0
    for role, w in (("DATE", 1.2), ("AMOUNT", 1.5), ("CURRENCY", 1.3), ("QUANTITY", 1.0)):
        for c in (c for c in sem.get(role, []) if c in df.columns):
            score += (~blank_mask(df[c])).astype(float) * w
    filled = pd.Series(0, index=df.index)
    for c in df.columns:
        filled += (~blank_mask(df[c])).astype(int)
    return score + filled.clip(upper=30) * 0.03


def select_representative_rows(df: pd.DataFrame, sem: dict[str, list[str]],
                               keys: dict[str, str], max_rows: int = 18,
                               header_rows: int = 1, source_file: str = "",
                               sheet: str = "", seed: int = 42) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    scores = _info_scores(df, sem)
    chosen: list[Any] = []

    def add(i):
        if i not in chosen:
            chosen.append(i)

    for i in scores.sort_values(ascending=False).head(max(4, max_rows // 3)).index:
        add(i)
    used = 0
    for c in (c for c in sem.get("STATUS", []) if c in df.columns):
        vals = df[c].map(norm_key)
        for val in vals.value_counts().head(8).index.tolist():
            if not val or val in TEXT_NULLS:
                continue
            idxs = df.index[vals.eq(val)]
            if len(idxs):
                add(scores.loc[idxs].idxmax())
                used += 1
                if used >= max(3, max_rows // 3):
                    break
        if used >= max(3, max_rows // 3):
            break
    for role in ("PR", "ORDER", "REG", "REG_FILE", "MATERIAL", "PO"):
        c = keys.get(role)
        if not c:
            continue
        s = df[c].map(norm_key)
        valid = s[~s.isin(TEXT_NULLS)]
        if valid.empty:
            continue
        vc = valid.value_counts()
        for key in vc[vc > 1].head(4).index:      # fan-out / repeated-key rows
            idxs = df.index[s.eq(key)]
            for i in scores.loc[idxs].sort_values(ascending=False).head(2).index:
                add(i)
    key_cols = [c for c in dict.fromkeys(keys.values()) if c in df.columns]
    if key_cols:
        blanks = pd.Series(0, index=df.index)
        for c in key_cols:
            blanks += blank_mask(df[c]).astype(int)
        add(blanks.idxmax())                      # a gap row, so gaps are visible
    remaining = [i for i in df.index if i not in chosen]
    need = max_rows - len(chosen)
    if need > 0 and remaining:
        for i in df.loc[remaining].sample(n=min(need, len(remaining)), random_state=seed).index:
            add(i)
    out = df.loc[chosen[:max_rows]].copy()
    # Provenance the reader can follow back into the workbook (M-07).
    out.insert(0, "__sheet__", sheet)
    out.insert(0, "__source_file__", source_file)
    out.insert(0, "__excel_row__", [int(df.index.get_loc(i)) + 1 + header_rows
                                    for i in out.index])
    out.insert(0, "__frame_row_index__", [str(i) for i in out.index])
    return out


# ─────────────────────────── grain, relations, duplicates ────────────────────
MIN_GRAIN_COVERAGE = 0.30       # M-06: a candidate seen on a handful of rows is not a grain


def infer_grain(df: pd.DataFrame, keys: dict[str, str]) -> dict[str, Any]:
    role_sets = [("PR_ITEM", ["PR", "PR_ITEM"]), ("PO_ITEM", ["PO", "PO_ITEM"]),
                 ("ORDER_MATERIAL", ["ORDER", "MATERIAL"]), ("ORDER_REG", ["ORDER", "REG"]),
                 ("ORDER_BL", ["ORDER", "BL"]), ("REG_FILE_REG", ["REG_FILE", "REG"]),
                 ("REG_NATIVE_ROW", ["REG", "NATIVE_ROW_ID"]),
                 ("REG_FILE_ORDER", ["REG_FILE", "ORDER"]),
                 ("REG", ["REG"]), ("ORDER", ["ORDER"]), ("PR", ["PR"]),
                 ("PO", ["PO"]), ("MATERIAL", ["MATERIAL"]), ("BL", ["BL"])]
    total = len(df)
    candidates = []
    for label, roles in role_sets:
        cols = [keys.get(r) for r in roles]
        if any(c is None for c in cols) or len(set(cols)) != len(cols):
            continue                                   # M-01: never the same column twice
        x = pd.DataFrame({c: df[c].map(norm_key) for c in cols})
        keep = pd.Series(True, index=x.index)
        for c in cols:
            keep &= ~x[c].isin(TEXT_NULLS)
        x = x[keep]
        if x.empty:
            continue
        uniq = int(x.drop_duplicates().shape[0])
        coverage = round(len(x) / total, 4) if total else 0.0
        candidates.append({"label": label, "columns": cols, "non_null_rows": int(len(x)),
                           "distinct_keys": uniq,
                           "uniqueness_ratio": round(uniq / len(x), 4),
                           "coverage_of_frame": coverage,
                           "repeated_key_rows": int(len(x) - uniq),
                           "eligible": coverage >= MIN_GRAIN_COVERAGE})
    eligible = [c for c in candidates if c["eligible"]]
    eligible.sort(key=lambda c: (c["uniqueness_ratio"], c["coverage_of_frame"]), reverse=True)
    candidates.sort(key=lambda c: (c["eligible"], c["uniqueness_ratio"], c["coverage_of_frame"]),
                    reverse=True)
    return {"best_candidate": eligible[0] if eligible else None,
            "candidates": candidates[:10],
            "min_coverage_required": MIN_GRAIN_COVERAGE,
            "note": "Heuristic. A candidate below the coverage threshold is reported but "
                    "never named best. Confirm against the source contract before use."}


def relation_examples(df: pd.DataFrame, sem: dict[str, list[str]],
                      keys: dict[str, str], limit: int = 12) -> list[dict[str, Any]]:
    """Co-observation between every pair of key columns, not just the first (M-09)."""
    pairs = [("PR", "PO"), ("PR", "ORDER"), ("PR", "MATERIAL"), ("PR", "PR_ITEM"),
             ("PO", "MATERIAL"), ("PO", "PO_ITEM"), ("ORDER", "REG"), ("ORDER", "BL"),
             ("ORDER", "MATERIAL"), ("REG", "REG_FILE"), ("REG", "NATIVE_ROW_ID"),
             ("REG", "COTTAGE"), ("BL", "COTTAGE"), ("BL", "CUSTOMS_FILE")]
    out = []
    for a, b in pairs:
        for ca in dict.fromkeys(c for c in sem.get(a, []) if c in df.columns):
            for cb in dict.fromkeys(c for c in sem.get(b, []) if c in df.columns):
                if ca == cb:
                    continue                                   # M-01
                x = pd.DataFrame({"a": df[ca].map(norm_key), "b": df[cb].map(norm_key),
                                  "a_raw": df[ca].map(norm_text), "b_raw": df[cb].map(norm_text)})
                x = x[~x["a"].isin(TEXT_NULLS) & ~x["b"].isin(TEXT_NULLS)]
                x = x.drop_duplicates(subset=["a", "b"])
                if x.empty:
                    continue
                a2b = x.groupby("a")["b"].nunique()
                b2a = x.groupby("b")["a"].nunique()
                out.append({
                    "from_role": a, "to_role": b, "from_column": ca, "to_column": cb,
                    "from_side": column_side(ca), "to_side": column_side(cb),
                    "is_primary_pair": ca == keys.get(a) and cb == keys.get(b),
                    "distinct_pairs": int(len(x)),
                    "max_to_per_from": int(a2b.max()), "max_from_per_to": int(b2a.max()),
                    "cardinality": ("1:1" if a2b.max() == 1 and b2a.max() == 1 else
                                    "1:N" if b2a.max() == 1 else
                                    "N:1" if a2b.max() == 1 else "N:M"),
                    "many_from_examples": [{"key": str(k), "linked_count": int(v)}
                                           for k, v in a2b[a2b > 1].sort_values(ascending=False).head(5).items()],
                    "examples": x[["a_raw", "b_raw"]].head(limit)
                                 .rename(columns={"a_raw": ca, "b_raw": cb}).to_dict("records"),
                    "assertion": "co-observed in the same native source row; not proof of a "
                                 "causal or authoritative relation",
                })
    return out


def key_conflicts(df: pd.DataFrame, sem: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Two columns claiming the same role but disagreeing on the same row.

    This is the detector for the header-PR vs po.Purchase Requisition problem:
    treating them as one key fabricates a PR/PO lineage that no source row shows.
    """
    out = []
    for role in KEY_ROLES:
        cols = [c for c in dict.fromkeys(sem.get(role, [])) if c in df.columns]
        for i, ca in enumerate(cols):
            for cb in cols[i + 1:]:
                a, b = df[ca].map(norm_key), df[cb].map(norm_key)
                both = ~a.isin(TEXT_NULLS) & ~b.isin(TEXT_NULLS)
                if not both.any():
                    continue
                differ = both & a.ne(b)
                if not differ.any():
                    continue
                ex = pd.DataFrame({ca: df.loc[differ, ca].map(norm_text),
                                   cb: df.loc[differ, cb].map(norm_text)}).head(5)
                out.append({
                    "role": role, "column_a": ca, "column_b": cb,
                    "side_a": column_side(ca), "side_b": column_side(cb),
                    "rows_both_present": int(both.sum()),
                    "rows_disagreeing": int(differ.sum()),
                    "disagreement_pct": round(int(differ.sum()) / int(both.sum()) * 100, 2),
                    "examples": ex.to_dict("records"),
                    "assertion": "same role, different value on the same native row; these are "
                                 "not interchangeable keys until the source owner says so",
                })
    return out


def duplicate_profile(df: pd.DataFrame, keys: dict[str, str],
                      grain: dict[str, Any]) -> dict[str, Any]:
    """Single-column and composite repeated-key signals (M-08)."""
    single = []
    for role in ("PR", "PO", "ORDER", "REG", "REG_FILE", "BL", "MATERIAL", "COTTAGE"):
        c = keys.get(role)
        if not c:
            continue
        s = df[c].map(norm_key)
        s = s[~s.isin(TEXT_NULLS)]
        if s.empty:
            continue
        dup = s.duplicated(keep=False)
        if dup.any():
            counts = s[dup].value_counts().head(10)
            single.append({"role": role, "column": c, "duplicate_rows": int(dup.sum()),
                           "examples": [{"key": str(k), "count": int(v)} for k, v in counts.items()]})
    composite = []
    for cand in grain.get("candidates", []):
        cols = cand["columns"]
        if len(cols) < 2 or cand["repeated_key_rows"] <= 0:
            continue
        x = pd.DataFrame({c: df[c].map(norm_key) for c in cols})
        keep = pd.Series(True, index=x.index)
        for c in cols:
            keep &= ~x[c].isin(TEXT_NULLS)
        x = x[keep]
        dup = x.duplicated(keep=False)
        if not dup.any():
            continue
        grp = x[dup].groupby(cols).size().sort_values(ascending=False).head(5)
        composite.append({
            "grain_label": cand["label"], "columns": cols,
            "duplicate_rows": int(dup.sum()),
            "examples": [{"key": " | ".join(str(v) for v in (k if isinstance(k, tuple) else (k,))),
                          "count": int(v)} for k, v in grp.items()],
            "question": "repeated composite key: a second business event, or the same record "
                        "re-observed in a later snapshot? the source owner decides",
        })
    return {"single_column": single, "composite_grain": composite}


# ─────────────────────────── per-frame profile ───────────────────────────────
def profile_frame(spec: SourceSpec, path: Path, sheet: Optional[str], df: pd.DataFrame,
                  sample_rows: int, out: Path, written: list[Path]) -> dict[str, Any]:
    sem = semantic_columns(df)
    keys = representative_key_columns(df, sem)
    schema = []
    for c in df.columns:
        cls = classify_column(str(c))
        schema.append({"column": str(c), "key_role": cls["key_role"],
                       "measure_roles": cls["measure_roles"], "roles": sorted(cls["roles"]),
                       "side": cls["side"], "dtype": str(df[c].dtype),
                       "is_representative_key": str(c) in set(keys.values()),
                       "candidate_key_score": candidate_key_score(df[c]), **series_stats(df[c])})
    grain = infer_grain(df, keys)
    label = sheet if sheet is not None else "table"
    stem = f"{safe_slug(spec.name)}__{safe_slug(label)}"
    (out / "samples").mkdir(parents=True, exist_ok=True)
    (out / "schemas").mkdir(parents=True, exist_ok=True)
    sample = select_representative_rows(df, sem, keys, sample_rows,
                                        source_file=path.name, sheet=str(label))
    sp = out / "samples" / f"{stem}__sample.csv"
    sample.to_csv(sp, index=False, encoding="utf-8-sig")
    written.append(sp)
    shp = out / "schemas" / f"{stem}__schema.json"
    shp.write_text(json.dumps({"source": spec.name, "sheet": label, "row_count": int(len(df)),
                               "column_count": int(len(df.columns)), "columns": schema},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(shp)
    unclassified = [str(c) for c in df.columns if not classify_column(str(c))["roles"]]
    return {"source": spec.name, "path": str(path), "sheet": label, "domain": spec.domain,
            "authority": spec.authority, "required": spec.required, "notes": spec.notes,
            "row_count": int(len(df)), "column_count": int(len(df.columns)),
            "headers": [str(c) for c in df.columns], "semantic_columns": sem,
            "representative_keys": keys, "unclassified_columns": unclassified,
            "grain_inference": grain,
            "status_profile": status_profile(df, sem.get("STATUS", [])),
            "duplicate_profile": duplicate_profile(df, keys, grain),
            "key_conflicts": key_conflicts(df, sem),
            "relation_examples": relation_examples(df, sem, keys),
            "candidate_keys": sorted([{"column": x["column"], "score": x["candidate_key_score"],
                                       "key_role": x["key_role"], "side": x["side"]}
                                      for x in schema if x["candidate_key_score"] >= 0.80],
                                     key=lambda x: x["score"], reverse=True)[:15],
            "sample_file": str(sp.relative_to(out)), "schema_file": str(shp.relative_to(out))}


def build_global_key_index(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-source role map built from representative keys only.

    Upstream listed every column that matched a role, so a money column and a
    quantity column were published as ORDER keys joinable across sources.
    """
    idx: dict[str, list[dict[str, Any]]] = {}
    for p in profiles:
        for role, col in p.get("representative_keys", {}).items():
            if role in NON_BUSINESS_KEY_ROLES:
                continue                       # an export sequence number joins nothing
            idx.setdefault(role, []).append({
                "source": p["source"], "sheet": p["sheet"], "column": col,
                "side": column_side(col), "authority": p.get("authority", ""),
                "domain": p.get("domain", "")})
    secondary: dict[str, list[dict[str, Any]]] = {}
    for p in profiles:
        primary = set(p.get("representative_keys", {}).values())
        for role, cols in p.get("semantic_columns", {}).items():
            if role not in KEY_ROLES:
                continue
            for c in cols:
                if c not in primary:
                    secondary.setdefault(role, []).append(
                        {"source": p["source"], "sheet": p["sheet"], "column": c,
                         "side": column_side(c)})
    return {"roles": idx, "secondary_role_columns": secondary,
            "candidate_cross_source_join_roles": sorted(k for k, v in idx.items() if len(v) >= 2),
            "warning": "A shared role is a join CANDIDATE only. Comparability must be confirmed "
                       "per field; identical role names do not make two identifiers the same "
                       "business entity."}


# ─────────────────────────── reporting ───────────────────────────────────────
def md_table(rows, cols):
    if not rows:
        return "_None detected._"
    esc = lambda x: str(x).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(esc(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def coverage_table(coverage: list[dict[str, Any]]) -> str:
    return md_table([{"Source": c["source"], "Status": c["status"],
                      "Frames": c.get("frames", 0), "Rows": f"{c.get('rows',0):,}",
                      "Detail": c.get("detail", "")} for c in coverage],
                    ["Source", "Status", "Frames", "Rows", "Detail"])


def build_markdown(profiles, key_index, cfg, coverage, errors) -> str:
    ok = [c for c in coverage if c["status"] == "PROFILED"]
    bad = [c for c in coverage if c["status"] != "PROFILED"]
    lines = ["# GSI Model Context Evidence Pack", "",
             f"Generated: {datetime.now().isoformat(timespec='seconds')} · tool `{TOOL_VERSION}`",
             f"Config: `{cfg}`", ""]
    if bad:                                                     # M-05: impossible to miss
        lines += ["> ## ⛔ INCOMPLETE EVIDENCE PACK", ">",
                  f"> **{len(bad)} of {len(coverage)} configured sources produced no evidence.** "
                  "Any conclusion drawn from this pack is scoped to the sources listed as "
                  "PROFILED below. Absence here is a gap in the pack, not a fact about the business.",
                  ">"]
        for c in bad:
            lines.append(f"> - **{c['source']}** — {c['status']}: {c.get('detail','')}")
        lines.append("")
    lines += ["## Source coverage", "", coverage_table(coverage), "",
              "## Interpretation rules", "",
              "- Samples maximise process/key/status coverage; they are not statistical samples.",
              "- Grain and relation findings are heuristic unless confirmed by contracts or code.",
              "- Co-observed keys are not automatically authoritative joins.",
              "- Missing evidence must not be read as proof that a process step did not occur.",
              "- A column carrying a date, amount, quantity, currency or status is never treated "
              "as a business key.",
              "- Persian/Arabic spellings and digits are folded for counting only; every value "
              "printed is the raw source value.", "",
              "## Cross-source key map", "",
              "_Representative key column per role per frame. Secondary columns that share a role "
              "are listed in `process_key_index.json` under `secondary_role_columns` and are "
              "deliberately kept out of the join map._", ""]
    rows = [{"Role": role, "Frames": len(refs),
             "Sources": ", ".join(sorted({r["source"] for r in refs})),
             "Columns": "; ".join(f"{r['source']}/{r['sheet']}: {r['column']}" for r in refs[:8])}
            for role, refs in sorted(key_index.get("roles", {}).items())]
    lines += [md_table(rows, ["Role", "Frames", "Sources", "Columns"]), ""]

    conflicts = [(p, k) for p in profiles for k in p.get("key_conflicts", [])]
    if conflicts:
        lines += ["## ⚠️ Same-role key conflicts", "",
                  "_Two columns claim the same role but disagree on the same native row. "
                  "Treating them as one key fabricates lineage._", "",
                  md_table([{"Frame": f"{p['source']}/{p['sheet']}", "Role": k["role"],
                             "A": f"{k['column_a']} ({k['side_a']})",
                             "B": f"{k['column_b']} ({k['side_b']})",
                             "Rows both": k["rows_both_present"],
                             "Disagree": f"{k['rows_disagreeing']} ({k['disagreement_pct']}%)"}
                            for p, k in conflicts],
                           ["Frame", "Role", "A", "B", "Rows both", "Disagree"]), ""]

    for p in profiles:
        lines += [f"---\n## Source: {p['source']} / Sheet: {p['sheet']}", "",
                  f"- Path: `{p['path']}`", f"- Domain: `{p.get('domain','')}`",
                  f"- Authority: `{p.get('authority','')}`", f"- Rows: **{p['row_count']:,}**",
                  f"- Columns: **{p['column_count']}**", f"- Sample: `{p['sample_file']}`", ""]
        if p.get("notes"):
            lines += [f"> Source note: {p['notes']}", ""]
        g = p.get("grain_inference", {}).get("best_candidate")
        lines.append("### Grain candidate")
        if g:
            lines += [f"`{g['label']}` on `{', '.join(g['columns'])}` — uniqueness "
                      f"`{g['uniqueness_ratio']}`, coverage `{g['coverage_of_frame']}`, "
                      f"repeated-key rows `{g['repeated_key_rows']}`.", ""]
        else:
            lines += [f"_No candidate reaches the {MIN_GRAIN_COVERAGE:.0%} coverage threshold; "
                      "grain is undetermined from this evidence._", ""]
        lines += ["### Representative keys",
                  md_table([{"Role": r, "Column": c, "Side": column_side(c)}
                            for r, c in sorted(p.get("representative_keys", {}).items())],
                           ["Role", "Column", "Side"]), ""]
        lines += ["### Status values"]
        sr = []
        for c, vals in p.get("status_profile", {}).items():
            for x in vals[:10]:
                sr.append({"Column": c, "Value": x["value"], "Count": x["count"],
                           "Raw variants": ", ".join(x.get("raw_variants") or [])})
        lines += [md_table(sr, ["Column", "Value", "Count", "Raw variants"]), ""]
        lines += ["### Co-observed relation candidates"]
        rr = [{"From": f"{r['from_role']} ({r['from_column']})",
               "To": f"{r['to_role']} ({r['to_column']})", "Card.": r["cardinality"],
               "Pairs": r["distinct_pairs"], "Max fanout": r["max_to_per_from"],
               "Primary": "yes" if r["is_primary_pair"] else ""}
              for r in p.get("relation_examples", [])]
        lines += [md_table(rr, ["From", "To", "Card.", "Pairs", "Max fanout", "Primary"]), ""]
        dp = p.get("duplicate_profile", {})
        if dp.get("composite_grain"):
            lines.append("### Repeated composite keys")
            for d in dp["composite_grain"][:6]:
                lines.append(f"- `{d['grain_label']}` on `{d['columns']}` → duplicate rows "
                             f"**{d['duplicate_rows']}**; examples: "
                             f"`{json.dumps(d['examples'][:3], ensure_ascii=False)}`")
            lines.append("")
        if dp.get("single_column"):
            lines.append("### Repeated single keys")
            for d in dp["single_column"][:8]:
                lines.append(f"- `{d['role']}` / `{d['column']}` → duplicate rows "
                             f"**{d['duplicate_rows']}**; examples: "
                             f"`{json.dumps(d['examples'][:3], ensure_ascii=False)}`")
            lines.append("")
        if p.get("unclassified_columns"):
            lines += ["### Unclassified columns",
                      "_No role was asserted for these; they are reported rather than guessed._",
                      "", "`" + "`, `".join(p["unclassified_columns"][:40]) + "`", ""]
    if errors:
        lines += ["---", "## Errors", ""] + [f"- {e}" for e in errors] + [""]
    return "\n".join(lines)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Profile GSI sources into a model evidence pack.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--output", default="gsi_evidence_pack")
    ap.add_argument("--sample-rows", type=int, default=18)
    ap.add_argument("--allow-missing", action="store_true",
                    help="exit 0 even when a configured source produced no evidence")
    args = ap.parse_args()

    cfg = Path(args.config).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = load_config(cfg)
    profiles: list[dict[str, Any]] = []
    errors: list[str] = []
    coverage: list[dict[str, Any]] = []
    written: list[Path] = []

    for spec in specs:
        path = Path(os.path.expandvars(os.path.expanduser(spec.path))).resolve()
        if not path.exists():
            msg = f"file not found: {path}"
            errors.append(f"{spec.name}: {msg}")
            coverage.append({"source": spec.name, "status": "MISSING_FILE", "detail": msg,
                             "required": spec.required})
            continue
        try:
            sheets, missing_sheets = selected_sheets(spec, path)
            for ms in missing_sheets:                                   # never silent
                errors.append(f"{spec.name}: configured sheet not in workbook: {ms}")
            if not sheets:
                msg = f"no matching sheet in workbook (missing: {missing_sheets or 'n/a'})"
                errors.append(f"{spec.name}: {msg}")
                coverage.append({"source": spec.name, "status": "NO_SHEET", "detail": msg,
                                 "required": spec.required})
                continue
            frames, rows, failed = 0, 0, []
            for sheet in sheets:
                try:
                    df = read_table(path, sheet).dropna(how="all")
                    df = df.reset_index(drop=True)
                    profiles.append(profile_frame(spec, path, sheet, df, args.sample_rows,
                                                  out, written))
                    frames += 1
                    rows += len(df)
                except Exception as e:
                    failed.append(f"{sheet}: {type(e).__name__}: {e}")
                    errors.append(f"{spec.name}/{sheet}: {type(e).__name__}: {e}")
            if frames and not failed:
                coverage.append({"source": spec.name, "status": "PROFILED", "frames": frames,
                                 "rows": rows, "required": spec.required})
            elif frames:
                coverage.append({"source": spec.name, "status": "PARTIAL", "frames": frames,
                                 "rows": rows, "required": spec.required,
                                 "detail": "; ".join(failed)})
            else:
                coverage.append({"source": spec.name, "status": "FAILED", "frames": 0, "rows": 0,
                                 "required": spec.required, "detail": "; ".join(failed)})
        except Exception as e:
            errors.append(f"{spec.name}: {type(e).__name__}: {e}")
            coverage.append({"source": spec.name, "status": "FAILED", "frames": 0, "rows": 0,
                             "required": spec.required, "detail": f"{type(e).__name__}: {e}"})

    idx = build_global_key_index(profiles)
    for name, payload in (("source_catalog.json", profiles),
                          ("process_key_index.json", idx),
                          ("coverage_report.json", {"tool_version": TOOL_VERSION,
                                                    "coverage": coverage, "errors": errors})):
        p = out / name
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(p)
    p = out / "model_context_pack.md"
    p.write_text(build_markdown(profiles, idx, cfg, coverage, errors), encoding="utf-8")
    written.append(p)

    incomplete = [c for c in coverage if c["status"] != "PROFILED"]
    conflicts = sum(len(x.get("key_conflicts", [])) for x in profiles)
    banner = ("\n> ⛔ **INCOMPLETE** — " +
              f"{len(incomplete)} of {len(coverage)} configured sources produced no evidence: " +
              ", ".join(f"{c['source']} ({c['status']})" for c in incomplete) +
              ".\n> Conclusions are scoped to the PROFILED sources only.\n"
              if incomplete else "\n> ✅ All configured sources profiled.\n")
    summary = ("# Executive Summary — GSI Source Evidence Pack\n\n"
               f"Tool `{TOOL_VERSION}` · generated {datetime.now().isoformat(timespec='seconds')}\n"
               f"{banner}\n"
               f"- Configured sources: **{len(coverage)}**\n"
               f"- Profiled frames/sheets: **{len(profiles)}**\n"
               f"- Total native rows scanned: **{sum(p['row_count'] for p in profiles):,}**\n"
               f"- Same-role key conflicts found: **{conflicts}**\n"
               f"- Cross-source key roles: "
               f"**{', '.join(idx.get('candidate_cross_source_join_roles', [])) or 'none detected'}**\n\n"
               "## Source coverage\n\n" + coverage_table(coverage) + "\n\n"
               "## Read order\n1. model_context_pack.md\n2. process_key_index.json\n"
               "3. coverage_report.json\n4. Relevant sample CSVs\n5. Relevant schema JSONs\n\n"
               "Heuristic grain and join findings are not business truth until confirmed by "
               "contracts or code. A shared role name never makes two identifiers the same "
               "business entity.\n")
    p = out / "executive_summary.md"
    p.write_text(summary, encoding="utf-8")
    written.append(p)

    # Manifest covers only what this run wrote (M-13).
    manifest = {"tool_version": TOOL_VERSION,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "config": str(cfg), "configured_sources": len(coverage),
                "profiled_frames": len(profiles), "coverage": coverage, "errors": errors,
                "files": {str(f.relative_to(out)): {"bytes": f.stat().st_size,
                                                    "sha256": sha256_file(f)}
                          for f in sorted(set(written)) if f.is_file()}}
    (out / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                           encoding="utf-8")

    print(f"Evidence pack written to: {out}")
    print(f"Configured sources: {len(coverage)} | profiled frames: {len(profiles)} | "
          f"errors: {len(errors)} | same-role key conflicts: {conflicts}")
    for e in errors:
        print("WARN:", e, file=sys.stderr)
    if incomplete and not args.allow_missing:
        print(f"FAIL: {len(incomplete)} configured source(s) produced no evidence: "
              + ", ".join(f"{c['source']}({c['status']})" for c in incomplete), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

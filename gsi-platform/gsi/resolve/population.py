# -*- coding: utf-8 -*-
"""Tier-1 business population for the flat operational report.

V29.7.4 changes the population contract: Commercial Expert + NTSW create the
business population. Abbasi/SATA are enrichment evidence and are never allowed
to create an otherwise absent business case.

The population is intentionally conservative:
* Commercial Expert contributes one row per ORDER (its native aggregate grain).
* NTSW contributes documented ORDER/REG rows and REG-only rows.
* Ambiguous equal-priority ORDER→REG mappings are not guessed. Conflicting NTSW
  registrations remain isolated REG cases so evidence is not lost.
* Abbasi may expand a primary ORDER to its directly observed BLs, but cannot add
  Abbasi-only orders. This preserves logistics detail without restoring Abbasi
  as the population authority.
"""
from __future__ import annotations

from typing import Dict, Mapping, Tuple

import pandas as pd

from ..adapters.base import KEY_BL, KEY_ORDER, KEY_REG, KEY_REG_FILE
from ..core.text import clean_key, clean_order_ref, is_empty_val
from .registration_bridge import build_ntsw_order_reg_bridge

POP_SOURCE = "POPULATION_SOURCE"
POP_PRIMARY = "IS_PRIMARY_POPULATION"
POP_EXPERT = "IS_IN_EXPERT_PRIMARY"
POP_NTSW = "IS_IN_NTSW_PRIMARY"
POP_KEY = "PRIMARY_POPULATION_KEY"


def _clean_reg(v) -> str:
    s = clean_key(v)
    return s if len(s) == 8 and s.isdigit() else ""


def _frame(sources: Mapping[str, Mapping[str, pd.DataFrame]], source: str, frame: str):
    return (sources.get(source) or {}).get(frame)


def _ntsw_reg_rows(sources: Mapping[str, Mapping[str, pd.DataFrame]]) -> pd.DataFrame:
    """Return distinct native NTSW registration observations.

    Rows are limited to keys needed for population construction. No lower-tier
    source participates here.
    """
    rows = []
    lic = _frame(sources, "ntsw", "import_license")
    if isinstance(lic, pd.DataFrame) and not lic.empty:
        for _, r in lic.iterrows():
            reg = _clean_reg(r.get("NTSW_KEY_REG", r.get(KEY_REG, "")))
            order = clean_order_ref(r.get(KEY_ORDER, ""))
            reg_file = clean_key(r.get(KEY_REG_FILE, ""))
            if reg:
                rows.append({KEY_ORDER: order, "NTSW_KEY_REG": reg,
                             KEY_REG_FILE: reg_file,
                             "NTSW_POPULATION_PATH": "IMPORT_LICENCE"})

    # Commitment/allocation can contain valid registrations that are not present
    # in the particular Import Licence export. They must not disappear from the
    # report population merely because an enrichment file is incomplete.
    for fname in ("commitment", "allocation_rows", "allocation"):
        df = _frame(sources, "ntsw", fname)
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        for _, r in df.iterrows():
            reg = _clean_reg(r.get("NTSW_KEY_REG", r.get(KEY_REG, "")))
            if reg:
                rows.append({KEY_ORDER: "", "NTSW_KEY_REG": reg,
                             KEY_REG_FILE: "",
                             "NTSW_POPULATION_PATH": fname.upper()})

    if not rows:
        return pd.DataFrame(columns=[KEY_ORDER, "NTSW_KEY_REG", KEY_REG_FILE,
                                     "NTSW_POPULATION_PATH"])
    out = pd.DataFrame(rows)
    return out.drop_duplicates(subset=[KEY_ORDER, "NTSW_KEY_REG", KEY_REG_FILE], keep="first")


def _merge_expert_with_ntsw(expert: pd.DataFrame, ntsw_rows: pd.DataFrame,
                            bridge: pd.DataFrame) -> pd.DataFrame:
    if isinstance(expert, pd.DataFrame) and not expert.empty:
        base = expert.copy()
        if KEY_ORDER not in base:
            base[KEY_ORDER] = ""
        base[KEY_ORDER] = base[KEY_ORDER].map(clean_order_ref)
        base[POP_EXPERT] = True
        base[POP_NTSW] = False
        base[POP_PRIMARY] = True
        base[POP_SOURCE] = "EXPERT"
        if not bridge.empty:
            b = bridge.drop_duplicates(subset=[KEY_ORDER], keep="first")
            base = base.merge(b, on=KEY_ORDER, how="left")
            hit = base["NTSW_KEY_REG"].fillna("").astype(str).str.strip().ne("")
            base.loc[hit, POP_NTSW] = True
            base.loc[hit, POP_SOURCE] = "EXPERT+NTSW"
    else:
        base = pd.DataFrame()

    represented_orders = set()
    represented_regs = set()
    if not base.empty:
        represented_orders = {clean_order_ref(x) for x in base.get(KEY_ORDER, []) if clean_order_ref(x)}
        represented_regs = {_clean_reg(x) for x in base.get("NTSW_KEY_REG", []) if _clean_reg(x)}

    # Orders for which the direct/hub NTSW bridge is unambiguous are safe to
    # materialize as ORDER+REG cases. Ambiguous mappings remain REG-only cases.
    resolved_order_reg = {
        clean_order_ref(r.get(KEY_ORDER, "")): _clean_reg(r.get("NTSW_KEY_REG", ""))
        for _, r in bridge.iterrows()
        if clean_order_ref(r.get(KEY_ORDER, "")) and _clean_reg(r.get("NTSW_KEY_REG", ""))
    } if not bridge.empty else {}

    additions = []
    for _, r in ntsw_rows.iterrows():
        reg = _clean_reg(r.get("NTSW_KEY_REG", ""))
        order = clean_order_ref(r.get(KEY_ORDER, ""))
        if not reg:
            continue
        if reg in represented_regs:
            continue
        if order and resolved_order_reg.get(order) == reg:
            if order in represented_orders:
                # Existing expert row should already carry this bridge value.
                represented_regs.add(reg)
                continue
            add_order = order
            src = "NTSW"
        else:
            # Do not attach an ambiguous NTSW REG to an ORDER. Keep the case, not
            # the guessed relation.
            add_order = ""
            src = "NTSW" if not order else "NTSW_CONFLICT_ISOLATED"
        additions.append({
            KEY_ORDER: add_order,
            "NTSW_KEY_REG": reg,
            KEY_REG: reg,
            KEY_REG_FILE: clean_key(r.get(KEY_REG_FILE, "")),
            "NTSW_POPULATION_PATH": r.get("NTSW_POPULATION_PATH", ""),
            POP_EXPERT: False,
            POP_NTSW: True,
            POP_PRIMARY: True,
            POP_SOURCE: src,
        })
        represented_regs.add(reg)
        if add_order:
            represented_orders.add(add_order)

    if additions:
        add_df = pd.DataFrame(additions)
        base = pd.concat([base, add_df], ignore_index=True, sort=False) if not base.empty else add_df

    if base.empty:
        return base
    if KEY_REG not in base.columns:
        base[KEY_REG] = ""
    # Only NTSW supplies KEY_REG at population construction time. The canonical
    # key is rematerialized later after all enrichment columns are present.
    nreg = base.get("NTSW_KEY_REG", pd.Series("", index=base.index)).map(_clean_reg)
    blank = base[KEY_REG].map(_clean_reg).eq("")
    base.loc[blank, KEY_REG] = nreg.loc[blank]
    base[POP_KEY] = [f"ORDER:{o}" if o else f"REG:{r}" for o, r in
                     zip(base[KEY_ORDER].map(clean_order_ref), base[KEY_REG].map(_clean_reg))]
    return base.reset_index(drop=True)


def _attach_abbasi(base: pd.DataFrame, abbasi: pd.DataFrame) -> pd.DataFrame:
    """Attach all directly observed BLs for primary orders, never Abbasi-only rows."""
    if base.empty or not isinstance(abbasi, pd.DataFrame) or abbasi.empty:
        if KEY_BL not in base.columns:
            base = base.copy(); base[KEY_BL] = ""
        return base
    if KEY_ORDER not in abbasi.columns:
        if KEY_BL not in base.columns:
            base = base.copy(); base[KEY_BL] = ""
        return base

    right = abbasi.copy()
    right[KEY_ORDER] = right[KEY_ORDER].map(clean_order_ref)
    right = right[right[KEY_ORDER].astype(str).str.strip().ne("")]
    if right.empty:
        if KEY_BL not in base.columns:
            base = base.copy(); base[KEY_BL] = ""
        return base

    # One ORDER may legitimately have several BLs. Deduplicate only identical
    # ORDER+BL observations, then expand primary rows across those BLs.
    subset = [KEY_ORDER] + ([KEY_BL] if KEY_BL in right.columns else [])
    right = right.drop_duplicates(subset=subset, keep="first")
    clashes = [c for c in right.columns if c != KEY_ORDER and c in base.columns]
    if clashes:
        right = right.drop(columns=clashes)
    out = base.merge(right, on=KEY_ORDER, how="left")
    if KEY_BL not in out.columns:
        out[KEY_BL] = ""
    out[KEY_BL] = out[KEY_BL].fillna("")
    return out


def build_primary_population(sources: Dict[str, Dict[str, pd.DataFrame]]) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Build full-report population from tier-1 sources and enrich with Abbasi BLs."""
    expert = _frame(sources, "moghavemat", "main")
    ntsw_rows = _ntsw_reg_rows(sources)
    bridge, diagnostics = build_ntsw_order_reg_bridge(sources)

    has_expert = isinstance(expert, pd.DataFrame) and not expert.empty
    has_ntsw = not ntsw_rows.empty
    if not has_expert and not has_ntsw:
        raise RuntimeError("جمعیت اصلی قابل ساخت نیست: هر دو سورس درجه‌اول کارشناسان و NTSW خالی‌اند.")

    base = _merge_expert_with_ntsw(expert if has_expert else pd.DataFrame(), ntsw_rows, bridge)
    base = _attach_abbasi(base, _frame(sources, "abbasi", "main"))

    meta = {
        "population_policy": "moghavemat+ntsw primary; abbasi+sata enrichment only",
        "primary_rows": int(len(base)),
        "expert_primary_rows": int(base.get(POP_EXPERT, pd.Series(False, index=base.index)).fillna(False).astype(bool).sum()),
        "ntsw_primary_rows": int(base.get(POP_NTSW, pd.Series(False, index=base.index)).fillna(False).astype(bool).sum()),
        "unique_primary_orders": int(base.get(KEY_ORDER, pd.Series(dtype=object)).replace("", pd.NA).nunique()),
        "unique_primary_regs": int(base.get(KEY_REG, pd.Series(dtype=object)).replace("", pd.NA).nunique()),
        "abbasi_enrichment_rows": int(base.get(KEY_BL, pd.Series(dtype=object)).fillna("").astype(str).str.strip().ne("").sum()),
    }
    return base, diagnostics, meta

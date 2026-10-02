# -*- coding: utf-8 -*-
"""Authoritative ORDER→REG bridge for the full report.

The flat mart historically obtained REG almost exclusively from SATA because
SATA sits on the BL spine.  That made the *technical merge path* silently
become evidence authority.  This module builds the documented NTSW bridge
before REG is materialized:

1) NTSW Import Licence direct ORDER + REG co-observation.
2) NTSW Import Licence REG_FILE→REG joined to IL Append REG_FILE→ORDER.

Only exact documented keys are used.  Ambiguous equal-tier NTSW mappings are
not guessed; they are returned as diagnostics and left blank for review.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from ..adapters.base import KEY_ORDER, KEY_REG, KEY_REG_FILE
from ..core.text import clean_key, clean_order_ref, is_empty_val


def _clean_order(v) -> str:
    return clean_order_ref(v)


def _clean_reg(v) -> str:
    s = clean_key(v)
    return s if len(s) == 8 and s.isdigit() else ""


def _clean_reg_file(v) -> str:
    """Registration-file number, or "" for placeholders.

    V29.9: placeholder values such as ``0``, ``000`` or ``-`` were kept as real
    keys, so the Import-Licence ⋈ IL-Append hub joined every placeholder row
    with every other one (cartesian). With a single licence row this silently
    mapped *all* placeholder orders to that licence's REG.
    """
    s = clean_key(v)
    return "" if is_empty_val(s) or not s.strip("0") else s


def build_ntsw_order_reg_bridge(sources: Dict[str, Dict[str, pd.DataFrame]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    lic = (sources.get('ntsw') or {}).get('import_license')
    il = (sources.get('ilappend') or {}).get('main')
    candidates: List[dict] = []

    if isinstance(lic, pd.DataFrame) and not lic.empty:
        for idx, r in lic.iterrows():
            order = _clean_order(r.get(KEY_ORDER, ''))
            reg = _clean_reg(r.get('NTSW_KEY_REG', r.get(KEY_REG, '')))
            if order and reg:
                candidates.append({'KEY_ORDER': order, 'NTSW_KEY_REG': reg,
                                   'NTSW_REG_AUTHORITY_PATH': 'NTSW_IMPORT_LICENCE_DIRECT',
                                   '_ref': f'ntsw/import_license#{idx+1}'})

        if isinstance(il, pd.DataFrame) and not il.empty and KEY_REG_FILE in il.columns:
            left = lic.copy()
            left['_RF'] = (left[KEY_REG_FILE].map(_clean_reg_file) if KEY_REG_FILE in left.columns
                           else pd.Series('', index=left.index, dtype=object))
            left['_REG'] = left.apply(lambda r: _clean_reg(r.get('NTSW_KEY_REG', r.get(KEY_REG, ''))), axis=1)
            left = left[(left['_RF'] != '') & (left['_REG'] != '')][['_RF','_REG']].drop_duplicates()

            right = il.copy()
            right['_RF'] = right.get(KEY_REG_FILE, '').map(_clean_reg_file)
            right['_ORDER'] = right.get(KEY_ORDER, '').map(_clean_order)
            right = right[(right['_RF'] != '') & (right['_ORDER'] != '')][['_RF','_ORDER']].drop_duplicates()

            if not left.empty and not right.empty:
                hub = left.merge(right, on='_RF', how='inner')
                for idx, r in hub.iterrows():
                    candidates.append({'KEY_ORDER': r['_ORDER'], 'NTSW_KEY_REG': r['_REG'],
                                       'NTSW_REG_AUTHORITY_PATH': 'NTSW_REG_FILE_HUB',
                                       '_ref': f"reg_file:{r['_RF']}"})

    if not candidates:
        return pd.DataFrame(columns=[KEY_ORDER,'NTSW_KEY_REG','NTSW_REG_AUTHORITY_PATH']), pd.DataFrame()

    c = pd.DataFrame(candidates)
    resolved: List[dict] = []
    diagnostics: List[dict] = []
    for order, g in c.groupby(KEY_ORDER, sort=False):
        regs = sorted({x for x in g['NTSW_KEY_REG'].astype(str) if x})
        if len(regs) != 1:
            diagnostics.append({
                'code': 'NTSW_EQUAL_PRIORITY_ORDER_REG_CONFLICT',
                'KEY_ORDER': order,
                'values': ' | '.join(regs),
                'references': ' | '.join(sorted(set(g['_ref'].astype(str)))),
            })
            continue
        direct = g[g['NTSW_REG_AUTHORITY_PATH'].eq('NTSW_IMPORT_LICENCE_DIRECT')]
        winner = direct.iloc[0] if not direct.empty else g.iloc[0]
        resolved.append({KEY_ORDER: order, 'NTSW_KEY_REG': regs[0],
                         'NTSW_REG_AUTHORITY_PATH': winner['NTSW_REG_AUTHORITY_PATH']})

    return pd.DataFrame(resolved), pd.DataFrame(diagnostics)

# -*- coding: utf-8 -*-
"""Source-grain material evidence index and exact identifier search.

This module deliberately does not depend on the BL/base mart.  A Material code is
an identifier, not descriptive free text, so exact canonical key equality is the
primary match rule.  Description/PR/Order differences never suppress a row that
carries the same material identifier.
"""
from __future__ import annotations
import pandas as pd
from ..core.text import clean_part_no

EVIDENCE_COLUMNS = (
    'MOGH_ROW_NO','KEY_ORDER','KEY_PR','MOGH_PR_ITEM','KEY_MATERIAL',
    'MOGH_MATERIAL','MOGH_MATERIAL_DESC','MOGH_MATERIAL_SHORT'
)


def build_material_evidence(lines: pd.DataFrame) -> pd.DataFrame:
    if lines is None or not isinstance(lines, pd.DataFrame) or lines.empty or 'KEY_MATERIAL' not in lines.columns:
        return pd.DataFrame(columns=[*EVIDENCE_COLUMNS, 'MATERIAL_SEARCH_KEY'])
    wanted=[c for c in EVIDENCE_COLUMNS if c in lines.columns]
    out=lines[wanted].copy()
    out['MATERIAL_SEARCH_KEY']=out['KEY_MATERIAL'].fillna('').map(clean_part_no)
    out=out[out['MATERIAL_SEARCH_KEY'].astype(str).str.strip().ne('')].copy()
    return out.reset_index(drop=True)


def search_material(evidence: pd.DataFrame, query: str) -> pd.DataFrame:
    if evidence is None or not isinstance(evidence, pd.DataFrame) or evidence.empty:
        return pd.DataFrame()
    q=clean_part_no(query)
    if not q:
        return pd.DataFrame()
    if 'MATERIAL_SEARCH_KEY' in evidence.columns:
        key=evidence['MATERIAL_SEARCH_KEY'].fillna('').astype(str)
    elif 'KEY_MATERIAL' in evidence.columns:
        key=evidence['KEY_MATERIAL'].fillna('').map(clean_part_no)
    else:
        return pd.DataFrame()
    keep=[c for c in EVIDENCE_COLUMNS if c in evidence.columns]
    return evidence.loc[key.eq(q), keep].copy().reset_index(drop=True)

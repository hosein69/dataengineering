# -*- coding: utf-8 -*-
"""Expert material positions at ORDER × MATERIAL grain, including partial rows.

This ledger is separate from the flat order/BL mart. No order-level amount or
Oracle stock is summed across source lines or different orders.
"""
from __future__ import annotations

from types import SimpleNamespace
import pandas as pd

from ..adapters.base import KEY_MATERIAL, KEY_ORDER
from ..core.text import is_empty_val
from ..stages.s38_supply_position import SupplyPositionStage


def build_expert_material_positions(lines: pd.DataFrame, inventory: pd.DataFrame | None,
                                    oracle: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(lines, pd.DataFrame) or lines.empty or KEY_MATERIAL not in lines:
        return pd.DataFrame()
    source = lines[lines[KEY_MATERIAL].fillna("").astype(str).str.strip().ne("")].copy()
    if source.empty:
        return pd.DataFrame()
    if KEY_ORDER not in source:
        source[KEY_ORDER] = ""
    source[KEY_ORDER] = source[KEY_ORDER].fillna("").astype(str).str.strip()

    rows = []
    for (order, material), group in source.groupby([KEY_ORDER, KEY_MATERIAL], sort=False):
        descriptions = list(dict.fromkeys(str(v).strip() for v in group.get(
            "MOGH_MATERIAL_DESC", pd.Series(dtype=object)) if not is_empty_val(v)))
        gaps = [(c, label) for c, label in (
            ("MOGH_PR_NO", "شماره درخواست خرید"),
            ("MOGH_PO_SENT_DATE", "تاریخ ابلاغ سفارش"),
            ("MOGH_VENDOR_CODE", "کد تأمین‌کننده"),
            ("MOGH_PI_LINE_VALUE", "ارزش PI"))
            if c in group and any(is_empty_val(v, treat_zero_as_empty=(c != "MOGH_PI_LINE_VALUE"))
                                  for v in group[c])]
        rows.append({KEY_ORDER: order, KEY_MATERIAL: material,
                     "MOGH_MATERIAL_DESCS_ALL": " | ".join(descriptions),
                     "MOGH_MATERIAL_DESC_COUNT": len(descriptions),
                     "EXPERT_SOURCE_ROWS": len(group),
                     "EXPERT_RECORD_GAPS": "، ".join(label for _, label in gaps)})
    out = pd.DataFrame(rows)
    if isinstance(inventory, pd.DataFrame) and not inventory.empty:
        # Part states per Order×Material, order-less materials included (29.15.12).
        inv_cols = [KEY_ORDER, KEY_MATERIAL] + [c for c in (
            "MOGH_QTY_AT_SUPPLIER", "MOGH_QTY_READY", "MOGH_QTY_IN_TRANSIT",
            "MOGH_QTY_IN_CUSTOMS", "MOGH_QTY_STATE_UNKNOWN", "MOGH_INVENTORY_CONFLICT")
            if c in inventory]
        inv = inventory[inv_cols].copy()
        inv[KEY_ORDER] = inv[KEY_ORDER].fillna("").astype(str).str.strip()
        out = out.merge(inv, on=[KEY_ORDER, KEY_MATERIAL], how="left", validate="m:1")
    if isinstance(oracle, pd.DataFrame) and not oracle.empty:
        orc_cols = [KEY_MATERIAL] + [c for c in (
            "ORC_STOCK_IKCO", "ORC_STOCK_SAPCO", "ORC_DAILY_NEED", "ORC_MATERIAL_DESC") if c in oracle]
        out = out.merge(oracle[orc_cols], on=KEY_MATERIAL, how="left", validate="m:1")
    for target, col in {
        "SUPPLIER_QTY": "MOGH_QTY_AT_SUPPLIER",
        "READY_QTY": "MOGH_QTY_READY",
        "IN_TRANSIT_QTY": "MOGH_QTY_IN_TRANSIT",
        "IN_CUSTOMS_QTY": "MOGH_QTY_IN_CUSTOMS",
        "EXPERT_INV_UNKNOWN_QTY": "MOGH_QTY_STATE_UNKNOWN",
        "EXPERT_INV_CONFLICT": "MOGH_INVENTORY_CONFLICT",
        "STOCK_IKCO": "ORC_STOCK_IKCO",
        "STOCK_SAPCO": "ORC_STOCK_SAPCO",
        "DAILY_NEED": "ORC_DAILY_NEED",
    }.items():
        if col in out:
            valid = out[col].map(lambda v: not is_empty_val(v, treat_zero_as_empty=False))
            out[target] = out[col].where(valid, "")
        else:
            out[target] = pd.Series("", index=out.index, dtype=object)
    out["CANONICAL_ORDER"] = out[KEY_ORDER]
    ctx = SimpleNamespace(extras={})
    return SupplyPositionStage().run(out, ctx)

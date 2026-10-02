# -*- coding: utf-8 -*-
"""R10: ستون‌های موازی و بی‌داده در خروجی‌های همه‌ستون (داده ساختگی)."""
import pandas as pd

from gsi.studio_core.column_tidy import tidy_columns


def _df():
    return pd.DataFrame({
        "KEY_ORDER": ["O1", "O2", "O3"],
        "CASE_KEY": ["O1", "O2", "O3"],
        "INVOICE_VALUE": [100.0, 200.0, 300.0],
        "SATA_INVOICE_VALUE": [100, None, 300],          # زیرمجموعه INVOICE_VALUE: موازی
        "BL_DISCHARGE_DATE": ["1405/01/01", "", "1405/02/01"],
        "DISCHARGE_DATE": ["1405/01/01", "1405/01/09", "1405/02/03"],   # ردیف ۳ فرق دارد
        "STOCK_IKCO": [5, 6, 7],
        "موجودی ایران خودرو": [5, 6, 7],
        "CRD_CURRENCY": ["EUR", "", ""],
        "CURRENCY": ["EUR", "CNY", "USD"],                # هم‌نام ولی معنای دیگر: می‌ماند
        "IL_STATUS": [None, "", None],                    # بی‌داده
        "IS_CANCELLED": [False, False, False],            # «خیر» داده است
        "KEY_MATERIAL": ["M1", "M2", "M3"],
        "CANONICAL_PART_NO": ["M1", "M2", "M3"],
        "MOGH_MATERIAL": ["M1", "M2", ""],
    })


def test_parallel_and_empty_columns_leave_output_only():
    df = _df()
    keep, dropped = tidy_columns(df)
    why = {d["ستون"]: (d["علت"], d["ستون معیار"]) for d in dropped}
    assert why["SATA_INVOICE_VALUE"] == ("موازی", "INVOICE_VALUE")
    assert why["موجودی ایران خودرو"] == ("موازی", "STOCK_IKCO")
    assert why["CASE_KEY"] == ("موازی", "KEY_ORDER")
    assert why["IL_STATUS"][0] == "بی‌داده"
    # زنجیره به ستونی ختم می‌شود که ماند
    assert why["MOGH_MATERIAL"] == ("موازی", "KEY_MATERIAL") and why["CANONICAL_PART_NO"][1] == "KEY_MATERIAL"
    for c in ("KEY_ORDER", "INVOICE_VALUE", "DISCHARGE_DATE", "BL_DISCHARGE_DATE", "CRD_CURRENCY", "CURRENCY",
              "IS_CANCELLED", "STOCK_IKCO", "KEY_MATERIAL"):
        assert c in keep, c
    assert list(df.columns) == list(_df().columns)       # داده دست نخورد


def test_explicit_choice_is_never_dropped():
    keep, _ = tidy_columns(_df(), ["KEY_ORDER", "SATA_INVOICE_VALUE", "IL_STATUS"],
                           protect=["SATA_INVOICE_VALUE", "IL_STATUS"])
    assert keep == ["KEY_ORDER", "SATA_INVOICE_VALUE", "IL_STATUS"]

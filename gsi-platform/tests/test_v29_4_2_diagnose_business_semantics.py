import pandas as pd


def test_reg_file_is_not_reg_and_ntsw_hub_is_used():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_REG, KEY_REG_FILE

    d = JoinDiagnostics()
    d.sources = {
        "ntsw": {
            "import_license": pd.DataFrame({KEY_REG_FILE:["664931855"], KEY_REG:["10290719"]}),
            "commitment": pd.DataFrame({KEY_REG:["10290719"]}),
            "allocation": pd.DataFrame({KEY_REG:["10290719"]}),
        },
        "ilappend": {"main": pd.DataFrame({KEY_REG_FILE:["664931855"], KEY_REG:["10290719"]})},
    }
    d.base = pd.DataFrame()

    il = d._check("ilappend", "main", "REG_FILE")
    assert il["کلید"] == KEY_REG_FILE
    assert il["اشتراک کلید"] == 1
    assert il["علت"] == "OK"

    c = d._check("ntsw", "commitment", "REG")
    assert c["اشتراک کلید"] == 1
    assert c["علت"] == "OK"
    # 9-digit file number must never contaminate the 8-digit REG universe.
    assert "664931855" not in d._left_keys_for("ntsw", "commitment", KEY_REG)


def test_sap_is_diagnosed_by_pr_but_excluded_while_source_is_known_incomplete(monkeypatch):
    from gsi import diagnose
    original = diagnose._known_incomplete
    monkeypatch.setattr(diagnose, '_known_incomplete', lambda source, frame: True if source == 'sap' else original(source, frame))
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_PR

    d = JoinDiagnostics()
    d.sources = {
        "moghavemat": {"lines": pd.DataFrame({KEY_PR:["1000000001", "1000000002"]})},
        "sap": {"main": pd.DataFrame({KEY_PR:["1000000001"]})},
    }
    d.base = pd.DataFrame()
    row = d._check("sap", "main", "PR")
    assert row["کلید"] == KEY_PR
    assert row["علت"] == "KNOWN_INCOMPLETE_SOURCE"
    assert row["شدت"] == "INFO"
    assert row["Semantic"] == "NOT_ASSESSED"


def test_order_material_is_grain_contract_not_bl_join():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_ORDER, KEY_MATERIAL

    d = JoinDiagnostics()
    d.sources = {
        "moghavemat": {"inventory": pd.DataFrame({
            KEY_ORDER:["502001", "502001"],
            KEY_MATERIAL:["MAT1", "MAT2"],
        })}
    }
    row = d._check("moghavemat", "inventory", "ORDER_MATERIAL")
    assert row["کلید"] == f"{KEY_ORDER}+{KEY_MATERIAL}"
    assert row["علت"] == "GRAIN_OK"
    assert row["کلید یکتا در سورس"] == 2


def test_order_material_duplicate_is_explicit_grain_violation():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_ORDER, KEY_MATERIAL

    d = JoinDiagnostics()
    d.sources = {
        "moghavemat": {"inventory": pd.DataFrame({
            KEY_ORDER:["502001", "502001"],
            KEY_MATERIAL:["MAT1", "MAT1"],
        })}
    }
    row = d._check("moghavemat", "inventory", "ORDER_MATERIAL")
    assert row["علت"] == "GRAIN_DUPLICATE"
    assert "dedupe" in row["اقدام"]


def test_critical_diagnostic_uses_real_clearance_field_and_mogh_grains():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_MATERIAL

    d = JoinDiagnostics()
    d.sources = {
        "clearance":{"main": pd.DataFrame({"CL_CLEAR_DATE":["1405/01/01"]})},
        "moghavemat":{
            "inventory": pd.DataFrame({
                KEY_MATERIAL:["M1"],
                "MOGH_SUPPLIER_STOCK_QTY":[""],
                "MOGH_SUPPLIER_STOCK_QTY_DERIVED":[12.0],
                "MOGH_IN_TRANSIT_QTY":[""],
                "MOGH_IN_CUSTOMS_QTY":[""],
            }),
            "lines": pd.DataFrame({"MOGH_ADDITIONAL_DATA":["ارسال شده"]}),
        },
    }
    out=d.critical_columns()
    clear=out[out["ستون"].eq("CL_CLEAR_DATE")].iloc[0]
    assert clear["نرخ پر بودن (٪)"] == 100.0
    mat=out[(out["ستون"].eq(KEY_MATERIAL)) & (out["سورس"].eq("moghavemat/inventory"))].iloc[0]
    assert mat["نرخ پر بودن (٪)"] == 100.0
    derived=out[out["ستون"].eq("MOGH_SUPPLIER_STOCK_QTY_DERIVED")].iloc[0]
    assert "مشتق قابل ممیزی" in derived["وضعیت"]
    transit=out[out["ستون"].eq("MOGH_IN_TRANSIT_QTY")].iloc[0]
    assert "Missing" in transit["وضعیت"]


def test_derive_accepts_actual_clearance_adapter_column():
    from gsi.stages.s20_derive import DERIVED
    assert "CL_CLEAR_DATE" in DERIVED["FULL_CLEAR_DATE"][0]

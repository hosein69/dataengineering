import pandas as pd


def test_low_base_coverage_does_not_make_healthy_source_join_bad():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_REG

    d = JoinDiagnostics()
    d.sources = {
        "ntsw": {"import_license": pd.DataFrame({KEY_REG:[str(i) for i in range(100,200)]})},
        "ilappend": {"main": pd.DataFrame({"IL_KEY_REG":[str(i) for i in range(100,200)]})},
        "fx_transaction": {"main": pd.DataFrame({KEY_REG:["100","101","102"]})},
    }
    d.base = pd.DataFrame()
    row = d._check("fx_transaction", "main", "REG")
    assert row["Source Match (٪)"] == 100.0
    assert row["Base Coverage (٪)"] == 3.0
    assert row["علت"] == "HEALTHY_LIMITED_SCOPE"
    assert row["شدت"] == "INFO"


def test_incomplete_sap_is_informational_not_false_error(monkeypatch):
    from gsi import diagnose
    original = diagnose._known_incomplete
    monkeypatch.setattr(diagnose, '_known_incomplete', lambda source, frame: True if source == 'sap' else original(source, frame))
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_PR

    d = JoinDiagnostics()
    d.sources = {
        "moghavemat":{"lines": pd.DataFrame({KEY_PR:["6100001"]})},
        "sap":{"main": pd.DataFrame({KEY_PR:["6900001"]})},
    }
    d.base = pd.DataFrame()
    row = d._check("sap", "main", "PR")
    assert row["علت"] == "KNOWN_INCOMPLETE_SOURCE"
    assert row["شدت"] == "INFO"
    assert row["Semantic"] == "NOT_ASSESSED"


def test_order_unmatched_breakdown_is_forensic_not_auto_match():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_ORDER

    d = JoinDiagnostics()
    d.base = pd.DataFrame({KEY_ORDER:["104620-S-2", "502001"]})
    d.sources = {
        "moghavemat":{"main": pd.DataFrame({KEY_ORDER:["104620S2", "700001", "888888"]})},
        "doccheck":{"main": pd.DataFrame({KEY_ORDER:["700001"]})},
    }
    row = d._check("moghavemat", "main", "ORDER")
    assert row["اشتراک کلید"] == 0  # candidate does not become a fabricated match
    assert row["Unmatched-NormalizationCandidate"] == 1
    assert row["Unmatched-OutsideBaseScope"] == 1
    assert row["Unmatched-Unresolved"] == 1
    cats = {x["طبقه"] for x in d.unmatched_details}
    assert cats == {"NORMALIZATION_CANDIDATE", "OUTSIDE_BASE_SCOPE", "UNRESOLVED"}


def test_mostly_matched_relation_is_info_not_error():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_REG, KEY_REG_FILE

    regfiles=[str(1000+i) for i in range(100)]
    d=JoinDiagnostics()
    d.sources={
        "ntsw":{"import_license":pd.DataFrame({KEY_REG_FILE:regfiles, KEY_REG:[str(2000+i) for i in range(100)]})},
        "ilappend":{"main":pd.DataFrame({KEY_REG_FILE:regfiles[:94] + ["X1","X2","X3","X4","X5","X6"]})},
    }
    d.base=pd.DataFrame()
    row=d._check("ilappend","main","REG_FILE")
    assert row["Source Match (٪)"] == 94.0
    assert row["علت"] == "HEALTHY_WITH_GAPS"
    assert row["شدت"] == "INFO"


def test_zero_overlap_is_unproven_relation_not_claimed_bad_format():
    from gsi.diagnose import JoinDiagnostics
    from gsi.adapters.base import KEY_REG
    d=JoinDiagnostics()
    d.sources={
        "ntsw":{"import_license":pd.DataFrame({KEY_REG:["100","101"]}),
                "commitment":pd.DataFrame({KEY_REG:["900","901"]})},
    }
    d.base=pd.DataFrame()
    row=d._check("ntsw","commitment","REG")
    assert row["علت"] == "NO_COMMON_EVIDENCE"
    assert row["Semantic"] == "UNPROVEN"
    assert "شکل کلید" not in row.get("اقدام", "")


def test_known_incomplete_zero_match_does_not_degrade_system_health():
    import pandas as pd
    from gsi import health
    from gsi.dataio.merge import safe_merge

    health.reset()
    left = pd.DataFrame({"K":["A"], "BASE":[1]})
    right = pd.DataFrame({"K":["B"], "SAP_X":[9]})
    out = safe_merge(left, right, "K", "sap", zero_match_degraded=False)
    assert len(out) == 1
    rec = health.current().joins[-1]
    assert rec.matched == 0
    assert rec.status == health.OK
    assert "ناقص" in rec.note
    assert health.current().findings[-1].severity == health.INFO

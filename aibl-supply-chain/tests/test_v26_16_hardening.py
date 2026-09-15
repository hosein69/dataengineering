# -*- coding: utf-8 -*-
from pathlib import Path
import tempfile
import pandas as pd

from aibl.studio_core.grain import measure_kind, KIND_ADDITIVE
from aibl.studio_core.html_export import build_dynamic_html
from aibl.studio_core.report_builder import ReportSpec, build


def test_unique_large_amounts_are_not_identifiers():
    s=pd.Series([1001,2002,3003,4004,5005,6006])
    for c in ("INVOICE_VALUE","BALANCE","DUTY_AMOUNT","CB_VALUE"):
        assert measure_kind(c,s)==KIND_ADDITIVE, c


def test_html_honors_visuals_tables_without_silent_payload_cap():
    df=pd.DataFrame({"KEY_MATERIAL":[f"M{i}" for i in range(100)],"ORG_DEPT":["A"]*100,"مانده تعهد":range(100)})
    h=build_dynamic_html(df,"2026-09-15",selected_fields=list(df.columns),show_visuals=False,show_tables=False,max_payload_cells=40)
    assert 'id="tb_0"' not in h
    assert '"payload_rows": 100' in h
    assert 'برای پایداری مرورگر' not in h
    assert 'const CHART_CFG={"keys": []' in h


def test_scope_is_applied_before_html_embedding():
    df=pd.DataFrame({"KEY_MATERIAL":["M1","M2"],"ORG_DEPT":["A","B"],"CANONICAL_EXPERT":["Ali","Sara"],"PHONE":["111","222"]})
    with tempfile.TemporaryDirectory() as td:
        spec=ReportSpec(ref_date="2026-09-15",formats=["html"],fields=list(df.columns),departments=["A"],file_stem="scope")
        r=build(df,{},spec,{},td)
        h=Path(r.files["html"]).read_text(encoding="utf-8")
        assert 'M1' in h and 'M2' not in h
        assert 'PHONE' not in h and '222' not in h


def test_pipeline_commitment_kpi_is_grain_safe():
    from types import SimpleNamespace
    from aibl.stages.s50_commitment import CommitmentStage
    df = pd.DataFrame({
        "KEY_REG": ["R1", "R1", "R2"],
        "مانده تعهد": [1000.0, 1000.0, 500.0],
        "جریمه برآوردی": [100.0, 100.0, 50.0],
        "وضعیت کلی هشدار": ["قرمز", "قرمز", "سبز"],
    })
    ctx = SimpleNamespace(rb=SimpleNamespace(status_label=lambda _: "قرمز"))
    k = CommitmentStage().kpis(df, ctx)
    assert k["جمع مانده تعهد"][0] == 1500.0
    assert k["جمع جریمه برآوردی"][0] == 150.0


if __name__ == "__main__":
    tests = [
        test_unique_large_amounts_are_not_identifiers,
        test_html_honors_visuals_tables_without_silent_payload_cap,
        test_scope_is_applied_before_html_embedding,
        test_pipeline_commitment_kpi_is_grain_safe,
    ]
    for fn in tests:
        fn()
        print("✅", fn.__name__)
    print(f"نتیجه: {len(tests)} موفق | 0 ناموفق")

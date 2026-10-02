# -*- coding: utf-8 -*-
from pathlib import Path
import hashlib
import pandas as pd

from gsi.cashflow.process_design import build_cashflow_process_html
from gsi.studio_core.composer import DEFAULT_BLOCKS, BLOCKS, SIZES


def _extras():
    timeline = pd.DataFrame([
        {"KEY_REG":"R1","STAGE_CODE":"ORDER_REG","STATUS":"DONE","EVENT_DATE":"2026-09-01","EVIDENCE":"REG"},
        {"KEY_REG":"R1","STAGE_CODE":"ALLOCATION","STATUS":"DONE","EVENT_DATE":"2026-09-03","EVIDENCE":"ALLOC"},
        {"KEY_REG":"R1","STAGE_CODE":"FX_PURCHASE","STATUS":"DONE","EVENT_DATE":"2026-09-06","EVIDENCE":"FX"},
        {"KEY_REG":"R1","STAGE_CODE":"SETTLEMENT","STATUS":"DONE","EVENT_DATE":"2026-09-20","EVIDENCE":"REL"},
    ])
    ledger = pd.DataFrame([
        {"KEY_REG":"R1","EVENT_CODE":"REGISTRATION_VALUE","EVENT_FA":"ارزش ثبت سفارش","EVENT_DATE":"2026-09-01","AMOUNT":100,"CURRENCY":"EUR","SOURCE":"NTSW","REFERENCE":"REG1","STATUS":"DONE","NOTE":""},
        {"KEY_REG":"R1","EVENT_CODE":"ALLOCATION","EVENT_FA":"تخصیص ارز","EVENT_DATE":"2026-09-03","AMOUNT":95,"CURRENCY":"EUR","SOURCE":"NTSW","REFERENCE":"AL1","STATUS":"DONE","NOTE":""},
        {"KEY_REG":"R1","EVENT_CODE":"COMMITMENT_INITIAL","EVENT_FA":"تعهد اولیه","EVENT_DATE":"2026-09-04","AMOUNT":95,"CURRENCY":"EUR","SOURCE":"NTSW","REFERENCE":"CM1","STATUS":"DONE","NOTE":""},
        {"KEY_REG":"R1","EVENT_CODE":"FX_PURCHASE","EVENT_FA":"خرید ارز","EVENT_DATE":"2026-09-06","AMOUNT":95,"CURRENCY":"EUR","SOURCE":"FX","REFERENCE":"FX1","STATUS":"DONE","NOTE":""},
        {"KEY_REG":"R1","EVENT_CODE":"BANK_FUNDING_IRR","EVENT_FA":"تامین وجه","EVENT_DATE":"2026-09-07","AMOUNT":1000000,"CURRENCY":"IRR","SOURCE":"BANK","REFERENCE":"F1","STATUS":"DONE","NOTE":""},
        {"KEY_REG":"R1","EVENT_CODE":"SUPPLIER_PAYMENT","EVENT_FA":"پرداخت ذی نفع","EVENT_DATE":"2026-09-08","AMOUNT":94,"CURRENCY":"EUR","SOURCE":"FX","REFERENCE":"SW1","STATUS":"DONE","NOTE":""},
        {"KEY_REG":"R1","EVENT_CODE":"COMMITMENT_RELEASED","EVENT_FA":"رفع تعهد","EVENT_DATE":"2026-09-20","AMOUNT":90,"CURRENCY":"EUR","SOURCE":"NTSW","REFERENCE":"REL1","STATUS":"DONE","NOTE":""},
        {"KEY_REG":"R1","EVENT_CODE":"COMMITMENT_BALANCE","EVENT_FA":"مانده تعهد","EVENT_DATE":"2026-09-30","AMOUNT":5,"CURRENCY":"EUR","SOURCE":"NTSW","REFERENCE":"BAL1","STATUS":"DONE","NOTE":""},
    ])
    return {"fx_stage_timeline": timeline, "fx_money_ledger": ledger, "fx_money_reconciliation": pd.DataFrame()}


def test_process_explorer_has_pipeline_dual_graph_drilldown_and_commitment():
    h = build_cashflow_process_html(extras=_extras(), instance_id="t")
    assert 'cfp-pipeline' in h
    assert 'data-role="graph-frequency"' in h
    assert 'data-role="graph-performance"' in h
    assert 'ایجاد تعهد ارزی' in h
    assert 'aria-label="مسیر پول"' in h
    assert 'شواهد مالی / اسنادی مرحله' in h
    assert 'پرونده برای Drill-down' in h
    assert 'ارزهای مختلف هرگز با هم جمع نمی‌شوند' in h


def test_composer_exposes_cashflow_and_layout_sizes():
    assert "cashflow" in BLOCKS
    assert "cashflow" in DEFAULT_BLOCKS["manager"]
    assert set(SIZES) == {"full","half","third","quarter"}


def test_supplied_process_explorer_modules_are_vendored_exactly():
    root = Path(__file__).resolve().parents[1]
    kit = root / "process-mining-ui-kit" / "pm_ui"
    assert (kit / "charts" / "process_flow.py").exists()
    assert (kit / "charts" / "system_flow.py").exists()
    assert (kit / "layout" / "dragdrop.py").exists()
    # Stable known hashes from the user-supplied GSI_Process_Explorer_full_package.zip.
    assert hashlib.sha256((kit/"charts"/"process_flow.py").read_bytes()).hexdigest() == "95705734879f706e1e23c17b7b72c381a47c9b52aacb6cff5feb8f4ba9d10f30"
    assert hashlib.sha256((kit/"charts"/"system_flow.py").read_bytes()).hexdigest() == "b3927f5e14907c6fbc8d3b5c56a8f17fe604dda5ec7e875a953df6ebb1a6fb72"
    assert hashlib.sha256((kit/"layout"/"dragdrop.py").read_bytes()).hexdigest() == "643d4bb1ad314b25141a7a0f8977029282b3b6f600fdbe8eea05dc71898cc0e8"
    frontend = root / "gsi" / "studio_core" / "dragdrop_frontend" / "index.html"
    assert hashlib.sha256(frontend.read_bytes()).hexdigest() == "e0fa2c32183c7477367e65acd8096e8e14e2b88d106b7ffbc2d197138b473227"


def test_streamlit_studio_has_add_remove_reorder_and_resize_controls():
    root = Path(__file__).resolve().parents[1]
    src = (root / "app" / "studio.py").read_text(encoding="utf-8")
    assert "draggable_list" in src
    assert "Blockهای این تب" in src
    assert "نمودارهای همین تب — اضافه/حذف" in src
    assert "اندازه Blockها در HTML" in src
    assert "اندازه نمودارهای این تب" in src
    assert "اندازه نماهای فرآیندی" in src
    assert "gsi_report_blocks_dnd_" in src
    assert "gsi_report_charts_dnd_" in src
    assert "gsi_report_process_dnd_" in src


def test_streamlit_sizes_propagate_into_exported_html():
    import pandas as pd
    from gsi.studio_core.html_export import build_dynamic_html
    df=pd.DataFrame({"KEY_MATERIAL":["M1"],"KEY_REG":["R1"],"بحرانی (کوتاه)":["ایمن"],"مقاومت (روز)":[50.]})
    tabs=[{"title":"T","fields":["KEY_MATERIAL","KEY_REG"],"blocks":["cashflow","charts","process"],
           "block_sizes":{"cashflow":"full","charts":"half","process":"third"},
           "charts":["criticality"],"chart_sizes":{"criticality":"quarter"},
           "process_views":["flow_map"],"process_sizes":{"flow_map":"half"}}]
    h=build_dynamic_html(df,"2026-09-26",audience="manager",tabs=tabs,process_extras={})
    assert 'data-composer-block="charts" data-gsi-size="half"' in h
    assert 'data-composer-block="process" data-gsi-size="third"' in h
    assert '"chart_sizes": {"criticality": "quarter"}' in h
    assert "sizes[k]||'half'" in h
    assert 'data-gsi-process-view="flow_map"' in h and 'data-gsi-size="half"' in h

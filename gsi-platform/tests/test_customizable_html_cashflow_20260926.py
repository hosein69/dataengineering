# -*- coding: utf-8 -*-
import pandas as pd

from gsi.studio_core.html_export import build_dynamic_html


def _df():
    return pd.DataFrame({
        "KEY_MATERIAL": ["M1", "M2"],
        "CANONICAL_ORDER": ["O1", "O2"],
        "KEY_REG": ["R1", "R2"],
        "CASE_KEY": ["R1", "R2"],
        "بحرانی (کوتاه)": ["بحرانی", "ایمن"],
        "کد طبقه بحرانی": ["CRITICAL", "SAFE"],
        "مقاومت (روز)": [5.0, 60.0],
        "مانده تعهد": [100.0, 20.0],
        "روزهای تأخیر": [10.0, 0.0],
    })


def _extras():
    return {
        "eventlog": pd.DataFrame({
            "_CASE_KEY": ["R1", "R1"],
            "CASE_KEY": ["R1", "R1"],
            "ACTIVITY_FA": ["ثبت سفارش", "تخصیص ارز"],
            "EVENTTIME": ["2026-09-01", "2026-09-05"],
        }),
        "bottlenecks": pd.DataFrame({
            "از فعالیت": ["ثبت سفارش"], "به فعالیت": ["تخصیص ارز"],
            "میانه روز": [4.0], "صدک ۹۰ روز": [7.0], "تعداد پرونده": [1],
        }),
        "variants": pd.DataFrame({
            "VARIANT": ["ثبت سفارش > تخصیص ارز"], "تعداد پرونده": [1],
            "سهم (٪)": [100.0], "پرونده بسته": [1], "میانه چرخه": [4.0],
        }),
        "fx_ledger": pd.DataFrame({
            "KEY_REG": ["R1"], "FX_NTSW_BALANCE": [100.0],
            "FX_NTSW_CURRENCY": ["EUR"], "FX_NTSW_BALANCE_EUR_EQ": [100.0],
            "FX_NTSW_BALANCE_RIAL_EQ": [1000.0], "FX_ANOMALY_COUNT": [1],
        }),
        "fx_control_summary": pd.DataFrame({
            "KEY_REG": ["R1"], "FX_CURRENT_STAGE": ["تخصیص ارز"],
            "FX_CONTROL_RISK_BAND": ["HIGH"], "FX_CONTROL_RISK_SCORE": [80],
            "FX_DEADLINE_STATUS": ["OVERDUE"], "FX_DEADLINE_DATE": ["2026-09-20"],
            "FX_DAYS_REMAINING": [-6], "FX_UNAUTHORIZED_REALLOCATION_COUNT": [1],
            "FX_CONVERSION_STATUS": ["EVIDENCE_GAP"], "FX_CONVERSION_IMPACT_RIAL": [500],
        }),
    }


def test_html_has_offline_layout_customizer_and_portable_seed():
    h = build_dynamic_html(_df(), "2026-09-26", audience="manager", process_extras=_extras())
    assert 'data-gsi-custom-action="toggle"' in h
    assert 'id="gsi-layout-seed"' in h
    assert "دانلود HTML سفارشی" in h
    assert "gsiCustomizerRefresh" in h
    assert "data-gsi-hidden" in h


def test_cashflow_is_a_real_default_composer_block_and_rendered_runtime_target():
    h = build_dynamic_html(_df(), "2026-09-26", audience="manager", process_extras=_extras())
    assert 'data-composer-block="cashflow"' in h
    assert 'data-gsi-cashflow-process="1"' in h
    assert "نقشه الگوریتمی مسیر پول و تعهد" in h
    assert 'data-role="graph-frequency"' in h
    assert 'data-role="graph-performance"' in h
    assert 'aria-label="مسیر پول"' in h


def test_charts_and_process_views_get_stable_customization_keys():
    h = build_dynamic_html(
        _df(), "2026-09-26", audience="manager", process_extras=_extras(),
        charts=["criticality", "low_resistance"],
        tabs=[{"title": "مدیریتی", "fields": ["KEY_MATERIAL", "مقاومت (روز)"],
               "blocks": ["cashflow", "charts", "process"],
               "process_views": ["flow_map", "variants"]}],
    )
    assert "gsi-chart-item" in h
    assert "data-gsi-item-key=\"chart:" in h
    assert 'data-gsi-process-view="flow_map"' in h
    assert 'data-gsi-item-key="process:variants"' in h

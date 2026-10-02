from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from gsi.report.dashboard import ExcelDashboardBuilder, SHEET_COMMIT, SHEET_SCORECARD
from gsi.report.financial_summary import (
    commitment_display,
    commitment_numeric_if_single_currency,
    commitment_status_summary,
    penalty_display,
)
from gsi.report.history import snapshot
from gsi.stages.s50_commitment import CommitmentStage


def financial_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "KEY_REG": ["R1", "R1", "R2", "R3"],
        "CANONICAL_REG": ["R1", "R1", "R2", "R3"],
        "CANONICAL_BL": ["B1", "B2", "B3", "B4"],
        "NTSW_CURRENCY": ["USD", "USD", "EUR", "USD"],
        "مانده تعهد": [100.0, 100.0, 50.0, 0.0],
        "جریمه برآوردی": [10.0, 10.0, 5.0, 0.0],
        "BALANCE_IS_UNKNOWN": [False, False, False, True],
        "روزهای تأخیر": [3.0, 3.0, 0.0, 0.0],
    })


def test_commitment_display_dedupes_reg_splits_currency_and_respects_unknown():
    df = financial_frame().iloc[:3].copy()
    assert commitment_display(df) == "50.00 EUR | 100.00 USD"
    assert penalty_display(df) == "5.00 EUR | 10.00 USD"

    unknown = financial_frame().copy()
    assert "نامشخص" in commitment_display(unknown)
    assert "نامشخص" in penalty_display(unknown)


def test_status_summary_never_turns_unknown_balance_into_settled():
    summary, diag = commitment_status_summary(financial_frame())
    assert diag["unknown"] == 1
    assert diag["conflict"] == 0
    got = {(r.currency, r.status): (r.amount, r.count) for r in summary.itertuples(index=False)}
    assert got[("USD", "معوق")] == (100.0, 1)
    assert got[("EUR", "در مهلت")] == (50.0, 1)
    assert ("USD", "تسویه‌شده") not in got


def test_numeric_financial_value_is_refused_for_mixed_currency():
    value, currency, display = commitment_numeric_if_single_currency(financial_frame().iloc[:3])
    assert value is None and currency is None
    assert display == "50.00 EUR | 100.00 USD"

    one = financial_frame().iloc[:2].copy()
    value, currency, display = commitment_numeric_if_single_currency(one)
    assert value == 100.0 and currency == "USD" and display == "100.00 USD"


def test_excel_commitment_total_is_not_raw_subtotal(tmp_path: Path):
    df = financial_frame().iloc[:3].copy()
    b = ExcelDashboardBuilder(str(tmp_path / "x.xlsx"))
    b.build_commitment(df)
    ws = b.wb[SHEET_COMMIT]
    total_row = len(df) + 3
    assert ws.cell(total_row, 6).value == "50.00 EUR | 100.00 USD"
    assert ws.cell(total_row, 11).value == "5.00 EUR | 10.00 USD"
    assert not str(ws.cell(total_row, 6).value).startswith("=")


def test_scorecard_finance_is_reg_grain_and_currency_aware(tmp_path: Path):
    df = financial_frame().iloc[:3].copy()
    df["ORG_VICE"] = "V"
    df["ORG_DEPT"] = "D"
    df["ORG_MANAGER"] = "M"
    df["ORG_HEAD"] = "H"
    df["CANONICAL_EXPERT"] = "E"
    df["KEY_EMP"] = "1"
    df["روزهای رسوب"] = [2.0, 3.0, 4.0]
    df["امتیاز ریسک"] = [10.0, 20.0, 30.0]
    df["BL_CRITICAL"] = False
    df["BL_CRITICAL_LEVEL"] = "SAFE"

    b = ExcelDashboardBuilder(str(tmp_path / "s.xlsx"))
    b.build_scorecard(df)
    ws = b.wb[SHEET_SCORECARD]
    assert ws.cell(2, 11).value == "50.00 EUR | 100.00 USD"
    assert ws.cell(2, 12).value == "5.00 EUR | 10.00 USD"


def test_history_keeps_legacy_numeric_but_refuses_cross_currency_number():
    legacy = pd.DataFrame({
        "KEY_REG": ["R1", "R1", "R2"],
        "مانده تعهد": [1000.0, 1000.0, 500.0],
        "روزهای تأخیر": [5.0, 5.0, 0.0],
    })
    old = snapshot(legacy, "2026-09-23")
    assert old["مانده تعهد"] == 1500.0
    assert old["مانده تعهد معوق"] == 1000.0

    mixed = financial_frame().iloc[:3].copy()
    new = snapshot(mixed, "2026-09-23")
    assert new["مانده تعهد"] is None
    assert new["ارز مانده تعهد"] == "چندارزی/نامشخص"
    assert new["مانده تعهد نمایشی"] == "50.00 EUR | 100.00 USD"


def test_pipeline_kpi_becomes_currency_aware_when_currency_contract_exists():
    df = financial_frame().iloc[:3].copy()
    df["وضعیت کلی هشدار"] = ["قرمز", "قرمز", "سبز"]
    ctx = SimpleNamespace(rb=SimpleNamespace(status_label=lambda _: "قرمز"))
    k = CommitmentStage().kpis(df, ctx)
    assert k["جمع مانده تعهد"][0] == "50.00 EUR | 100.00 USD"
    assert k["جمع جریمه برآوردی"][0] == "5.00 EUR | 10.00 USD"


def test_studio_kpi_uses_shared_financial_summary_not_raw_sum():
    text = (Path(__file__).parents[1] / "app" / "studio.py").read_text(encoding="utf-8")
    assert "commit = commitment_display(fdf)" in text
    assert 'pd.to_numeric(fdf.get("مانده تعهد"), errors="coerce").sum()' not in text

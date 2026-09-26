# -*- coding: utf-8 -*-
"""V29.8.2 — source-backed EUR/IRR equivalents and currency-safe FX totals."""
from datetime import date

import pandas as pd
import pytest

from gsi.finance.equivalents import (commitment_equivalents, summarize_credit_equivalents,
                                     summarize_fx_purchases)
from gsi.report.financial_summary import commitment_equivalent_summary
from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext
from gsi.stages.s55_fx_traceability import FxTraceabilityStage


def test_purchase_summary_keeps_native_currencies_separate_but_sums_reported_equivalents():
    fx = pd.DataFrame([
        {"FX_AMOUNT": 100, "FX_CURRENCY": "EUR", "FX_EUR_VALUE": 100, "FX_RIAL_VALUE": 60_000_000},
        {"FX_AMOUNT": 200, "FX_CURRENCY": "USD", "FX_EUR_VALUE": 180, "FX_RIAL_VALUE": 120_000_000},
    ])
    x = summarize_fx_purchases(fx)
    assert x.single_native_amount is None
    assert "100.00 EUR" in x.native_display and "200.00 USD" in x.native_display
    assert x.source_eur_total == 280
    assert x.source_rial_total == 180_000_000
    assert x.eur_coverage_pct == 100 and x.rial_coverage_pct == 100


def test_purchase_equivalent_coverage_is_explicit_not_silently_zero_filled():
    fx = pd.DataFrame([
        {"FX_AMOUNT": 100, "FX_CURRENCY": "USD", "FX_EUR_VALUE": 90, "FX_RIAL_VALUE": 60_000_000},
        {"FX_AMOUNT": 50, "FX_CURRENCY": "USD", "FX_EUR_VALUE": None, "FX_RIAL_VALUE": None},
    ])
    x = summarize_fx_purchases(fx)
    assert x.single_native_amount == 150
    assert x.source_eur_total == 90
    assert x.source_rial_total == 60_000_000
    assert x.eur_coverage_pct == 50 and x.rial_coverage_pct == 50


def test_commitment_uses_same_reg_same_currency_reported_equivalent_rates():
    reg = "12345678"
    fx = pd.DataFrame([
        {"KEY_REG": reg, "FX_AMOUNT": 1000, "FX_CURRENCY": "USD",
         "FX_EUR_VALUE": 900, "FX_RIAL_VALUE": 600_000_000, "FX_RATE": 590_000},
        # Different currency must never enter the USD valuation.
        {"KEY_REG": reg, "FX_AMOUNT": 100, "FX_CURRENCY": "EUR",
         "FX_EUR_VALUE": 100, "FX_RIAL_VALUE": 70_000_000, "FX_RATE": 700_000},
        # Different REG must never enter this valuation.
        {"KEY_REG": "87654321", "FX_AMOUNT": 1000, "FX_CURRENCY": "USD",
         "FX_EUR_VALUE": 500, "FX_RIAL_VALUE": 100_000_000, "FX_RATE": 100_000},
    ])
    out = commitment_equivalents(reg=reg, currency="USD", balance=500, initial=1000, fx_rows=fx)
    assert out["FX_NTSW_BALANCE_EUR_EQ"] == pytest.approx(450)
    assert out["FX_NTSW_BALANCE_RIAL_EQ"] == pytest.approx(300_000_000)
    assert out["FX_NTSW_INITIAL_EUR_EQ"] == pytest.approx(900)
    assert "SAME_REG_CURRENCY" in out["FX_NTSW_EUR_EQ_BASIS"]
    assert "SOURCE_REPORTED_RIAL" in out["FX_NTSW_RIAL_EQ_BASIS"]


def test_commitment_irr_falls_back_to_ntsw_allocation_same_case_rate_only():
    reg = "12345678"
    alloc = pd.DataFrame([
        {"KEY_REG": reg, "NTSW_REQ_CURRENCY": "USD", "NTSW_FX_RATE_NUMERIC": 600_000,
         "NTSW_REQ_DATE": "2026-01-01"},
        {"KEY_REG": reg, "NTSW_REQ_CURRENCY": "USD", "NTSW_FX_RATE_NUMERIC": 620_000,
         "NTSW_REQ_DATE": "2026-02-01"},
        {"KEY_REG": reg, "NTSW_REQ_CURRENCY": "EUR", "NTSW_FX_RATE_NUMERIC": 700_000,
         "NTSW_REQ_DATE": "2026-03-01"},
    ])
    out = commitment_equivalents(reg=reg, currency="USD", balance=100, allocation_rows=alloc)
    assert out["FX_NTSW_BALANCE_RIAL_EQ"] == pytest.approx(62_000_000)
    assert out["FX_NTSW_BALANCE_EUR_EQ"] is None
    assert out["FX_NTSW_RIAL_EQ_BASIS"] == "NTSW_ALLOCATION_LATEST_RATE_SAME_REG_CURRENCY"


def test_eur_commitment_has_identity_eur_equivalent_without_inventing_irr():
    out = commitment_equivalents(reg="12345678", currency="EUR", balance=125.5)
    assert out["FX_NTSW_BALANCE_EUR_EQ"] == pytest.approx(125.5)
    assert out["FX_NTSW_BALANCE_RIAL_EQ"] is None
    assert out["FX_NTSW_EUR_EQ_BASIS"] == "NTSW_NATIVE_EUR"


def test_equivalent_portfolio_summary_deduplicates_bl_material_fanout():
    df = pd.DataFrame([
        {"KEY_REG":"R1", "FX_NTSW_BALANCE_EUR_EQ":100, "FX_NTSW_BALANCE_RIAL_EQ":60_000_000},
        {"KEY_REG":"R1", "FX_NTSW_BALANCE_EUR_EQ":100, "FX_NTSW_BALANCE_RIAL_EQ":60_000_000},
        {"KEY_REG":"R2", "FX_NTSW_BALANCE_EUR_EQ":200, "FX_NTSW_BALANCE_RIAL_EQ":120_000_000},
    ])
    s = commitment_equivalent_summary(df)
    assert s["eur"] == 300
    assert s["irr"] == 180_000_000
    assert s["total"] == 2 and s["status"] == "COMPLETE"


def test_fx_stage_mixed_purchase_currency_has_no_naked_native_total_and_values_commitment():
    reg = "12345678"
    sources = {
        "fx_transaction": {"main": pd.DataFrame([
            {"KEY_REG":reg, "FX_AMOUNT":100, "FX_CURRENCY":"USD", "FX_EUR_VALUE":90,
             "FX_RIAL_VALUE":60_000_000, "FX_RATE":600_000, "FX_BUY_DATE":"2026-01-01"},
            {"KEY_REG":reg, "FX_AMOUNT":50, "FX_CURRENCY":"EUR", "FX_EUR_VALUE":50,
             "FX_RIAL_VALUE":35_000_000, "FX_RATE":700_000, "FX_BUY_DATE":"2026-01-02"},
        ])},
        "ntsw": {
            "commitment": pd.DataFrame([{
                "KEY_REG":reg, "NTSW_INITIAL_COMMIT":100, "NTSW_BALANCE":50,
                "NTSW_CURRENCY":"USD", "NTSW_COMMIT_DATE":"2026-01-03",
                "NTSW_RELEASE_STATUS":"رفع تعهد نشده",
            }]),
            "allocation": pd.DataFrame(),
            "allocation_rows": pd.DataFrame(),
        },
        "credit": {"main": pd.DataFrame()},
    }
    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 23)),
                          today=date(2026, 9, 23), sources=sources)
    df = pd.DataFrame([{"CANONICAL_REG":reg, "CANONICAL_BL":"B1", "IS_FULL_CLEARED":False}])
    out = FxTraceabilityStage().run(df, ctx)
    row = ctx.extras["fx_ledger"].iloc[0]
    assert pd.isna(row["FX_PURCHASED_AMOUNT"])
    assert "100.00 USD" in row["FX_PURCHASED_NATIVE_DISPLAY"]
    assert row["FX_EUR_EQUIVALENT"] == 140
    assert row["FX_RIAL_OUTFLOW_REPORTED"] == 95_000_000
    # Commitment is USD, so only USD purchase evidence determines its reference equivalent.
    assert row["FX_NTSW_BALANCE_EUR_EQ"] == pytest.approx(45)
    assert row["FX_NTSW_BALANCE_RIAL_EQ"] == pytest.approx(30_000_000)
    assert out["FX_NTSW_BALANCE_EUR_EQ"].iloc[0] == pytest.approx(45)



def test_credit_direct_equivalents_dedupe_same_lc_snapshot():
    cr = pd.DataFrame([
        {"CRD_LC_NO":"LC1", "CRD_EUR_AMOUNT":500, "CRD_RIAL_AMOUNT":300_000_000},
        {"CRD_LC_NO":"LC1", "CRD_EUR_AMOUNT":500, "CRD_RIAL_AMOUNT":300_000_000},
        {"CRD_LC_NO":"LC2", "CRD_EUR_AMOUNT":200, "CRD_RIAL_AMOUNT":120_000_000},
    ])
    x = summarize_credit_equivalents(cr)
    assert x.source_eur_total == 700
    assert x.source_rial_total == 420_000_000
    assert x.status == "EUR_AND_IRR_REPORTED"
    assert x.logical_credit_count == 2


def test_credit_conflicting_same_lc_equivalent_is_not_guessed():
    cr = pd.DataFrame([
        {"CRD_LC_NO":"LC1", "CRD_EUR_AMOUNT":500, "CRD_RIAL_AMOUNT":300_000_000},
        {"CRD_LC_NO":"LC1", "CRD_EUR_AMOUNT":550, "CRD_RIAL_AMOUNT":300_000_000},
    ])
    x = summarize_credit_equivalents(cr)
    assert x.source_eur_total is None
    assert x.source_rial_total == 300_000_000
    assert x.status == "CONFLICTING_SOURCE_EQUIVALENTS"


def test_stage_exposes_credit_source_equivalents_without_recalculating_them():
    reg = "12345678"
    sources = {
        "fx_transaction": {"main": pd.DataFrame()},
        "ntsw": {"commitment": pd.DataFrame(), "allocation": pd.DataFrame(), "allocation_rows": pd.DataFrame()},
        "credit": {"main": pd.DataFrame([
            {"KEY_REG":reg, "CRD_LC_NO":"LC1", "CRD_EUR_AMOUNT":800,
             "CRD_RIAL_AMOUNT":480_000_000, "CRD_PROFORMA_VALUE":900,
             "CRD_PREPAYMENT":0, "CRD_REMAINING":100},
        ])},
    }
    ctx = PipelineContext(rb=get_rulebook(reload=True, as_of=date(2026, 9, 23)),
                          today=date(2026, 9, 23), sources=sources)
    df = pd.DataFrame([{"CANONICAL_REG":reg, "CANONICAL_BL":"", "IS_FULL_CLEARED":False}])
    out = FxTraceabilityStage().run(df, ctx)
    assert out["FX_CREDIT_EUR_REPORTED"].iloc[0] == 800
    assert out["FX_CREDIT_RIAL_REPORTED"].iloc[0] == 480_000_000
    assert out["FX_CREDIT_EQ_STATUS"].iloc[0] == "EUR_AND_IRR_REPORTED"


@pytest.mark.parametrize("missing", ["KEY_REG", "FX_CURRENCY"])
def test_purchase_rate_missing_identity_cannot_value_other_case(missing):
    fx = pd.DataFrame([{"KEY_REG": "OTHER", "FX_CURRENCY": "USD", "FX_AMOUNT": 100,
                        "FX_EUR_VALUE": 90, "FX_RIAL_VALUE": 60_000_000}])
    out = commitment_equivalents(reg="TARGET", currency="USD", balance=10,
                                 fx_rows=fx.drop(columns=missing))
    assert out["FX_NTSW_BALANCE_EUR_EQ"] is None
    assert out["FX_NTSW_BALANCE_RIAL_EQ"] is None

@pytest.mark.parametrize("missing", ["KEY_REG", "NTSW_REQ_CURRENCY"])
def test_allocation_rate_missing_identity_cannot_value_other_case(missing):
    alloc = pd.DataFrame([{"KEY_REG": "OTHER", "NTSW_REQ_CURRENCY": "USD",
                           "NTSW_FX_RATE_NUMERIC": 600_000}])
    out = commitment_equivalents(reg="TARGET", currency="USD", balance=10,
                                 allocation_rows=alloc.drop(columns=missing))
    assert out["FX_NTSW_BALANCE_RIAL_EQ"] is None

def test_conflicted_registration_remains_in_coverage_denominator():
    df = pd.DataFrame([
        {"KEY_REG": "R1", "FX_NTSW_BALANCE_EUR_EQ": 100, "FX_NTSW_BALANCE_RIAL_EQ": 10},
        {"KEY_REG": "R2", "FX_NTSW_BALANCE_EUR_EQ": 200, "FX_NTSW_BALANCE_RIAL_EQ": 20},
        {"KEY_REG": "R2", "FX_NTSW_BALANCE_EUR_EQ": 300, "FX_NTSW_BALANCE_RIAL_EQ": 20},
    ])
    s = commitment_equivalent_summary(df)
    assert s["total"] == 2 and s["conflicted"] == 1
    assert s["eur"] == 100 and s["eur_covered"] == 1
    assert s["status"] == "PARTIAL"

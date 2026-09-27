"""Counterexamples for stable advisory identity and evidence-bound stages."""
from datetime import date

import pandas as pd

from gsi.rulebook import get_rulebook
from gsi.stages.base import PipelineContext
from gsi.stages.s55_fx_traceability import FxTraceabilityStage
from gsi.stages.s56_money_flow_control import MoneyFlowControlStage
from gsi.stages.s58_case_actions import CaseActionStage


def context(sources=None):
    today = date(2026, 9, 27)
    return PipelineContext(rb=get_rulebook(reload=True, as_of=today), today=today,
                           sources=sources or {})


def test_action_id_survives_changed_due_date():
    stage = CaseActionStage()
    df = pd.DataFrame({"CANONICAL_REG": ["R1"]})
    ledger = pd.DataFrame({"KEY_REG": ["R1"]})
    def actions(when):
        timeline = pd.DataFrame([{"KEY_REG": "R1", "STAGE_CODE": "ALLOCATION_QUEUE",
                                  "STATUS": "CURRENT", "EVENT_DATE": when,
                                  "EVIDENCE": "درخواست باز"}])
        return stage._build_actions(df, context(), ledger, timeline, None, None)
    earlier, corrected = actions("2026-09-01"), actions("2026-09-02")
    assert earlier.ACTION_ID.iloc[0] == corrected.ACTION_ID.iloc[0]
    assert earlier.DUE_DATE.iloc[0] != corrected.DUE_DATE.iloc[0]


def test_planned_purchase_is_not_a_completed_purchase():
    fx = pd.DataFrame([{"KEY_REG": "R1", "FX_AMOUNT": 100, "FX_CURRENCY": "EUR",
                        "FX_BUY_DATE": "2026-09-01", "FX_PURCHASE_STATE": "PLANNED",
                        "FX_STATUS": "در برنامه خرید"}])
    ctx = context({"fx_transaction": {"main": fx}})
    df = pd.DataFrame({"CANONICAL_REG": ["R1"]})
    FxTraceabilityStage().run(df, ctx)
    row = ctx.extras["fx_ledger"].iloc[0]
    assert not row.FX_LAST_BUY_DATE
    timeline = MoneyFlowControlStage()._build_timeline(df, ctx, ctx.extras["fx_ledger"],
                                                       pd.DataFrame())
    assert timeline.loc[timeline.STAGE_CODE.eq("FX_PURCHASE"), "STATUS"].iloc[0] != "DONE"


def test_positive_commitment_balance_blocks_textual_settlement():
    ledger = pd.DataFrame([{"KEY_REG": "R1", "FX_NTSW_INITIAL": 100,
                            "FX_NTSW_BALANCE": 50, "FX_NTSW_RELEASE_STATUS": "رفع تعهد شده"}])
    ctx = context()
    df = pd.DataFrame({"CANONICAL_REG": ["R1"]})
    timeline = MoneyFlowControlStage()._build_timeline(df, ctx, ledger, pd.DataFrame())
    settlement = timeline[timeline.STAGE_CODE.eq("SETTLEMENT")].iloc[0]
    assert settlement.STATUS != "DONE"
    assert "50" in settlement.EVIDENCE


def test_unknown_balance_is_not_rendered_as_zero_in_action():
    ledger = pd.DataFrame([{"KEY_REG": "R1", "FX_NTSW_BALANCE": None}])
    timeline = pd.DataFrame([
        {"KEY_REG": "R1", "STAGE_CODE": "BANK_DOCS", "STATUS": "DONE", "EVENT_DATE": "2026-09-10"},
        {"KEY_REG": "R1", "STAGE_CODE": "SETTLEMENT", "STATUS": "CURRENT", "EVENT_DATE": ""},
    ])
    actions = CaseActionStage()._build_actions(pd.DataFrame({"CANONICAL_REG": ["R1"]}),
                                               context(), ledger, timeline, None, None)
    row = actions.loc[actions.ACTION_CODE.eq("BANK_DOCS_COMMITMENT_OPEN")].iloc[0]
    assert "نامعلوم" in row.RATIONALE
    assert "0.00" not in row.RATIONALE

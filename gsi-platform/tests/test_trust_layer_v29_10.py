# -*- coding: utf-8 -*-
"""V29.10 — the data-trust layer's non-negotiable invariants.

Each test here pins one promise made in ``docs/DATA_STRATEGY_FA.md``. If one of
them fails, the layer is no longer telling the truth about the data, which is
worse than not having it at all.
"""
from datetime import date

import pandas as pd
import pytest

from gsi.trust import assess
from gsi.trust import codes as C
from gsi.trust.contracts import BL, KEY_COLUMN, MATERIAL, REG, RULES
from gsi.trust.fitness import (ADDITIVE, DECISION_GRADE, DIRECTIONAL, DISTRIBUTIONAL,
                               NOT_USABLE, DecisionContract, evaluate)
from gsi.trust.impact import rank_opportunities
from gsi.trust.profiling import CURRENCY, DATE, KEY, NUMBER, FieldRule, profile_frame

REF = date(2026, 8, 31)


def _mart() -> pd.DataFrame:
    """A mart with the shapes that break naive quality tools.

    * ``R1`` is clean and **fans out over three bills of lading** — the single
      most common way a defect count gets inflated by 3x.
    * ``R2`` has no commitment balance.
    * ``R3`` carries two different currencies for one registration.
    """
    rows = [
        # R1 — clean, three shipment rows
        *[{"CANONICAL_REG": "10000001", "CANONICAL_BL": f"BL{i}", "KEY_MATERIAL": f"M{i}",
           "مانده تعهد": 1000.0, "FX_NTSW_CURRENCY": "EUR",
           "مهلت قانونی رفع تعهد": "1405/09/01", "NTSW_RELEASE_STATUS": "رفع تعهد نشده",
           "BL_DATE": "1405/05/01", "نیاز روزانه": 10, "موجودی ایران خودرو": 100,
           "موجودی ساپکو": 50, "EXPERT_SETTLEMENT": "زهرا الف",
           "EXPERT_LOGISTICS": "کاوه ب", "EXPERT_COMMERCIAL": "نگار پ",
           "ORG_DEPT": "خرید خارجی", "_SOURCE_FILE": "ntsw.xlsx",
           "_SOURCE_SHEET": "Release Commitment", "_SOURCE_ROW": 10 + i}
          for i in (1, 2, 3)],
        # R2 — balance missing
        {"CANONICAL_REG": "10000002", "CANONICAL_BL": "BL4", "KEY_MATERIAL": "M4",
         "مانده تعهد": None, "FX_NTSW_CURRENCY": "EUR",
         "مهلت قانونی رفع تعهد": "1405/09/01", "NTSW_RELEASE_STATUS": "رفع تعهد نشده",
         "BL_DATE": "1405/05/02", "نیاز روزانه": 5, "موجودی ایران خودرو": 20,
         "موجودی ساپکو": 10, "EXPERT_SETTLEMENT": "زهرا الف",
         "EXPERT_LOGISTICS": "کاوه ب", "EXPERT_COMMERCIAL": "نگار پ",
         "ORG_DEPT": "خرید خارجی", "_SOURCE_FILE": "ntsw.xlsx",
         "_SOURCE_SHEET": "Release Commitment", "_SOURCE_ROW": 20},
        # R3 — same registration, two currencies across its rows
        *[{"CANONICAL_REG": "10000003", "CANONICAL_BL": f"BL{5 + i}", "KEY_MATERIAL": f"M{5 + i}",
           "مانده تعهد": 500.0, "FX_NTSW_CURRENCY": cur,
           "مهلت قانونی رفع تعهد": "1405/09/01", "NTSW_RELEASE_STATUS": "رفع تعهد نشده",
           "BL_DATE": "1405/05/03", "نیاز روزانه": 8, "موجودی ایران خودرو": 40,
           "موجودی ساپکو": 20, "EXPERT_SETTLEMENT": "زهرا الف",
           "EXPERT_LOGISTICS": "کاوه ب", "EXPERT_COMMERCIAL": "نگار پ",
           "ORG_DEPT": "خرید خارجی", "_SOURCE_FILE": "ntsw.xlsx",
           "_SOURCE_SHEET": "Release Commitment", "_SOURCE_ROW": 30 + i}
          for i, cur in enumerate(("EUR", "CNY"))],
    ]
    return pd.DataFrame(rows)


def _reg_profile(df=None):
    return profile_frame(df if df is not None else _mart(), list(RULES[REG]),
                         entity_type=REG, key_column=KEY_COLUMN[REG], ref_date=REF)


# ── invariant 1: nothing is deleted ─────────────────────────────────────────
def test_profiling_never_removes_a_row_or_mutates_the_mart():
    df = _mart()
    before = df.copy(deep=True)
    report = assess(df, ref_date=REF)
    pd.testing.assert_frame_equal(df, before)          # untouched
    assert len(df) == len(before) == 6
    assert len(report.ledger) > 0                      # defects live beside it


# ── invariant 2: entity grain, not row grain ────────────────────────────────
def test_fan_out_does_not_multiply_a_single_missing_cell():
    # R1 occupies three rows. A defect on a registration-grain field must be
    # reported once — reporting it three times would treble every count and
    # send the owner three tickets for one cell.
    df = _mart()
    df.loc[df["CANONICAL_REG"] == "10000001", "مهلت قانونی رفع تعهد"] = None
    profile = _reg_profile(df)
    deadline = [d for d in profile.ledger
                if d.entity_key == "10000001" and d.field_name == "مهلت قانونی رفع تعهد"]
    assert len(deadline) == 1
    assert profile.entities == 3                       # three registrations, not six rows


# ── invariant 3: unknown is not zero ────────────────────────────────────────
def test_missing_balance_is_unknown_not_zero_and_stays_out_of_the_total():
    profile = _reg_profile()
    assert profile.state_of("10000002", "مانده تعهد") == C.MISSING

    from gsi.trust.contracts import BY_ID
    verdict = evaluate(BY_ID["FX_COMMITMENT_TOTAL"], profile, _mart(), KEY_COLUMN[REG])
    # R1 is the only fully-clean registration: 1000 EUR, and nothing else.
    assert verdict.known_total == {"EUR": 1000.0}
    assert verdict.ready == 1 and verdict.entities == 3
    assert "نامعلوم" in verdict.total_display()


# ── invariant 4: a grade belongs to (decision, record), not to the record ───
def test_same_record_is_usable_for_one_decision_and_not_for_another():
    """The heart of the strategy: no record is globally good or globally bad."""
    df = _mart()
    # R2 has no commitment balance but a perfectly good bill-of-lading date.
    reg_profile = _reg_profile(df)
    bl_profile = profile_frame(df, list(RULES[BL]), entity_type=BL,
                               key_column=KEY_COLUMN[BL], ref_date=REF)

    from gsi.trust.contracts import BY_ID
    money = evaluate(BY_ID["FX_COMMITMENT_TOTAL"], reg_profile, df, KEY_COLUMN[REG])
    tracking = evaluate(BY_ID["SHIPMENT_TRACKING"], bl_profile, df, KEY_COLUMN[BL])

    assert reg_profile.state_of("10000002", "مانده تعهد") != C.OK   # unusable for money
    assert bl_profile.state_of("BL4", "BL_DATE") == C.OK            # usable for tracking
    assert tracking.grade == DECISION_GRADE
    assert money.grade != DECISION_GRADE


# ── invariant 5: additive metrics are stricter than distributional ones ─────
def test_additive_metric_is_never_green_while_a_case_is_unknown():
    df = _mart()
    profile = _reg_profile(df)
    common = dict(entity_type=REG, required=("CANONICAL_REG", "مانده تعهد"),
                  amount_field="مانده تعهد", currency_field="FX_NTSW_CURRENCY",
                  directional_floor=50.0)
    additive = DecisionContract(id="A", title_fa="جمع", question_fa="؟",
                                aggregation=ADDITIVE, **common)
    distributional = DecisionContract(id="D", title_fa="رتبه", question_fa="؟",
                                      aggregation=DISTRIBUTIONAL,
                                      decision_floor=60.0, **common)
    a = evaluate(additive, profile, df, KEY_COLUMN[REG])
    d = evaluate(distributional, profile, df, KEY_COLUMN[REG])
    assert a.coverage_pct == d.coverage_pct           # same data
    assert a.grade == DIRECTIONAL                     # a sum with a hole is wrong
    assert d.grade == DECISION_GRADE                  # a ranking survives the hole


# ── invariant 6: contradiction is fail-closed ───────────────────────────────
def test_conflicting_currency_blocks_decision_grade_and_is_reported():
    profile = _reg_profile()
    assert profile.state_of("10000003", "FX_NTSW_CURRENCY") == C.CONFLICT
    codes_seen = {d.code for d in profile.ledger if d.entity_key == "10000003"}
    assert "VALUE_CONFLICT" in codes_seen

    from gsi.trust.contracts import BY_ID
    verdict = evaluate(BY_ID["FX_COMMITMENT_TOTAL"], profile, _mart(), KEY_COLUMN[REG])
    assert verdict.conflicted == 1
    assert verdict.grade != DECISION_GRADE
    assert verdict.known_total.get("CNY") is None     # conflicted case enters no total


def test_currencies_are_never_added_together():
    df = _mart()
    df.loc[df["CANONICAL_REG"] == "10000002", "مانده تعهد"] = 7.0
    df.loc[df["CANONICAL_REG"] == "10000002", "FX_NTSW_CURRENCY"] = "CNY"
    from gsi.trust.contracts import BY_ID
    verdict = evaluate(BY_ID["FX_COMMITMENT_TOTAL"], _reg_profile(df), df, KEY_COLUMN[REG])
    assert verdict.known_total == {"EUR": 1000.0, "CNY": 7.0}
    assert "EUR" in verdict.total_display() and "CNY" in verdict.total_display()


# ── invariant 7: every defect carries evidence and an owner ─────────────────
def test_every_defect_can_be_found_and_routed():
    report = assess(_mart(), ref_date=REF)
    assert len(report.ledger) > 0
    for defect in report.ledger:
        assert defect.evidence.column, "defect without a column is unactionable"
        assert defect.evidence.locator_fa and defect.evidence.locator_fa != "—"
        assert defect.spec.action_fa                   # always says what to do


def test_field_defects_route_to_the_role_that_owns_that_field():
    df = _mart()
    df.loc[df["CANONICAL_REG"] == "10000002", "مهلت قانونی رفع تعهد"] = None
    df["BL_DATE"] = None
    report = assess(df, ref_date=REF)
    by_field = {(d.field_name, d.owner.name) for d in report.ledger}
    # settlement fields go to the settlement expert, shipment dates to logistics
    assert ("مهلت قانونی رفع تعهد", "زهرا الف") in by_field
    assert ("BL_DATE", "کاوه ب") in by_field


# ── invariant 8: the promise made to an owner is arithmetically honest ──────
def test_a_case_blocked_in_two_decisions_is_still_one_cell_and_one_case():
    df = _mart()
    # The deadline blocks both FX_DEADLINE_RISK and PENALTY_EXPOSURE.
    df.loc[df["CANONICAL_REG"] == "10000001", "مهلت قانونی رفع تعهد"] = None
    profile = _reg_profile(df)
    from gsi.trust.contracts import contracts_for
    opps = rank_opportunities(list(contracts_for(REG)), profile, df, KEY_COLUMN[REG])
    deadline = [o for o in opps if o.field == "مهلت قانونی رفع تعهد"][0]
    assert deadline.cells == 1
    assert deadline.entities_unlocked <= deadline.cells
    assert deadline.entities_unlocked >= 1
    # value must not be counted once per decision either
    assert deadline.value_unlocked.get("EUR", 0.0) in (0.0, 1000.0)


def test_opportunity_never_promises_more_than_it_unlocks():
    report = assess(_mart(), ref_date=REF)
    for opp in report.opportunities:
        assert opp.entities_unlocked <= opp.entities_touched
        assert opp.cells == opp.entities_touched
        if opp.entities_unlocked:
            assert "قابل تصمیم می‌شود" in opp.headline_fa()
        else:
            assert "قابل تصمیم می‌شود" not in opp.headline_fa()


# ── invariant 9: placeholders are not silently accepted as values ───────────
@pytest.mark.parametrize("junk", ["-", "نامشخص", "در حال بررسی", "N/A", "0"])
def test_placeholder_text_is_not_mistaken_for_a_real_value(junk):
    df = _mart()
    df.loc[df["CANONICAL_REG"] == "10000002", "مهلت قانونی رفع تعهد"] = junk
    profile = _reg_profile(df)
    assert profile.state_of("10000002", "مهلت قانونی رفع تعهد") != C.OK


def test_top_offending_values_are_reported_for_a_quick_diagnosis():
    df = _mart()
    df["مهلت قانونی رفع تعهد"] = "نامشخص"
    profile = _reg_profile(df)
    field = [f for f in profile.fields if f.column == "مهلت قانونی رفع تعهد"][0]
    assert field.top_bad_values and field.top_bad_values[0][0] == "نامشخص"
    assert field.coverage_pct == 0.0


# ── invariant 10: the report survives degenerate input ──────────────────────
def test_empty_and_column_less_input_do_not_raise():
    for df in (pd.DataFrame(), pd.DataFrame({"irrelevant": [1, 2]})):
        report = assess(df, ref_date=REF)
        assert report.headline_fa()
        assert set(report.frames()) == {"decisions", "fields", "defects", "next_fixes", "owners"}


def test_unknown_defect_code_fails_loudly():
    with pytest.raises(KeyError):
        C.get("NOT_A_REAL_CODE")


def test_summary_is_json_safe_for_the_trend_line():
    import json
    json.dumps(assess(_mart(), ref_date=REF).summary(), ensure_ascii=False)

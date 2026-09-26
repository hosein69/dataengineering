# -*- coding: utf-8 -*-
"""Locks for GSI 29.15.0 — anomalies are asked about, never silently cleaned.

Each test pins one promise the feature makes to the business owner:

* nothing is removed or altered by detection;
* every anomaly carries hypotheses tested against the data, not guesses;
* the three archetypes the owner described are recognised — the recurring dip
  that is really a capture failure, the "broken" segment that is really new
  behaviour, and the number too good to be true that is really double counting;
* no value changes without a named person and a written reason;
* "we don't know" expires;
* an approval stays bound to exactly what was approved.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta

import pandas as pd
import pytest

from gsi.trust import anomaly as A
from gsi.trust import inquiry as Q
from gsi.trust import trend

TODAY = date(2026, 9, 26)


# ── fixtures ────────────────────────────────────────────────────────────────
def _invoices(n=20, *, slip_key=None, factor=1000.0, seed=1, currency="یورو"):
    random.seed(seed)
    rows = []
    for i in range(n):
        value = random.uniform(10_000, 50_000)
        if f"R{i}" == slip_key:
            value *= factor
        rows.append({"CANONICAL_REG": f"R{i}", "INVOICE_VALUE": value,
                     "CURRENCY": currency, "EXPERT_CLEARANCE": "کارشناس ترخیص الف",
                     "_SOURCE_FILE": "SATA.xlsx", "_SOURCE_ROW": str(i + 2)})
    return pd.DataFrame(rows)


def _find(anomalies, kind, key=None):
    return [a for a in anomalies if a.kind == kind and (key is None or a.key == key)]


# ═══════════════════════════════════════════════════════════════════════════
#  Detection never touches the data
# ═══════════════════════════════════════════════════════════════════════════
def test_detection_changes_nothing():
    df = _invoices(slip_key="R5")
    before = df.copy(deep=True)
    A.detect(df)
    A.observe(df)
    pd.testing.assert_frame_equal(df, before)


# ═══════════════════════════════════════════════════════════════════════════
#  Numeric outliers
# ═══════════════════════════════════════════════════════════════════════════
def test_unit_slip_is_recognised_with_a_bound_rescale_proposal():
    df = _invoices(slip_key="R5")
    hits = _find(A.detect(df), A.VALUE_OUTLIER, "R5")
    assert len(hits) == 1
    anomaly = hits[0]
    lead = anomaly.leading
    assert lead.code == A.SCALE_SLIP and lead.strength == A.STRONG
    repair = anomaly.repair
    assert repair["kind"] == A.RESCALE and repair["factor"] == 1000.0
    assert repair["key"] == "R5" and repair["column"] == "INVOICE_VALUE"
    assert 10_000 <= repair["new"] <= 50_000
    # "it is real" is always on the table, never assumed away
    assert any(h.code == A.GENUINE_EXTREME for h in anomaly.hypotheses)
    assert "SATA.xlsx" in anomaly.locator_fa
    assert anomaly.owner_name == "کارشناس ترخیص الف"


def test_unit_slip_on_a_large_but_normal_value_is_still_recognised():
    """Found by looking at the real render: the largest ordinary invoice,
    typed in thousands, lands at the *edge* of its peers once corrected —
    not in the middle — and a 10–90% band alone missed it."""
    values = [12_000 + i * (48_000 / 23) for i in range(24)]      # 12k … 60k evenly
    df = pd.DataFrame({"CANONICAL_REG": [f"R{i}" for i in range(24)],
                       "INVOICE_VALUE": values, "CURRENCY": "EUR"})
    df.loc[23, "INVOICE_VALUE"] = values[23] * 1000                # the top one slips
    hit = _find(A.detect(df), A.VALUE_OUTLIER, "R23")[0]
    assert hit.leading.code == A.SCALE_SLIP
    assert hit.repair["factor"] == 1000.0


def test_extreme_without_digit_shift_leads_with_genuine():
    # 10^1.5 ≈ 31.6×: far from its peers but not a clean digit shift
    df = _invoices(slip_key="R3", factor=31.6)
    hits = _find(A.detect(df), A.VALUE_OUTLIER, "R3")
    assert len(hits) == 1
    assert hits[0].leading.code == A.GENUINE_EXTREME
    # a decimal slip may still be offered as an alternative, but never as a
    # strong one and never ahead of "it is real"
    assert all(h.strength != A.STRONG for h in hits[0].hypotheses if h.repair)


def test_one_entity_one_question_even_across_many_rows():
    df = _invoices(slip_key="R5")
    df = pd.concat([df] + [df[df["CANONICAL_REG"] == "R5"]] * 6, ignore_index=True)
    assert len(_find(A.detect(df), A.VALUE_OUTLIER, "R5")) == 1


def test_small_peer_group_is_not_judged():
    df = _invoices(n=A.MIN_PEERS - 1, slip_key="R2")
    assert _find(A.detect(df), A.VALUE_OUTLIER) == []


def test_zero_is_never_an_outlier():
    # zero stock stops the line: it is information, not noise
    rows = [{"KEY_MATERIAL": f"M{i}", "STOCK_IKCO": 100 + i} for i in range(20)]
    rows.append({"KEY_MATERIAL": "MZ", "STOCK_IKCO": 0})
    assert _find(A.detect(pd.DataFrame(rows)), A.VALUE_OUTLIER, "MZ") == []


def test_wrong_currency_hypothesis():
    eur = _invoices(n=12, currency="یورو")
    irr = _invoices(n=12, seed=7, currency="ریال")
    irr["CANONICAL_REG"] = [f"I{i}" for i in range(12)]
    irr["INVOICE_VALUE"] = irr["INVOICE_VALUE"] * 50_000
    odd = eur.iloc[[0]].copy()
    odd["CANONICAL_REG"] = "ODD"
    odd["INVOICE_VALUE"] = float(irr["INVOICE_VALUE"].median())
    hits = _find(A.detect(pd.concat([eur, irr, odd], ignore_index=True)),
                 A.VALUE_OUTLIER, "ODD")
    assert hits and any(h.code == A.OTHER_GROUP for h in hits[0].hypotheses)


def test_computed_output_is_asked_about_but_never_repaired():
    rows = [{"CANONICAL_REG": f"R{i}", "مانده تعهد": 1000.0 + i * 37,
             "FX_NTSW_CURRENCY": "EUR"} for i in range(15)]
    rows[4]["مانده تعهد"] = 1_040_000.0
    hits = _find(A.detect(pd.DataFrame(rows)), A.VALUE_OUTLIER, "R4")
    assert len(hits) == 1
    assert hits[0].repair is None
    assert any(h.code == A.COMPUTED_INPUT for h in hits[0].hypotheses)
    with pytest.raises(Q.InquiryError):
        Q.make_decision(hits[0], Q.APPROVE, "در سورس به ریال وارد شده است", "علی", today=TODAY)


# ═══════════════════════════════════════════════════════════════════════════
#  Categories — the "broken" segment that is really new
# ═══════════════════════════════════════════════════════════════════════════
def test_spelling_variant_proposes_alias_to_the_common_form():
    rows = [{"CANONICAL_BL": f"B{i}", "ENTRY_BORDER": "بندر عباس"} for i in range(10)]
    rows += [{"CANONICAL_BL": "B98", "ENTRY_BORDER": "بندرعباس"},
             {"CANONICAL_BL": "B99", "ENTRY_BORDER": "بندر-عباس"}]
    hits = _find(A.detect(pd.DataFrame(rows)), A.CATEGORY_VARIANT)
    assert {a.key for a in hits} == {"بندرعباس", "بندر-عباس"}
    for a in hits:
        assert a.repair["kind"] == A.ALIAS and a.repair["canonical"] == "بندر عباس"
        assert a.leading.strength == A.STRONG


def test_new_value_against_history_is_a_question_not_an_error():
    history = [{"observations": {"categories": {"TRANSPORT_MODE": ["SEA", "AIR"]}}}] * 3
    rows = [{"CANONICAL_BL": f"B{i}", "TRANSPORT_MODE": "SEA"} for i in range(8)]
    rows += [{"CANONICAL_BL": f"R{i}", "TRANSPORT_MODE": "RAIL"} for i in range(3)]
    hits = _find(A.detect(pd.DataFrame(rows), history=history), A.NEW_CATEGORY)
    assert len(hits) == 1 and hits[0].key == "RAIL"
    assert any(h.code == A.NEW_SEGMENT for h in hits[0].hypotheses)


def test_wholesale_vocabulary_change_is_one_source_question():
    history = [{"observations": {"categories": {"PART_GROUP": ["G1", "G2", "G3"]}}}] * 3
    rows = [{"KEY_MATERIAL": f"M{i}", "PART_GROUP": f"گروه-{i:02d}"} for i in range(20)]
    hits = _find(A.detect(pd.DataFrame(rows), history=history), A.NEW_CATEGORY)
    assert len(hits) == 1
    assert hits[0].leading.code == A.VOCABULARY_SHIFT


# ═══════════════════════════════════════════════════════════════════════════
#  Against history — the recurring dip and the number too good
# ═══════════════════════════════════════════════════════════════════════════
def _hist(sources_seq, **extra):
    return [{"observations": {"sources": s, **extra}} for s in sources_seq]


def test_isolated_source_drop_points_at_capture_not_business():
    history = _hist([{"bls/main": 100, "ntsw/main": 200}] * 5)
    obs = {"sources": {"bls/main": 50, "ntsw/main": 201}}
    hits = _find(A.detect(pd.DataFrame(), history=history, observations=obs), A.VOLUME_DROP)
    assert len(hits) == 1 and hits[0].key == "bls/main"
    assert hits[0].leading.code == A.CAPTURE_GAP and hits[0].leading.strength == A.STRONG


def test_recurring_drop_is_named_as_recurring():
    seq = [100, 100, 100, 60, 100, 100, 100, 55, 100, 100]
    history = _hist([{"bls/main": v, "ntsw/main": 200} for v in seq])
    obs = {"sources": {"bls/main": 58, "ntsw/main": 200}}
    hit = _find(A.detect(pd.DataFrame(), history=history, observations=obs), A.VOLUME_DROP)[0]
    assert hit.leading.code == A.CAPTURE_GAP
    assert "بار دیگر" in hit.leading.evidence_fa


def test_broad_drop_keeps_real_decline_on_the_table():
    history = _hist([{"a/x": 100, "b/x": 100, "c/x": 100}] * 4)
    obs = {"sources": {"a/x": 50, "b/x": 50, "c/x": 50}}
    hits = _find(A.detect(pd.DataFrame(), history=history, observations=obs), A.VOLUME_DROP)
    assert len(hits) == 3
    for a in hits:
        real = [h for h in a.hypotheses if h.code == A.REAL_DECLINE][0]
        assert real.strength == A.MEDIUM


def test_no_history_no_history_based_questions():
    obs = {"sources": {"bls/main": 1}}
    assert A.detect(pd.DataFrame(), history=[], observations=obs) == []


def test_total_that_jumps_with_row_inflation_is_double_counting_first():
    past = {"fields": {"INVOICE_VALUE": {"totals": {"EUR": 1_000_000.0}}},
            "rows_per_entity": {"REG": 1.0}, "entities": {"REG": 100}}
    obs = {"fields": {"INVOICE_VALUE": {"totals": {"EUR": 2_000_000.0}}},
           "rows_per_entity": {"REG": 2.0}, "entities": {"REG": 100}}
    hits = _find(A.detect(pd.DataFrame(), history=[{"observations": past}] * 4,
                          observations=obs), A.TOO_GOOD)
    assert len(hits) == 1
    assert hits[0].leading.code == A.DOUBLE_COUNT and hits[0].leading.strength == A.STRONG


def test_coverage_jump_filled_with_one_value_is_placeholder_first():
    past = {"fields": {"INVOICE_DATE": {"coverage": 10.0, "top_share": 0.1}}}
    obs = {"fields": {"INVOICE_DATE": {"coverage": 95.0, "top_share": 0.8, "top": "1400/01/01"}}}
    hits = _find(A.detect(pd.DataFrame(), history=[{"observations": past}] * 3,
                          observations=obs), A.TOO_GOOD)
    assert len(hits) == 1
    assert hits[0].leading.code == A.PLACEHOLDER_FILL
    assert "1400/01/01" in hits[0].leading.evidence_fa


def test_observations_are_json_safe_and_carry_what_the_next_run_needs():
    from gsi.warehouse.store import dumps, loads
    df = _invoices(slip_key="R5")
    obs = A.observe(df, sources={"sata": {"main": df}})
    back = loads(dumps(obs))
    assert back["sources"] == {"sata/main": 20}
    assert back["entities"]["REG"] == 20
    assert "EUR" in back["fields"]["INVOICE_VALUE"]["totals"]


# ═══════════════════════════════════════════════════════════════════════════
#  Answers — one sentence, a name, and "unknown" expires
# ═══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def slip():
    return _find(A.detect(_invoices(slip_key="R5")), A.VALUE_OUTLIER, "R5")[0]


@pytest.mark.parametrize("note", ["", "  ", "ok", "باشه", "تأیید", "نمی‌دانم", "کوتاه"])
def test_an_answer_needs_a_real_sentence(slip, note):
    with pytest.raises(Q.InquiryError):
        Q.make_decision(slip, Q.EXPLAIN, note, "علی", today=TODAY)


def test_an_answer_needs_a_name(slip):
    with pytest.raises(Q.InquiryError):
        Q.make_decision(slip, Q.EXPLAIN, "سفارش یک‌باره خط جدید است", " ", today=TODAY)


def test_unknown_is_temporary(slip):
    d = Q.make_decision(slip, Q.DONT_KNOW, "باید با ساتا چک شود", "علی", today=TODAY)
    assert d.until == (TODAY + timedelta(days=Q.UNKNOWN_DEFAULT_DAYS)).isoformat()
    with pytest.raises(Q.InquiryError):
        Q.make_decision(slip, Q.DONT_KNOW, "باید با ساتا چک شود", "علی",
                        today=TODAY, days=Q.UNKNOWN_MAX_DAYS + 1)
    reg = Q.InquiryRegister([d])
    assert reg.status(slip.id, TODAY) == Q.UNKNOWN
    assert reg.status(slip.id, TODAY + timedelta(days=Q.UNKNOWN_DEFAULT_DAYS + 1)) == Q.OVERDUE


def test_standing_approval_only_for_spelling(slip):
    with pytest.raises(Q.InquiryError):
        Q.make_decision(slip, Q.APPROVE, "در سورس به یورو×۱۰۰۰ وارد شده", "علی",
                        today=TODAY, standing=True)


def test_latest_answer_wins_and_revoke_reopens(slip):
    reg = Q.InquiryRegister()
    reg.record(Q.make_decision(slip, Q.APPROVE, "در سورس به یورو×۱۰۰۰ وارد شده", "علی"),
               persist=False)
    assert reg.status(slip.id) == Q.REPAIR_APPROVED and len(reg.approved()) == 1
    reg.record(Q.make_decision(slip, Q.REVOKE, "مالک گفت عدد درست است", "مریم"), persist=False)
    assert reg.status(slip.id) == Q.OPEN and reg.approved() == []
    assert len(reg) == 2          # nothing is erased


def test_register_round_trips_through_the_warehouse_append_only(slip):
    reg = Q.InquiryRegister()
    reg.record(Q.make_decision(slip, Q.DONT_KNOW, "باید با ساتا چک شود", "علی", today=TODAY))
    reg.record(Q.make_decision(slip, Q.EXPLAIN, "سفارش یک‌باره خط جدید است", "علی"))
    loaded = Q.InquiryRegister.load()
    assert [d.action for d in loaded.decisions] == [Q.DONT_KNOW, Q.EXPLAIN]
    assert loaded.status(slip.id) == Q.EXPLAINED
    assert loaded.latest(slip.id).anomaly["headline_fa"] == slip.headline_fa


def test_inquiries_frame_puts_overdue_then_open_first(slip):
    other = _find(A.detect(_invoices(slip_key="R7", seed=3)), A.VALUE_OUTLIER, "R7")[0]
    reg = Q.InquiryRegister([Q.make_decision(slip, Q.DONT_KNOW, "باید با ساتا چک شود", "علی",
                                             today=TODAY - timedelta(days=40), days=5)])
    frame = Q.inquiries_frame([other, slip], reg, TODAY)
    assert list(frame["_status"]) == [Q.OVERDUE, Q.OPEN]
    assert json.loads(frame["_payload"].iloc[0])["id"] == slip.id
    summary = Q.summarize(frame)
    assert summary["needs_answer"] == 2


# ═══════════════════════════════════════════════════════════════════════════
#  Healing — only what was approved, only while it still fits
# ═══════════════════════════════════════════════════════════════════════════
def _approved(anomaly, **kw):
    return Q.make_decision(anomaly, Q.APPROVE, "در سورس به واحد اشتباه وارد شده", "علی", **kw)


def test_approved_rescale_is_applied_with_provenance(slip):
    df = _invoices(slip_key="R5")
    df = pd.concat([df, df[df["CANONICAL_REG"] == "R5"]], ignore_index=True)
    original = float(df.loc[df["CANONICAL_REG"] == "R5", "INVOICE_VALUE"].iloc[0])
    others_before = df.loc[df["CANONICAL_REG"] != "R5", "INVOICE_VALUE"].copy()
    out, applied, stale = Q.apply_repairs(df, [_approved(slip)])
    assert len(out) == len(df)                                   # no row removed
    r5 = out[out["CANONICAL_REG"] == "R5"]
    assert (r5["INVOICE_VALUE"] - original / 1000).abs().max() < 1e-6
    assert r5["HEALED_FIELDS"].str.contains("علی").all()
    pd.testing.assert_series_equal(out.loc[out["CANONICAL_REG"] != "R5", "INVOICE_VALUE"],
                                   others_before)
    assert (out.loc[out["CANONICAL_REG"] != "R5", "HEALED_FIELDS"] == "").all()
    assert applied[0]["ردیف"] == 2 and stale == []


def test_negative_approval_does_not_follow_the_value_to_another_case(slip):
    """The same number on a different case is a different fact."""
    df = _invoices(slip_key="R5")
    value = float(df.loc[df["CANONICAL_REG"] == "R5", "INVOICE_VALUE"].iloc[0])
    df.loc[df["CANONICAL_REG"] == "R5", "INVOICE_VALUE"] = 33_000.0   # fixed at source
    df.loc[df["CANONICAL_REG"] == "R9", "INVOICE_VALUE"] = value      # same number, other case
    out, applied, stale = Q.apply_repairs(df, [_approved(slip)])
    assert applied == [] and len(stale) == 1
    assert float(out.loc[out["CANONICAL_REG"] == "R9", "INVOICE_VALUE"].iloc[0]) == value


def test_repair_never_touches_keys(slip):
    # A forged spelling fix aimed at a key column: it *would* match (R5 exists),
    # so only the NEVER_HEAL guard stands between it and a silent re-join.
    forged = slip.as_dict()
    forged["hypotheses"][0]["repair"] = {
        "kind": A.ALIAS, "column": "CANONICAL_REG", "key_column": "CANONICAL_REG",
        "variant": "R5", "canonical": "R6", "keys": []}
    decision = Q.make_decision(forged, Q.APPROVE, "در سورس به واحد اشتباه وارد شده", "علی",
                               standing=True)
    df = _invoices(slip_key="R5")
    out, applied, stale = Q.apply_repairs(df.copy(), [decision])
    assert applied == [] and stale
    pd.testing.assert_series_equal(out["CANONICAL_REG"], df["CANONICAL_REG"])


def test_alias_case_scoped_vs_standing():
    rows = [{"CANONICAL_BL": f"B{i}", "ENTRY_BORDER": "بندر عباس"} for i in range(10)]
    rows.append({"CANONICAL_BL": "B98", "ENTRY_BORDER": "بندرعباس"})
    variant = _find(A.detect(pd.DataFrame(rows)), A.CATEGORY_VARIANT)[0]
    later = pd.DataFrame(rows + [{"CANONICAL_BL": "NEW1", "ENTRY_BORDER": "بندرعباس"}])

    scoped = Q.make_decision(variant, Q.APPROVE, "یک گمرک است با دو املا", "علی")
    out, _, _ = Q.apply_repairs(later.copy(), [scoped])
    assert out.loc[out["CANONICAL_BL"] == "B98", "ENTRY_BORDER"].item() == "بندر عباس"
    assert out.loc[out["CANONICAL_BL"] == "NEW1", "ENTRY_BORDER"].item() == "بندرعباس"

    standing = Q.make_decision(variant, Q.APPROVE, "یک گمرک است با دو املا", "علی",
                               standing=True)
    out, _, _ = Q.apply_repairs(later.copy(), [standing])
    assert (out["ENTRY_BORDER"] == "بندر عباس").all()


def test_nothing_approved_means_business_values_unchanged():
    df = _invoices(slip_key="R5")
    out, applied, stale = Q.apply_repairs(df.copy(), [])
    pd.testing.assert_frame_equal(out.drop(columns="HEALED_FIELDS"), df)
    assert (out["HEALED_FIELDS"] == "").all() and applied == [] and stale == []


# ═══════════════════════════════════════════════════════════════════════════
#  Stages and the round trip through a run
# ═══════════════════════════════════════════════════════════════════════════
def _ctx(**extras):
    from gsi.stages.base import PipelineContext
    return PipelineContext(rb=None, today=TODAY, extras=dict(extras))


def test_stage_21_runs_before_any_engine_and_applies_injected_decisions(slip):
    from gsi.stages import discover
    from gsi.stages.s21_heal import ApprovedHealingStage
    orders = {s.name: s.order for s in discover()}
    assert orders["derive"] < orders["approved_healing"] < min(
        o for n, o in orders.items() if n not in ("resolve", "derive", "approved_healing"))
    ctx = _ctx(inquiry_decisions=[_approved(slip).as_dict()])
    out = ApprovedHealingStage().run(_invoices(slip_key="R5"), ctx)
    assert len(ctx.extras["heal_applied"]) == 1
    assert out.loc[out["CANONICAL_REG"] == "R5", "HEALED_FIELDS"].str.len().gt(0).all()


def test_stage_96_publishes_questions_and_enriches_the_snapshot():
    from gsi.stages.s96_anomaly import AnomalyInquiryStage
    from gsi.warehouse.store import dumps
    ctx = _ctx(anomaly_history=[], inquiry_decisions=[], trust_summary={"grades": {}})
    df = _invoices(slip_key="R5")
    out = AnomalyInquiryStage().run(df, ctx)
    assert out is df
    frame = ctx.extras["anomaly_inquiries"]
    assert (frame["_status"] == Q.OPEN).all() and len(frame) >= 1
    ts = ctx.extras["trust_summary"]
    assert ts["observations"]["entities"]["REG"] == 20
    assert ts["anomalies"][0]["id"] == frame["شناسه"].iloc[0]
    dumps(ts)                                  # the snapshot must stay storable
    assert "حذف" in ctx.extras["anomaly_headline"]


def test_cli_list_and_decide_through_the_stored_snapshot(slip, capsys):
    from gsi.warehouse.store import Warehouse
    Warehouse().audit("trust_snapshot", {"grades": {}, "anomalies": [slip.as_dict()]})
    assert trend.load_payloads()[-1]["anomalies"][0]["id"] == slip.id
    assert Q.main(["list"]) == 0
    assert slip.id in capsys.readouterr().out
    assert Q.main(["decide", slip.id, "explain", "--note", "سفارش یک‌باره خط جدید است",
                   "--actor", "علی"]) == 0
    assert Q.InquiryRegister.load().status(slip.id) == Q.EXPLAINED
    assert Q.main(["decide", slip.id, "explain", "--note", "ok", "--actor", "علی"]) == 2

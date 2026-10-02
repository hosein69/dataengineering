# -*- coding: utf-8 -*-
"""دور ۱۰: تناقض فایل کارشناسان و گزارش (داده ساختگی؛ شکل ردیف‌ها از نمونه مالک، مقدارها ساختگی).

فایل کارشناسان برای هر سفارش × متریال چند ردیف محموله (پارت) دارد، هر کدام با Order Status،
Quantity In Part، بارنامه و روش حمل خودش. مقدار سفارش و ارزش PI مال قلم‌اند و روی هر پارت تکرار می‌شوند.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from test_expert_file_exact_35_columns_v29_15_12 import _file, _row  # noqa: E402

from gsi.adapters.moghavemat import PART_STATES, MoghavematAdapter  # noqa: E402
from gsi.resolve.canonical import CanonicalEntityResolver  # noqa: E402
from gsi.rulebook import get_rulebook  # noqa: E402
from gsi.stages.s10_resolve import ResolveStage  # noqa: E402
from gsi.stages.s20_derive import DERIVED  # noqa: E402


def _order(*parts, qo=900, piv=4500, cur="CNY"):
    rows = []
    for i, (part, qp, status, mode, bl) in enumerate(parts, 1):
        rows.append(_row(ROW=i, ORD="O1", MAT="M1", PR="P1", PRI="10", VPI="PI-1", QO=qo, PIV=piv, CUR=cur,
                         PART=part, QP=qp, OS=status, MODE=mode, BL=bl))
    return _file(*rows)


def test_cleared_is_a_part_state_and_does_not_turn_the_order_unknown():
    assert any(code == "CLEARED" for code, _, _ in PART_STATES)
    rb = get_rulebook()
    for word in ("ترخیص کامل", "ترخیص شده", "ترخیص کامل "):
        assert rb.part_state(word) == "CLEARED", word
    inv = _order(("", 100, "ترخیص کامل", "هوایی", "AAAU1111111"),
                 ("", 300, "در راه", "دریایی", "BBBU2222222"))["inventory"].iloc[0]
    assert inv["MOGH_QTY_CLEARED_PART"] == 100 and inv["MOGH_QTY_IN_TRANSIT"] == 300
    assert inv["MOGH_QTY_STATE_UNKNOWN"] == 0 and inv["MOGH_QTY_AT_SUPPLIER"] == 0


def test_shipments_without_part_no_are_counted_by_their_own_bl():
    inv = _order(("", 100, "در راه", "دریایی", "AAAU1111111"),
                 ("", 200, "در راه", "دریایی", "BBBU2222222"),
                 ("", 50, "در راه", "دریایی", "BBBU 2222222"))["inventory"].iloc[0]
    # دو بارنامه: 100 + بیشینه(200، 50)؛ تکرار یک بارنامه با فاصله یک محموله است.
    assert inv["MOGH_QTY_IN_TRANSIT"] == 300


def test_air_waybill_is_accepted_and_masked_numbers_are_rejected():
    rb = get_rulebook()
    assert rb.validate_bl("999-1234 5678")[0]
    assert rb.validate_bl("99912345678")[0]
    ok, why = rb.validate_bl("ABC1234WXYZ......")
    assert not ok and "ناقص" in why
    lines = _order(("", 1, "در راه", "هوایی", "999-1234 5678"),
                   ("", 1, "در راه", "دریایی", "abc1234wxyz 5678"),
                   ("", 1, "در راه", "دریایی", "ABC1234WXYZ......"))["lines"]
    assert list(lines["MOGH_BL_NO"]) == ["99912345678", "ABC1234WXYZ5678", ""]
    assert lines["MOGH_BL_SUSPECT"].iloc[2] == "ABC1234WXYZ......"


def test_order_row_never_shows_one_shipment_as_the_whole_order():
    main = _order(("1", 100, "ترخیص کامل", "هوایی", "AAAU1111111"),
                  ("2", 300, "در راه", "دریایی", "BBBU2222222"))["main"].iloc[0]
    assert main["MOGH_BL_NO"] == "" and main["MOGH_ORDER_STATUS"] == "" and main["MOGH_TRANSPORT_MODE_CODE"] == ""
    assert main["MOGH_BL_COUNT"] == 2
    assert set(main["MOGH_BLS_ALL"].split("، ")) == {"AAAU1111111", "BBBU2222222"}
    assert set(main["MOGH_ORDER_STATUSES_ALL"].split("، ")) == {"ترخیص کامل", "در راه"}
    assert set(main["MOGH_TRANSPORT_MODES_ALL"].split("، ")) == {"AIR", "SEA"}
    # یک پارت ترخیص کامل از چهار پارت یعنی ترخیص جزئی سفارش، نه کامل.
    assert main["MOGH_CLEARANCE_HINT"] in ("", "PARTIAL")
    single = _order(("1", 100, "در راه", "دریایی", "AAAU1111111"),
                    ("2", 300, "در راه", "دریایی", "AAAU1111111"))["main"].iloc[0]
    assert single["MOGH_BL_NO"] == "AAAU1111111" and single["MOGH_ORDER_STATUS"] == "در راه"


def test_order_clearance_hint_is_full_only_when_every_row_is_full():
    h = MoghavematAdapter._order_clearance_hint
    assert h(pd.Series(["FULL", "FULL"])) == "FULL"
    assert h(pd.Series(["FULL", ""])) == "PARTIAL"
    assert h(pd.Series(["PARTIAL", "FULL"])) == "PARTIAL"
    assert h(pd.Series(["", ""])) == ""


def test_item_values_repeated_on_every_part_are_counted_once():
    main = _order(("1", 100, "در راه", "دریایی", "AAAU1111111"),
                  ("2", 200, "در راه", "دریایی", "BBBU2222222"),
                  ("3", 300, "در راه", "دریایی", "CCCU3333333"))["main"].iloc[0]
    assert main["MOGH_ORDER_QTY_SUM"] == 900       # نه 2700
    assert main["MOGH_PI_VALUE_SUM"] == 4500       # نه 13500
    assert main["MOGH_PART_QTY_SUM"] == 600


def test_repeated_item_value_that_disagrees_is_unknown_not_summed():
    rows = [_row(ROW=1, ORD="O1", MAT="M1", PR="P1", PRI="10", QO=900, PIV=4500, CUR="CNY", PART="1", QP=1,
                 OS="در راه", BL="AAAU1111111"),
            _row(ROW=2, ORD="O1", MAT="M1", PR="P1", PRI="10", QO=800, PIV=4500, CUR="CNY", PART="2", QP=1,
                 OS="در راه", BL="BBBU2222222")]
    main = _file(*rows)["main"].iloc[0]
    assert pd.isna(main["MOGH_ORDER_QTY_SUM"]) and main["MOGH_PI_VALUE_SUM"] == 4500


def test_distinct_items_of_one_order_are_still_added():
    rows = [_row(ROW=1, ORD="O1", MAT="M1", PR="P1", PRI="10", QO=900, PIV=100, CUR="CNY", QP=1, OS="در راه"),
            _row(ROW=2, ORD="O1", MAT="M2", PR="P1", PRI="20", QO=50, PIV=30, CUR="CNY", QP=1, OS="در راه")]
    main = _file(*rows)["main"]
    assert set(main["MOGH_ORDER_QTY_SUM"]) == {950} and set(main["MOGH_PI_VALUE_SUM"]) == {130}


def test_canonical_bl_keeps_each_rows_own_bl():
    df = pd.DataFrame({"KEY_BL": ["AAAU1111111", "BBBU2222222", ""],
                       "MOGH_BL_NO": ["CCCU3333333", "CCCU3333333", "CCCU3333333"],
                       "KEY_ORDER": ["O1", "O1", "O1"]})
    label, is_key, cands = ResolveStage.MAP["CANONICAL_BL"]
    out = CanonicalEntityResolver().resolve(df, label, cands, is_key=is_key,
                                      keep_order="CANONICAL_BL" in ResolveStage.ROW_OWNED)
    assert list(out) == ["AAAU1111111", "BBBU2222222", "CCCU3333333"]


def test_transport_mode_prefers_the_rows_own_bl_trip():
    assert DERIVED["TRANSPORT_MODE"][0][0] == "BL_TRIP_MODE_CODE"
    assert DERIVED["TRANSPORT_MODE"][0][-1] == "MOGH_TRANSPORT_MODE_CODE"
    assert DERIVED["EXPERT_CLEARED_PART_QTY"][0] == ["MOGH_QTY_CLEARED_PART"]


def test_short_number_is_a_bl_only_for_air_or_land_rows():
    rb = get_rulebook()
    assert rb.validate_bl("4321-8765", "AIR")[0] and rb.validate_bl("4321-8765", "ROAD")[0]
    assert not rb.validate_bl("4321-8765", "SEA")[0] and not rb.validate_bl("4321-8765")[0]
    assert not rb.validate_bl("ABC1234WXYZ......", "AIR")[0]
    lines = _file(_row(ROW=1, ORD="O1", MAT="M1", QP=1, OS="در راه", MODE="هوایی", BL="4321-8765"),
                  _row(ROW=2, ORD="O1", MAT="M1", QP=1, OS="در راه", MODE="زمینی", BL="765432"),
                  _row(ROW=3, ORD="O1", MAT="M1", QP=1, OS="در راه", MODE="", BL="765431"),
                  _row(ROW=4, ORD="O1", MAT="M1", QP=1, OS="در راه", MODE="هوایی", BL="998877", MFR="998877"))["lines"]
    assert list(lines["MOGH_BL_NO"]) == ["43218765", "765432", "", ""]
    assert list(lines["MOGH_BL_SUSPECT"])[2:] == ["765431", "998877"]

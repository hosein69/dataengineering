import pandas as pd

from app import process_cockpit as pc


def test_critical_materials_unique_and_sorted():
    df = pd.DataFrame({
        "KEY_MATERIAL": ["A", "A", "B", "C", ""],
        "مقاومت (روز)": [4.0, 3.0, 10.0, None, 1.0],
    })
    out = pc._critical_materials(df, 10)
    assert out["KEY_MATERIAL"].tolist() == ["A", "B"]
    assert out["مقاومت (روز)"].tolist() == [3.0, 10.0]


def test_stage_counts_use_latest_real_event():
    ev = pd.DataFrame({
        "_CASE_KEY": ["1", "1", "2", "2"],
        "LIFECYCLE_STAGE": ["PR", "ALLOCATION", "PO", "CUSTOMS"],
        "EVENTTIME": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-03"],
        "_SORTING": [1, 2, 1, 2],
    })
    out = pc._current_stage_counts({"eventlog": ev})
    assert int(out["ALLOCATION"]) == 1
    assert int(out["CUSTOMS"]) == 1
    assert "PR" not in out.index


def test_owner_and_quality_unknown_not_zero():
    df = pd.DataFrame({
        "PART_OWNER": ["x", ""],
        "KEY_MATERIAL": ["M1", ""],
        "DAILY_NEED": [10, None],
        "مقاومت (روز)": [2.0, None],
    })
    owner, _ = pc._owner_coverage(df)
    quality, _ = pc._quality_coverage(df)
    assert owner == "50%"
    assert quality == "50%"


def test_action_board_priority_order():
    a = pd.DataFrame({
        "PRIORITY": ["LOW", "CRITICAL", "HIGH"],
        "TITLE": ["l", "c", "h"],
        "DAYS_REMAINING": [10, -1, 1],
        "KEY_REG": ["1", "2", "3"],
    })
    out = pc._action_board({"case_actions": a})
    assert out.iloc[0]["PRIORITY"] == "CRITICAL"

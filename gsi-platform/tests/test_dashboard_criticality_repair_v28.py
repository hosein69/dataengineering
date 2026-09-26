import pandas as pd

from gsi.studio_core.runtime_data import ensure_criticality_columns
from app.ui_kit import band_count
from app.process_cockpit import _band_count


def _frame():
    return pd.DataFrame({
        'KEY_MATERIAL': ['A','B','C','D','E'],
        'STOCK_IKCO': [0, 20, 60, 200, None],
        'STOCK_SAPCO': [0, 30, 90, 300, None],
        'DAILY_NEED': [10, 10, 10, 10, 10],
        'مقاومت (روز)': [0, 5, 15, 50, None],
        'کد طبقه بحرانی': ['UNKNOWN']*5,
        'بحرانی (کوتاه)': ['نامشخص']*5,
        'طبقه بحرانی': ['❓ نامشخص (داده ناقص)']*5,
    })


def test_unknown_bands_are_repaired_from_official_resistance():
    out = ensure_criticality_columns(_frame())
    assert out.loc[0, 'کد طبقه بحرانی'] == 'STOCKOUT'
    assert out.loc[1, 'کد طبقه بحرانی'] == 'CRITICAL'
    assert out.loc[2, 'کد طبقه بحرانی'] == 'BECOMING_CRITICAL'
    assert out.loc[3, 'کد طبقه بحرانی'] == 'SAFE'
    assert out.loc[4, 'کد طبقه بحرانی'] == 'UNKNOWN'
    assert out.loc[1, 'بحرانی (کوتاه)'] == 'بحرانی'


def test_existing_valid_band_is_not_overwritten():
    df = _frame().iloc[[1]].copy()
    df['کد طبقه بحرانی'] = 'WATCH'
    df['بحرانی (کوتاه)'] = 'تحت نظر'
    out = ensure_criticality_columns(df)
    assert out.iloc[0]['کد طبقه بحرانی'] == 'WATCH'
    assert out.iloc[0]['بحرانی (کوتاه)'] == 'تحت نظر'


def test_dashboard_and_cockpit_counts_follow_repaired_band():
    out = ensure_criticality_columns(_frame())
    assert band_count(out, 'STOCKOUT') == 1
    assert band_count(out, 'CRITICAL') == 1
    assert band_count(out, 'BECOMING_CRITICAL') == 1
    assert _band_count(out, 'CRITICAL') == 1
    assert _band_count(out, 'BECOMING_CRITICAL') == 1

from gsi.factsheet import VERSION
import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html


def test_html_exposes_build_and_material_filter_in_every_tab():
    df = pd.DataFrame({
        'KEY_MATERIAL': [f'MAT-{i:03d}' for i in range(50)],
        'CANONICAL_ORDER': [f'ORD-{i:03d}' for i in range(50)],
        'ORG_DEPT': ['D'] * 50,
    })
    tabs = [
        {'id':'a','title':'A','fields':['CANONICAL_ORDER'], 'blocks':['table']},
        {'id':'b','title':'B','fields':['ORG_DEPT'], 'blocks':['table']},
    ]
    out = build_dynamic_html(df, '2026-09-21', tabs=tabs, selected_fields=['CANONICAL_ORDER'])
    assert f'Build {VERSION}' in out
    # Material must be injected into both tab schemas, not rendered as a global supply table.
    assert out.count('KEY_MATERIAL') >= 2
    assert out.count('data-filter-mode="contains"') >= 2
    # Since 29.6.8 the engine owns one dedicated material tab.
    assert out.count('دید تأمین — متریال محور</button>') == 1

import re
import pandas as pd

from gsi.studio_core.html_export import build_dynamic_html


def test_material_is_in_each_tab_and_each_tab_owns_filter():
    df = pd.DataFrame({
        'KEY_MATERIAL': [f'MAT-{i:03d}' for i in range(50)],
        'CANONICAL_ORDER': [f'PO-{i:03d}' for i in range(50)],
        'KEY_REG': [f'REG-{i%3}' for i in range(50)],
        'ORG_DEPT': ['A' if i % 2 else 'B' for i in range(50)],
    })
    tabs = [
        {'id':'legacy_a','title':'A','fields':['CANONICAL_ORDER'], 'blocks':['table']},
        {'id':'legacy_b','title':'B','fields':['KEY_REG','ORG_DEPT'], 'blocks':['table']},
    ]
    out = build_dynamic_html(df, '2026-09-21', tabs=tabs, selected_fields=['CANONICAL_ORDER'])

    # Material must be a table column inside both pane-owned tables.
    assert out.count('<th scope="col">KEY_MATERIAL</th>') == 2

    # 50 materials => high-cardinality text filter, once for each pane.
    filters = re.findall(r'<input[^>]+data-f="KEY_MATERIAL"[^>]+data-pane="([^"]+)"', out)
    assert len(filters) == 2
    assert len(set(filters)) == 2
    assert all(x.startswith('pane_') for x in filters)

    # Regression guard: no legacy global material/supply table outside panes.
    assert 'material-supply-view' not in out
    assert out.count('دید تأمین — متریال محور</button>') == 1


def test_authoritative_version_bumped():
    from gsi.factsheet import VERSION
    assert tuple(map(int, VERSION.split('.'))) >= (29, 6, 3)

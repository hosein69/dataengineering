from gsi.factsheet import VERSION
import pandas as pd
from gsi.studio_core.report_builder import ReportSpec, build


def test_html_contains_one_filterable_material_supply_tab(tmp_path):
    df = pd.DataFrame([
        {
            'KEY_MATERIAL':'MAT-001','CANONICAL_ORDER':'O1','CANONICAL_BL':'B1','KEY_REG':'R1',
            'CANONICAL_EXPERT':'Expert A','ORG_DEPT':'Dept A','STAGE_FA':'حمل',
            'بحرانی (کوتاه)':'بحرانی','مقاومت (روز)':4,
        },
        {
            'KEY_MATERIAL':'MAT-002','CANONICAL_ORDER':'O2','CANONICAL_BL':'B2','KEY_REG':'R2',
            'CANONICAL_EXPERT':'Expert B','ORG_DEPT':'Dept B','STAGE_FA':'گمرک',
            'بحرانی (کوتاه)':'عادی','مقاومت (روز)':12,
        },
    ])
    spec = ReportSpec(
        fields=['CANONICAL_ORDER'], ref_date='2026-09-21', formats=['html'],
        tabs=[{'id':'main','title':'نمای اصلی','fields':['CANONICAL_ORDER'],'blocks':['table']}],
        file_stem='material-test'
    )
    res = build(df, {}, spec, {}, tmp_path)
    h = res.html
    # Exact supply view is a dedicated tab, not a global/floating duplicate.
    assert h.count('دید تأمین — متریال محور</button>') == 1
    assert 'data_source": "material_supply"' in h
    assert 'const MATERIAL_SUPPLY_DATA=' in h
    # Material-specific filter belongs to that pane.
    assert 'data-pane="pane_supply_material"' in h
    assert 'placeholder="جستجو در متریال"' in h
    # Same business records are carried in the independent material view payload.
    assert 'MAT-001' in h and 'MAT-002' in h
    # Build marker proves runtime package.
    assert f'Build {VERSION}' in h

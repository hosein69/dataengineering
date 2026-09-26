import json
import pandas as pd
from pandas.testing import assert_frame_equal
from gsi.report.supply_views import build_material_html_view
from gsi.studio_core.html_export import build_dynamic_html
from gsi.studio_core.report_builder import ReportSpec, build
from gsi.stages.s20_derive import DERIVED, DeriveStage


def frame():
    raw = pd.DataFrame([{
        'KEY_MATERIAL': 'M-001', 'ORC_PART_NO': 'M-001',
        'ORC_MATERIAL_DESC': 'قطعه مرجع', 'MOGH_MATERIAL': 'M-001',
        'MOGH_MATERIAL_DESC': 'شرح کارشناسی', 'MOGH_PO_SENT_DATE': '2026-01-01',
        'MOGH_COMMERCIAL_NOTE': 'کامنت یک', 'MOGH_STAGE_FA': 'خرید',
        'NTSW_ALLOC_DATE': '2026-02-01', 'NTSW_BALANCE': 150,
        'NTSW_RELEASE_STATUS': 'رفع تعهد نشده', 'BL_BL_DATE': '2026-03-01',
        'CANONICAL_ORDER': '123456', 'CANONICAL_BL': 'BL123456',
        'KEY_REG': '12345678', 'روایت': 'روایت آلوده',
        'BL_CRITICAL_REASON': 'علت آلوده',
    }])
    # Real alias definitions, including MOGH_PO_SENT_DATE -> PO_SENT_DATE.
    derived = {target: DeriveStage._first_nonempty(raw, candidates, default)
               for target, (candidates, default, numeric) in DERIVED.items()}
    return pd.concat([raw.drop(columns=list(derived), errors="ignore"), pd.DataFrame(derived)], axis=1)


def payload(h):
    return json.JSONDecoder().raw_decode(h.split('const MATERIAL_SUPPLY_DATA=',1)[1])[0]


def test_real_aliases_and_material_link_do_not_control_position():
    v=build_material_html_view(frame())
    assert len(v)==1
    r=v.iloc[0]
    for c in ['موقعیت فعلی','مرحله فعلی','معطل حوزه','فعالیت بعدی مورد انتظار']:
        assert r[c]=='نامشخص'
    assert r['شرح متریال']=='قطعه مرجع'
    assert r['تعداد سفارش یکتای گروه']==0
    assert r['تعداد بارنامه یکتای گروه']==0
    assert '123456' in r['کامنت کارشناسان']
    assert 'کامنت یک' in r['کامنت کارشناسان']
    assert 'مانده تعهد' in r['هشدار NTSW']
    assert 'علت آلوده' not in r['چرایی / مبنای وضعیت']


def test_advisory_fanout_and_mutation_leave_operational_values_identical():
    x=frame(); original=x.copy(deep=True)
    y=pd.concat([x,x],ignore_index=True)
    y.loc[1,'MOGH_COMMERCIAL_NOTE']='کامنت دو'
    y.loc[1,'NTSW_ALLOC_DATE']='2026-08-01'
    y.loc[1,'NTSW_BALANCE']=9999
    y.loc[1,'MOGH_MATERIAL']='OTHER'
    a=build_material_html_view(x); b=build_material_html_view(y)
    cols=[c for c in a if not c.startswith(('هشدار','کامنت'))]
    assert_frame_equal(a[cols],b[cols])
    assert 'کامنت دو' in b.iloc[0]['کامنت کارشناسان']
    assert_frame_equal(x,original)


def test_excluded_dates_never_assign_next_activity_or_missing_date():
    x=pd.DataFrame([{'KEY_MATERIAL':'A','BL_DATE':'2026-01-01',
                     'NTSW_ALLOC_DATE':'2026-02-01','NTSW_COMMIT_DATE':''}])
    v=build_material_html_view(x).iloc[0]
    assert v['موقعیت فعلی']=='حمل'
    assert 'تخصیص' not in v['داده مفقود برای تعیین وضعیت']
    assert 'تعهد' not in v['داده مفقود برای تعیین وضعیت']


def test_old_precomputed_view_cannot_bypass_boundary():
    x=frame(); original=x.copy(deep=True)
    h=build_dynamic_html(x,'2026-09-21',material_supply_view=pd.DataFrame([{'موقعیت فعلی':'BYPASS'}]))
    assert payload(h)[0]['موقعیت فعلی']=='نامشخص'
    assert 'BYPASS' not in json.dumps(payload(h))
    assert_frame_equal(x,original)


def test_missing_material_and_duplicate_index_preserve_comment_alignment():
    x=pd.DataFrame([{'KEY_MATERIAL':'Z','MOGH_COMMERCIAL_NOTE':'zed'},
                    {'KEY_MATERIAL':'','MOGH_COMMERCIAL_NOTE':'orphan'},
                    {'KEY_MATERIAL':'A','MOGH_COMMERCIAL_NOTE':'alpha'}],index=[7,7,7])
    v=build_material_html_view(x).set_index('متریال')
    assert 'alpha' in v.loc['A','کامنت کارشناسان']
    assert 'zed' in v.loc['Z','کامنت کارشناسان']


def test_expert_only_identity_is_not_operational_material():
    x=frame();x['ORC_PART_NO']=''
    assert build_material_html_view(x).empty


def test_composer_financial_data_is_preserved(tmp_path):
    x=frame()
    spec=ReportSpec(ref_date='2026-09-21',formats=['html'],fields=['NTSW_BALANCE'],
        tabs=[{'id':'financial','title':'Financial / FX','fields':['NTSW_BALANCE'],'blocks':['table']}])
    h=build(x,{},spec,{},tmp_path).html
    assert payload(h)[0]['موقعیت فعلی']=='نامشخص'
    # The financial table keeps its authorized original amount.
    assert 'NTSW_BALANCE' in h and '150' in h

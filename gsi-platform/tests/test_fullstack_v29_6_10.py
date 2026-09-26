from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
from gsi.studio_core.report_builder import _filtered_process_extras, ReportSpec, build
from gsi.studio_core.access_control import AccessScope, apply_row_scope
from gsi.report.supply_views import build_material_html_view


def test_empty_scope_never_leaks_process_or_fx():
    extras={'eventlog':pd.DataFrame({'_CASE_KEY':['secret'],'ACTIVITY_FA':['hidden']}),
            'case_actions':pd.DataFrame({'KEY_REG':['R1'],'TITLE':['hidden']}),
            'fx_control_summary':pd.DataFrame({'amount':[1000]}),
            'stage_queue':pd.DataFrame({'مرحله جاری':['hidden']})}
    result=_filtered_process_extras(extras,pd.DataFrame(columns=['CASE_KEY','KEY_REG']))
    assert all(v.empty for v in result.values())


def test_scope_keys_do_not_match_other_identity_types():
    selected=pd.DataFrame({'CASE_KEY':['C1'],'KEY_REG':['R1']})
    extras={'case_actions':pd.DataFrame({'CASE_KEY':['C2'],'KEY_REG':['C1'],'TITLE':['hidden']})}
    assert _filtered_process_extras(extras,selected)['case_actions'].empty


def test_missing_department_column_does_not_expand_scope():
    df=pd.DataFrame({'KEY_MATERIAL':['M1']})
    assert apply_row_scope(df,AccessScope(departments=['D1'])).empty


def test_column_scope_blocks_material_and_hidden_fields(tmp_path):
    df=pd.DataFrame({'KEY_MATERIAL':['secret-material'],'NTSW_BALANCE':[20],
                     'ORG_DEPT':['hidden-dept'],'EMAIL':['private@example.invalid']})
    spec=ReportSpec(ref_date='2026-09-21',formats=['html'],allowed_fields=['NTSW_BALANCE'],
        fields=['NTSW_BALANCE'], tabs=[{'title':'Requested','fields':['EMAIL','ORG_DEPT','NTSW_BALANCE'],'blocks':['table']}])
    html=build(df,{},spec,out_dir=tmp_path).html
    assert 'secret-material' not in html
    assert 'private@example.invalid' not in html
    assert 'hidden-dept' not in html
    assert '"material_supply_embedded_rows": 0' in html


def test_oracle_resistance_survives_advisory_boundary():
    df=pd.DataFrame({'KEY_MATERIAL':['M1'],'ORC_PART_NO':['M1'],'MOGH_MATERIAL':['M1'],
        'ORC_STOCK_IKCO':[60],'ORC_STOCK_SAPCO':[40],'ORC_DAILY_NEED':[20],
        'MOGH_SUPPLIER_STOCK_QTY':[100000],'مقاومت (روز)':[999]})
    view=build_material_html_view(df)
    assert view.iloc[0]['مقاومت (روز)']==5
    assert view.iloc[0]['بحرانی']=='بحرانی'


def test_real_dashboard_runs_through_html_download(tmp_path):
    """The dashboard renders from the published snapshot, not from a fresh run.

    This test used to patch ``Pipeline.run`` and expect the page to build. The
    29.8.2 runtime contract is ``ui_default_mode: published_snapshot_only`` /
    ``refresh_mode: explicit_only``: with no published snapshot the page now
    stops with an instruction instead of starting an ETL, so patching the
    pipeline no longer drives it. Drive the snapshot path the page actually
    takes.
    """
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    df=pd.DataFrame({'KEY_MATERIAL':['M1'],'CANONICAL_ORDER':['O1'],'CANONICAL_BL':['B1'],
                     'KEY_REG':['R1'],'ORG_DEPT':['D1'],'NTSW_BALANCE':[5],
                     'مقاومت (روز)':[5.0],'بحرانی (کوتاه)':['بحرانی'],'کد طبقه بحرانی':['CRITICAL']})
    excel=tmp_path/'official.xlsx';df.to_excel(excel,index=False)
    st.cache_data.clear()
    with patch('gsi.warehouse.service.last_report',
               return_value=(df, df, {'warehouse_run_id':'run-test'}, str(excel))):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/dashboard.py')).run(timeout=60)
    assert not app.exception, [e.message for e in app.exception]
    assert any('HTML' in b.label for b in app.get('download_button'))
    st.cache_data.clear()


def test_dashboard_refuses_to_start_an_etl_when_nothing_is_published(tmp_path):
    """The other half of the same contract: no snapshot means stop, not rebuild."""
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    st.cache_data.clear()
    with patch('gsi.warehouse.service.last_report', return_value=None), \
         patch('gsi.pipeline.Pipeline.run', side_effect=AssertionError('ETL must not run on page load')):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/dashboard.py')).run(timeout=60)
    assert not app.exception, [e.message for e in app.exception]
    assert any('Snapshot' in str(e.value) for e in app.get('error'))
    st.cache_data.clear()


def test_financial_card_deduplicates_and_never_adds_currencies():
    from gsi.report.financial_summary import commitment_display
    df=pd.DataFrame({'KEY_REG':['R1','R1','R2'], 'NTSW_CURRENCY':['EUR','EUR','USD'], 'NTSW_BALANCE':[10,10,20]})
    assert commitment_display(df)=='10.00 EUR | 20.00 USD'
    df.loc[1,'NTSW_BALANCE']=11
    assert 'مغایرت' in commitment_display(df)


def test_historical_material_status_uses_report_date():
    df=pd.DataFrame({'KEY_MATERIAL':['M1'],'SHIPPED_EVIDENCE_DATE':['2026-06-01']})
    assert build_material_html_view(df,today='2026-05-01').iloc[0]['موقعیت فعلی']=='نامشخص'
    assert build_material_html_view(df,today='2026-06-06').iloc[0]['سن وضعیت (روز)']==5


def test_studio_starts_with_published_snapshot(tmp_path):
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    df=pd.DataFrame({'KEY_MATERIAL':['M1'],'CANONICAL_ORDER':['O1'],'CANONICAL_BL':['B1'],
                    'KEY_REG':['R1'],'ORG_DEPT':['D1'],'مقاومت (روز)':[5.0]})
    excel=tmp_path/'official.xlsx';df.to_excel(excel,index=False)
    st.cache_data.clear()
    with patch('gsi.warehouse.service.last_report',return_value=(df,df,{},str(excel))):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/studio.py')).run(timeout=40)
    assert not app.exception, [e.message for e in app.exception]
    st.cache_data.clear()

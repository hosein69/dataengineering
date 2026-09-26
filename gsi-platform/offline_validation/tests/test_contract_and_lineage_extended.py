from __future__ import annotations
import pandas as pd
import pytest
from gsi.adapters.a60_finance import CreditAdapter,SapAdapter

@pytest.mark.parametrize('field,value',[('_SOURCE_ROW',17),('_SOURCE_FILE_ID','sha256:abc'),('_SOURCE_SHEET','PURCREDIT')])
def test_credit_lineage_roundtrip(field,value):
    raw={'شماره ثبت سفارش':'12345678','_SOURCE_ROW':17,'_SOURCE_FILE_ID':'sha256:abc','_SOURCE_SHEET':'PURCREDIT'}
    out=CreditAdapter().transform({'PURCREDIT':pd.DataFrame([raw])})['main']
    assert field in out.columns and out[field].iloc[0]==value

@pytest.mark.parametrize('native,foreign',[
    ('Material','SAP_MATERIAL'),('Currency','SAP_PR_CURRENCY')
])
def test_pr_native_fields_remain_on_pr_semantics(native,foreign):
    raw={'Purchase Requisition':'1234567890','Item of requisition':'10','Material':'M1','Currency':'EUR'}
    row=SapAdapter().transform({'pr':pd.DataFrame([raw])})['pr_items'].iloc[0]
    if native=='Material': assert row['SAP_MATERIAL']=='M1'
    if native=='Currency' and foreign in row.index: assert row[foreign]=='EUR'

@pytest.mark.parametrize('field',['SAP_PO_MATERIAL','SAP_PACK_MATERIAL','SAP_PO_CURRENCY'])
def test_pr_does_not_fill_foreign_sheet_authority(field):
    raw={'Purchase Requisition':'1234567890','Item of requisition':'10','Material':'M1','Currency':'EUR'}
    row=SapAdapter().transform({'pr':pd.DataFrame([raw])})['pr_items'].iloc[0]
    assert pd.isna(row[field]) or row[field]==''

@pytest.mark.parametrize('header,event_col',[
    ('نوع ارز5','CRD_ALLOC_CURRENCY'),('نوع ارز6','CRD_SWIFT_CURRENCY')
])
def test_event_specific_currency_does_not_become_lc_currency(header,event_col):
    row=CreditAdapter().transform({'PURCREDIT':pd.DataFrame([{header:'USD'}])})['main'].iloc[0]
    assert row[event_col]=='USD'
    assert row['CRD_CURRENCY']==''

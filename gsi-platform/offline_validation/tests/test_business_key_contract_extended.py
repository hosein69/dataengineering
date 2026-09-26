from __future__ import annotations
import pandas as pd
import pytest
from gsi.adapters.a60_finance import CreditAdapter
from gsi.adapters.a50_ntsw import NtswAdapter
from gsi.config.keys import KeyRegistry

@pytest.mark.parametrize('header',[
    'کد ثبت سفارش','شماره ثبت سفارش','ثبت سفارش',' شماره ثبت سفارش ',
    'شماره_ثبت_سفارش','شماره\nثبت سفارش'
])
def test_reg_aliases_are_one_identity(header):
    raw=pd.DataFrame([{header:'12345678'}]); out=pd.DataFrame(index=raw.index)
    CreditAdapter().add_reg_key(out,raw)
    assert out.KEY_REG.tolist()==['12345678']

@pytest.mark.parametrize('header',[
    'شماره پرونده ثبت سفارش','شماره پرونده','تاریخ ثبت سفارش','ارزش ثبت سفارش',
    'مبلغ کارمزد ثبت سفارش (ریال)','حالت ثبت سفارش','وضعیت ثبت سفارش'
])
def test_reg_semantic_near_misses_are_not_reg_identity(header):
    raw=pd.DataFrame([{header:'12345678'}]); out=pd.DataFrame(index=raw.index)
    CreditAdapter().add_reg_key(out,raw)
    assert out.KEY_REG.eq('').all(), (header,out.to_dict('records'))

@pytest.mark.parametrize('header',['شماره سفارش','سفارش','Order No.','Our Reference'])
def test_order_aliases_are_one_commercial_identity(header):
    raw=pd.DataFrame([{header:'83329WA'}]); out=pd.DataFrame(index=raw.index)
    CreditAdapter().add_order_key(out,raw)
    assert out.KEY_ORDER.tolist()==['83329WA']

@pytest.mark.parametrize('header',[
    'Purchase Requisition','Order Unit','Net Order Value','Gross order value',
    'Purchase Order Item','Purchase Order Date','PO No','Material Document'
])
def test_order_semantic_near_misses_do_not_create_commercial_order(header):
    raw=pd.DataFrame([{header:'8300000001'}]); out=pd.DataFrame(index=raw.index)
    CreditAdapter().add_order_key(out,raw)
    assert out.KEY_ORDER.eq('').all(), (header,out.to_dict('records'))

@pytest.mark.parametrize('header',['Material Document','Material Description','Material Group','Order Material'])
def test_material_descriptors_do_not_create_material_identity(header):
    raw=pd.DataFrame([{header:'500000001'}]); out=pd.DataFrame(index=raw.index)
    CreditAdapter().add_material_key(out,raw)
    assert out.KEY_MATERIAL.eq('').all(), (header,out.to_dict('records'))

@pytest.mark.parametrize('bad',[None,'',float('nan'),pd.NA])
def test_all_composite_components_are_mandatory(bad):
    f=pd.DataFrame({'KEY_REG':['12345678'],'CURRENCY_CODE':[bad]})
    assert KeyRegistry().build(f,'REG_CURRENCY').KEY_REG_CURRENCY.eq('').all()

@pytest.mark.parametrize('bad',[None,'',float('nan'),pd.NA])
def test_order_bl_composite_never_serializes_missing_component(bad):
    f=pd.DataFrame({'KEY_BL':['BL0001'],'KEY_ORDER':[bad]})
    assert KeyRegistry().build(f,'BL_ORDER').KEY_BL_ORDER.eq('').all()

def test_ntsw_import_license_does_not_require_material():
    raw=pd.DataFrame([{'شماره پرونده':'7100000001','شماره ثبت سفارش':'12345678','وضعیت':'فعال'}])
    out=NtswAdapter().transform({'Import License':raw})['import_license']
    assert out.KEY_REG_FILE.iloc[0]=='7100000001'
    assert out.KEY_REG.iloc[0]=='12345678'
    assert 'KEY_MATERIAL' not in out.columns

def test_ntsw_reg_file_without_reg_stays_unresolved_not_fabricated():
    raw=pd.DataFrame([{'شماره پرونده':'7100000001','وضعیت':'در انتظار'}])
    out=NtswAdapter().transform({'Import License':raw})['import_license']
    assert out.KEY_REG_FILE.iloc[0]=='7100000001'
    assert out.KEY_REG.iloc[0]==''

def test_ntsw_order_absence_does_not_fabricate_order_from_registration():
    raw=pd.DataFrame([{'شماره پرونده':'7100000001','شماره ثبت سفارش':'12345678'}])
    out=NtswAdapter().transform({'Import License':raw})['import_license']
    assert out.KEY_ORDER.iloc[0]==''

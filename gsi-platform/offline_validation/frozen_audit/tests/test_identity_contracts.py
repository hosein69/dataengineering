"""User requirements 1–8, 21–23, 47. Semantic identity is never string similarity."""
import pandas as pd
import pytest
from gsi.adapters.a60_finance import CreditAdapter,FxTransactionAdapter,SapAdapter
from gsi.config.keys import KeyRegistry

@pytest.mark.parametrize('header',['شماره ثبت سفارش','شماره_ثبت_سفارش','شماره\nثبت سفارش',' شماره ثبت سفارش '])
def test_registration_textual_alias(header):
    """Permitted spelling changes preserve the same REG meaning and eight-digit value."""
    row=CreditAdapter().transform({'PURCREDIT':pd.DataFrame([{header:'12345678'}])})['main'].iloc[0]
    assert row.KEY_REG=='12345678'

@pytest.mark.parametrize('header',['شماره پرونده ثبت سفارش','تاریخ ثبت سفارش','شماره سفارش'])
def test_non_registration_header_cannot_supply_reg(header):
    """File identity, date and commercial order are not REG even when value looks like REG."""
    row=CreditAdapter().transform({'PURCREDIT':pd.DataFrame([{header:'12345678'}])})['main'].iloc[0]
    assert row.KEY_REG==''

@pytest.mark.parametrize('header',['نام تامین کننده','نام تامين کننده','نام_تامین_کننده'])
def test_persian_supplier_spelling(header):
    """Arabic/Persian letters and underscores are textual aliases only."""
    row=CreditAdapter().transform({'PURCREDIT':pd.DataFrame([{header:'Vendor7'}])})['main'].iloc[0]
    assert row.CRD_SUPPLIER=='Vendor7'

@pytest.mark.parametrize('header,method,key',[('po no','add_order_key','KEY_ORDER'),('Material Document','add_material_key','KEY_MATERIAL')])
def test_similar_header_cannot_create_business_identity(header,method,key):
    """Without source-specific authority PO cannot be ORDER and material document cannot be MATERIAL."""
    raw=pd.DataFrame([{header:'8300000001'}]);out=pd.DataFrame(index=raw.index)
    getattr(CreditAdapter(),method)(out,raw)
    assert out[key].eq('').all(),out.to_dict('records')

@pytest.mark.parametrize('header,expected',[('نوع ارز6','CRD_SWIFT_CURRENCY'),('نوع ارز5','CRD_ALLOC_CURRENCY')])
def test_event_currency_cannot_leak_into_lc_currency(header,expected):
    """SWIFT/allocation currencies must not fill absent native credit currency."""
    row=CreditAdapter().transform({'PURCREDIT':pd.DataFrame([{header:'USD'}])})['main'].iloc[0]
    assert row[expected]=='USD'
    assert row.CRD_CURRENCY==''

def test_rate_type_separation():
    """File conversion rate is not a source-reported FX purchase rate."""
    raw=pd.DataFrame([{'ثبت سفارش':'12345678','مبلغ خرید ارز':100,'نوع ارز':'USD','نرخ تبدیل ارز':99}])
    row=FxTransactionAdapter().transform({'Sheet1':raw})['main'].iloc[0]
    assert row.FX_CONVERSION_RATE==99 and pd.isna(row.FX_RATE)

@pytest.mark.parametrize('missing',['','none_column'])
def test_partial_composite_is_not_a_valid_identity(missing):
    """BL+ORDER is unknown if an entire component or its column is absent."""
    raw=pd.DataFrame({'KEY_BL':['BL000001']})
    if missing!='none_column':raw['KEY_ORDER']=''
    out=KeyRegistry().build(raw,'BL_ORDER')
    assert out.KEY_BL_ORDER.eq('').all(),out.to_dict('records')

def test_full_composite_does_not_merge_distinct_orders():
    """Same BL attached to two orders produces two distinct composite keys."""
    raw=pd.DataFrame({'KEY_BL':['BL000001']*2,'KEY_ORDER':['602164B','602165B']})
    assert KeyRegistry().build(raw,'BL_ORDER').KEY_BL_ORDER.tolist()==['BL000001|602164B','BL000001|602165B']

@pytest.mark.parametrize('missing',[None,'',float('nan')])
def test_reg_currency_requires_currency(missing):
    """REG alone cannot substitute for REG+currency grain."""
    f=pd.DataFrame({'KEY_REG':['12345678'],'CURRENCY_CODE':[missing]})
    assert KeyRegistry().build(f,'REG_CURRENCY').KEY_REG_CURRENCY.eq('').all()

@pytest.mark.parametrize('field',['_SOURCE_ROW','_SOURCE_FILE_ID','_SOURCE_SHEET'])
def test_credit_adapter_preserves_physical_lineage(field):
    """Physical source identity survives raw-to-canonical transformation."""
    raw=pd.DataFrame([{'شماره ثبت سفارش':'12345678','_SOURCE_ROW':7,'_SOURCE_FILE_ID':'fixture-sha','_SOURCE_SHEET':'PURCREDIT'}])
    out=CreditAdapter().transform({'PURCREDIT':raw})['main']
    assert field in out and out[field].iloc[0]==raw[field].iloc[0]

@pytest.mark.parametrize('field',['SAP_PO_MATERIAL','SAP_PACK_MATERIAL','SAP_PO_CURRENCY'])
def test_pr_does_not_manufacture_other_sheet_fields(field):
    """PR Material/Currency are not authority for absent PO/package-native fields."""
    row=SapAdapter().transform({'pr':pd.DataFrame([{'Purchase Requisition':'1234567890','Item of requisition':'10','Material':'M1','Currency':'EUR'}])})['pr_items'].iloc[0]
    assert row.SAP_MATERIAL=='M1'
    assert pd.isna(row[field]) or row[field]==''

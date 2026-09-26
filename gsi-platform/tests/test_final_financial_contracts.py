"""RC2 financial and identifier regression counterexamples."""
import pandas as pd
import pytest
from gsi.adapters.a50_ntsw import NtswAdapter
from gsi.adapters.a60_finance import IlAppendAdapter
from gsi.resolve.process_evidence import build_process_inventory
from gsi.cashflow.dwh import bundle_from_dwh, FinancialSourceUnavailable
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build

def publish(wh,sources):
    with wh.run({'reference_date':'2026-09-22'}) as rid:build(wh,sources,rid)
    wh.publish(rid);return rid

def test_swift_stage_visible_without_payment():
    from gsi.resolve.process_evidence import STAGES
    codes=[s[0] for s in STAGES]
    assert codes.index('FUNDING')<codes.index('SWIFT_SENT')<codes.index('PAYMENT')
    obs,cases,matrix=build_process_inventory({'credit':{'main':pd.DataFrame([{'KEY_ORDER':'602164B','CRD_SWIFT_DATE':'2026-01-01'}])}})
    assert 'SWIFT_SENT' in set(matrix.STAGE_CODE)
    assert 'PAYMENT' not in set(obs.STAGE_CODE)
    assert matrix.loc[matrix.STAGE_CODE.eq('SWIFT_SENT'),'STATUS'].iloc[0]=='OBSERVED'

def test_registration_is_never_order():
    raw=pd.DataFrame([{'شماره پرونده ثبت سفارش':'900000001','شماره ثبت سفارش':'88000001','وضعیت':'تایید شده'}])
    for f in (NtswAdapter().transform({'Import License':raw})['import_license'],IlAppendAdapter().transform({'Append':raw})['main']):
        assert f.KEY_REG.iloc[0]=='88000001'
        assert f.KEY_REG_FILE.iloc[0]=='900000001'
        assert f.KEY_ORDER.iloc[0]==''
    raw['شماره سفارش']='602164B'
    assert IlAppendAdapter().transform({'Append':raw})['main'].KEY_ORDER.iloc[0]=='602164B'

def test_repeated_license_status_preserved():
    raw=pd.DataFrame([{'شماره پرونده ثبت سفارش':'900000001','کد ثبت سفارش':'88000001','وضعیت':s} for s in ['تایید شده','ابطال']])
    lic=NtswAdapter().transform({'Import License':raw})['import_license']
    assert len(lic)==2 and lic.NTSW_LICENSE_STATUS_CONFLICT.all()
    assert set(lic.NTSW_LICENSE_STATUS)=={'تایید شده','ابطال'}

def test_commitment_status_conflict_quarantined():
    base={'کد ثبت سفارش':'88000001','شماره ردیف تعهد':'1','تعهد اولیه':100,'مانده تعهد':0,'ارز':'EUR'}
    raw=pd.DataFrame([{**base,'وضعیت رفع تعهد':s} for s in ['رفع تعهد شده','رفع تعهد نشده']])
    out=NtswAdapter().transform({'Release Commitment':raw})
    assert len(out['commitment_rows'])==2 and len(out['commitment_quarantine'])==2
    assert out['commitment'].empty

def allocation(status,date='2026-09-02'):
    return {'کد ثبت سفارش':'88000001','ردیف درخواست':'1','مبلغ درخواست':100,'ارز درخواست':'EUR','تاریخ ایجاد درخواست':'2026-09-01','تاریخ تایید':date,'وضعیت':status}

def test_equal_date_conflict_order_independent():
    raw=pd.DataFrame([allocation('تایید'),allocation('رد شده')])
    for data in (raw,raw.iloc[::-1]):
        out=NtswAdapter().transform({'Allocation':data})
        assert out['allocation'].empty
        assert len(out['allocation_history'])==2
        assert set(out['allocation_rows'].NTSW_REQUEST_STATE)=={'AMBIGUOUS'}
        assert len(out['allocation_quarantine'])==2

def test_identical_request_counted_once():
    row=allocation('تایید')
    out=NtswAdapter().transform({'Allocation':pd.DataFrame([row,row])})
    assert len(out['allocation_history'])==2 and len(out['allocation_rows'])==1
    assert float(out['allocation'].NTSW_ALLOCATED_AMOUNT.iloc[0])==100

def test_newer_status_requires_date():
    rows=[allocation('در گردش'),allocation('تایید','2026-09-03')]
    for data in (rows,rows[::-1]):
        out=NtswAdapter().transform({'Allocation':pd.DataFrame(data)})
        assert len(out['allocation_rows'])==1
        assert out['allocation_rows'].NTSW_REQUEST_STATE.iloc[0]=='ALLOCATED'

def test_scope_does_not_expand(tmp_path):
    wh=Warehouse(tmp_path/'w.sqlite')
    rid=publish(wh,{'ntsw':{'allocation_rows':pd.DataFrame([{'KEY_REG':'88000001','NTSW_REQ_AMOUNT':100,'NTSW_REQ_CURRENCY':'EUR','NTSW_REQ_DATE':'2026-09-01','NTSW_REQUEST_KEY':'1','NTSW_REQUEST_STATE':'OPEN'}])}})
    assert len(bundle_from_dwh('2026-09-22',wh)['events'])==1
    for scope in (pd.DataFrame(),pd.DataFrame([{'KEY_ORDER':'UNKNOWN'}])):
        b=bundle_from_dwh('2026-09-22',wh,scope=scope)
        assert b['events'].empty and b['scope_status']=='EMPTY_OR_UNRESOLVED'
        assert b['warehouse_run_id']==rid

def test_corruption_is_not_empty(tmp_path):
    p=tmp_path/'bad.sqlite';p.write_bytes(b'not a sqlite database')
    with pytest.raises(FinancialSourceUnavailable):bundle_from_dwh('2026-09-22',Warehouse(p,initialize=False))

def test_opus_unknown_flags():
    from gsi.stages.s20_derive import DeriveStage
    from gsi.stages.base import PipelineContext
    from datetime import date
    ctx=PipelineContext(rb=None,today=date(2026,9,22))
    df=DeriveStage().run(pd.DataFrame({'NTSW_BALANCE':[float('nan'),0,'bad',float('inf')]}),ctx)
    assert df.BALANCE_IS_UNKNOWN.tolist()==[True,False,True,True]
    assert 'FIN_RECEIPT_DATE' in ctx.extras['derive_coverage']['declared_unmeasured']

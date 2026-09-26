import pandas as pd

from gsi.cashflow.dwh import bundle_from_dwh, scope_regs_from_dwh, SOURCE_PRIORITY
from gsi.cashflow.engine import build_cashflow
from gsi.cashflow.inputs import pipeline_measurements, pipeline_observations
from gsi.warehouse.business_dwh import build as build_business_dwh
from gsi.warehouse.store import Warehouse


def _money_extras():
    reg='12345678'
    rows=[
        {'KEY_REG':reg,'EVENT_CODE':'REGISTRATION_VALUE','EVENT_DATE':'2026-07-01','AMOUNT':100,'CURRENCY':'EUR','SOURCE':'credit','REFERENCE':'credit#1','STATUS':'sent','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'BANK_FUNDING_IRR','EVENT_DATE':'2026-08-02','AMOUNT':8000,'CURRENCY':'IRR','SOURCE':'credit','REFERENCE':'credit#1','STATUS':'sent','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'SWIFT','EVENT_DATE':'2026-08-03','AMOUNT':80,'CURRENCY':'EUR','SOURCE':'credit','REFERENCE':'credit#1','STATUS':'LC1','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'ALLOCATION_REQUEST','EVENT_DATE':'2026-07-10','AMOUNT':100,'CURRENCY':'EUR','SOURCE':'ntsw/allocation','REFERENCE':'R1','STATUS':'ALLOCATED','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'ALLOCATION','EVENT_DATE':'2026-07-20','AMOUNT':100,'CURRENCY':'EUR','SOURCE':'ntsw/allocation','REFERENCE':'R1','STATUS':'ALLOCATED','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'FX_PURCHASE','EVENT_DATE':'2026-08-01','AMOUNT':80,'CURRENCY':'EUR','SOURCE':'fx_transaction','REFERENCE':'fx#1','STATUS':'done','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'SUPPLIER_PAYMENT','EVENT_DATE':'2026-08-05','AMOUNT':80,'CURRENCY':'EUR','SOURCE':'fx_transaction','REFERENCE':'fx#1','STATUS':'RECEIVED','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'COMMITMENT_INITIAL','EVENT_DATE':'2026-08-10','AMOUNT':100,'CURRENCY':'EUR','SOURCE':'ntsw/commitment','REFERENCE':'commitment#1','STATUS':'open','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'COMMITMENT_RELEASED','EVENT_DATE':'','AMOUNT':80,'CURRENCY':'EUR','SOURCE':'ntsw/commitment','REFERENCE':'commitment#1','STATUS':'open','NOTE':''},
        {'KEY_REG':reg,'EVENT_CODE':'COMMITMENT_BALANCE','EVENT_DATE':'2026-10-01','AMOUNT':20,'CURRENCY':'EUR','SOURCE':'ntsw/commitment','REFERENCE':'commitment#1','STATUS':'open','NOTE':'deadline'},
    ]
    return {'fx_money_ledger':pd.DataFrame(rows)}


def test_pipeline_bridge_no_longer_quarantines_every_dwh_fact():
    extras=_money_extras()
    events=pipeline_observations(extras)
    measurements=pipeline_measurements(extras,'2026-09-22')
    result=build_cashflow(events,measurements=measurements,as_of='2026-09-22')
    assert len(events) >= 7
    assert len(result['events']) >= 7
    assert not result['summary'].empty
    eur=result['summary'].query("currency == 'EUR'").iloc[0]
    assert float(eur['allocation']) == 100.0
    assert float(eur['paid']) == 80.0
    assert len(result['measurements']) == 1
    assert result['measurements'].iloc[0]['observed_at'] == '2026-09-22'


def test_native_dwh_prefers_ntsw_and_commercial_expert_over_sata(tmp_path):
    wh=Warehouse(tmp_path/'warehouse.sqlite')
    sources={
        'moghavemat':{'main':pd.DataFrame([{
            'KEY_ORDER':'O1','MOGH_PI_VALUE_SUM':120,'MOGH_CURRENCY':'EUR','MOGH_PO_SENT_DATE':'2026-07-01'}])},
        'ntsw':{
            'import_license':pd.DataFrame([{'KEY_REG':'11111111','KEY_REG_FILE':'900000001'}]),
            'allocation_rows':pd.DataFrame([{'KEY_REG':'11111111','NTSW_REQUEST_KEY':'N1',
                'NTSW_REQ_AMOUNT':120,'NTSW_REQ_CURRENCY':'EUR','NTSW_REQ_DATE':'2026-07-02',
                'NTSW_ALLOC_DATE':'2026-07-05','NTSW_REQUEST_STATE':'ALLOCATED'}]),
            'commitment':pd.DataFrame([{'KEY_REG':'11111111','NTSW_INITIAL_COMMIT':120,'NTSW_BALANCE':40,
                'NTSW_COMMIT_DATE':'2026-08-01','NTSW_DEADLINE':'2026-12-01','NTSW_CURRENCY':'EUR'}])},
        'ilappend':{'main':pd.DataFrame([{'KEY_ORDER':'O1','KEY_REG_FILE':'900000001','IL_KEY_REG':''}])},
        'sata':{'main':pd.DataFrame([{'KEY_ORDER':'O1','KEY_BL':'B1','SATA_KEY_REG':'22222222'}])},
        'abbasi':{'main':pd.DataFrame([{'KEY_ORDER':'O1','KEY_BL':'B1'}])},
    }
    with wh.run({'reference_date':'2026-09-22','version':'test'}) as rid:
        build_business_dwh(wh,sources,rid)
    wh.publish(rid,slots=('dwh','report'))

    bundle=bundle_from_dwh('2026-09-22',wh)
    assert bundle['origin']=='SQLITE_BUSINESS_DWH'
    assert SOURCE_PRIORITY['moghavemat']==SOURCE_PRIORITY['ntsw']
    assert SOURCE_PRIORITY['moghavemat']>SOURCE_PRIORITY['sata']
    reg_events=bundle['events'][bundle['events']['kind'].eq('REGISTRATION')]
    assert not reg_events.empty
    assert set(reg_events['case_id'])=={'11111111'}
    assert 'DWH/moghavemat/main' in set(reg_events['source'])
    assert '22222222' not in set(bundle['events']['case_id'])

    result=build_cashflow(bundle['events'],measurements=bundle['measurements'],as_of='2026-09-22')
    assert not result['summary'].empty
    assert '11111111' in set(result['summary']['case_id'])

    scope=scope_regs_from_dwh(pd.DataFrame([{'CANONICAL_ORDER':'O1'}]),wh)
    assert scope=={'11111111'}

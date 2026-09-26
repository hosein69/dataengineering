# -*- coding: utf-8 -*-
from datetime import date
import pandas as pd

from gsi.cashflow.engine import build_cashflow
from gsi.pipeline import Pipeline
from gsi.resolve.partition import partition, M1_MAIN


def _ev(eid, kind, amount='100', currency='EUR', date_='2026-01-01'):
    return dict(event_id=eid, case_id='11111111', kind=kind, amount=amount,
                currency=currency, date=date_, document='DOC-'+eid, source='TEST',
                status='SOURCE_FACT')


def test_primary_population_is_expert_plus_ntsw_not_abbasi():
    p=Pipeline(today=date(2026,9,22))
    p.sources={
        'moghavemat':{'main':pd.DataFrame([{
            'KEY_ORDER':'602164B','MOGH_ORDER_REF':'602164B','MOGH_PRESENT':True,
            'MOGH_MATERIAL':'M1','MOGH_MATERIAL_DESC':'expert'}])},
        'ntsw':{
            'import_license':pd.DataFrame([
                {'KEY_ORDER':'602164B','KEY_REG':'11111111','NTSW_KEY_REG':'11111111','KEY_REG_FILE':'900000001'},
                {'KEY_ORDER':'','KEY_REG':'33333333','NTSW_KEY_REG':'33333333','KEY_REG_FILE':'900000003'},
            ]),
            'commitment':pd.DataFrame(), 'allocation':pd.DataFrame(),
        },
        'abbasi':{'main':pd.DataFrame([
            {'KEY_ORDER':'602164B','KEY_BL':'BL000001','BL_STATUS':'primary enrichment'},
            {'KEY_ORDER':'999999B','KEY_BL':'BL999999','BL_STATUS':'must not enter'},
        ])},
        'sata':{'main':pd.DataFrame([{'KEY_ORDER':'602164B','KEY_BL':'BL000001','SATA_KEY_REG':'22222222'}])},
        'ilappend':{'main':pd.DataFrame()},
    }
    p.ctx.sources=p.sources
    out=p.build_base()
    assert '999999B' not in set(out['KEY_ORDER'].astype(str))
    assert {'11111111','33333333'} <= set(out['KEY_REG'].astype(str))
    expert=out[out['KEY_ORDER'].eq('602164B')].iloc[0]
    assert expert['KEY_REG']=='11111111'
    assert expert['KEY_BL']=='BL000001'
    ntsw_only=out[out['KEY_REG'].eq('33333333')].iloc[0]
    assert bool(ntsw_only['IS_IN_NTSW_PRIMARY']) is True
    assert ntsw_only['POPULATION_SOURCE']=='NTSW'


def test_one_primary_order_can_keep_multiple_abbasi_bls_without_abbasi_population():
    p=Pipeline(today=date(2026,9,22))
    p.sources={
        'moghavemat':{'main':pd.DataFrame([{'KEY_ORDER':'602164B','MOGH_PRESENT':True}])},
        'ntsw':{'import_license':pd.DataFrame([{'KEY_ORDER':'602164B','KEY_REG':'11111111','NTSW_KEY_REG':'11111111'}]),
                'commitment':pd.DataFrame(), 'allocation':pd.DataFrame()},
        'abbasi':{'main':pd.DataFrame([
            {'KEY_ORDER':'602164B','KEY_BL':'BL000001'},
            {'KEY_ORDER':'602164B','KEY_BL':'BL000002'},
            {'KEY_ORDER':'777777B','KEY_BL':'BL777777'},
        ])},
    }
    p.ctx.sources=p.sources
    out=p.build_base()
    assert set(out['KEY_BL'])=={'BL000001','BL000002'}
    assert set(out['KEY_ORDER'])=={'602164B'}


def test_ntsw_only_primary_row_is_main_population_not_to_resolve():
    df=pd.DataFrame([{
        'CANONICAL_ORDER':'','CANONICAL_BL':'','IS_IN_MOGHAVEMAT':False,
        'IS_IN_NTSW_PRIMARY':True,'SATA_NO':'','COTAGE_NO':''
    }])
    res=partition(df,moghavemat_available=False)
    assert len(res.main)==1
    assert res.main.iloc[0]['PARTITION_COVERAGE']==M1_MAIN


def test_cashflow_chain_exposes_missing_funding_and_settlement_without_inference():
    rows=[
        _ev('pi','REGISTRATION'), _ev('q','QUEUE'), _ev('a','ALLOCATION'),
        _ev('c','COMMITMENT'), _ev('x','FX_BUY','80'), _ev('p','PAYMENT','80'),
    ]
    links=pd.DataFrame([dict(link_id='xp',relation_type='SOURCE_RECORD_FLOW',from_event='x',to_event='p',
                             from_amount='80',to_amount='80',document='FX-ROW')])
    ms=pd.DataFrame([dict(measurement_id='m1',case_id='11111111',metric='COMMITMENT_BALANCE',
                          observed_at='2026-01-31',amount='40',currency='EUR',source='NTSW',document='NTSW-SNAPSHOT')])
    r=build_cashflow(pd.DataFrame(rows),links=links,measurements=ms,as_of='2026-01-31')
    chain=r['chain']
    # Missing upstream stages are not declared mandatory without an explicit
    # applicability contract. Downstream evidence remains visible but absence
    # is not upgraded to a process violation by inference alone.
    assert chain.query("stage == 'FUNDING'").iloc[0]['status']=='NOT_YET_EVIDENCED'
    assert chain.query("stage == 'SETTLEMENT_RETURN'").iloc[0]['status']=='NOT_YET_EVIDENCED'
    codes=set(r['issues']['code'])
    assert 'MISSING_FUNDING_EVIDENCE' not in codes
    assert 'MISSING_SETTLEMENT_EVIDENCE' not in codes
    assert 'SNAPSHOT_LEDGER_MISMATCH' in codes
    assert chain.query("stage == 'PAYMENT'").iloc[0]['status']=='EVIDENCED'


def test_complete_obligation_link_reconciles_remaining_commitment():
    rows=[
        _ev('pi','REGISTRATION'), _ev('q','QUEUE'), _ev('a','ALLOCATION'),
        _ev('c','COMMITMENT'), _ev('x','FX_BUY','80'), _ev('f','FUNDING','80'),
        _ev('p','PAYMENT','80'), _ev('s','SETTLEMENT','60'),
    ]
    links=pd.DataFrame([
        dict(link_id='xp',relation_type='SOURCE_RECORD_FLOW',from_event='x',to_event='p',from_amount='80',to_amount='80',document='FX-ROW'),
        dict(link_id='cs',relation_type='OBLIGATION_SETTLEMENT',from_event='c',to_event='s',from_amount='60',to_amount='60',document='SETTLEMENT-DOC'),
    ])
    ms=pd.DataFrame([dict(measurement_id='m1',case_id='11111111',metric='COMMITMENT_BALANCE',
                          observed_at='2026-01-31',amount='40',currency='EUR',source='NTSW',document='NTSW-SNAPSHOT')])
    r=build_cashflow(pd.DataFrame(rows),links=links,measurements=ms,as_of='2026-01-31')
    assert r['reconciliation'].iloc[0]['status']=='MATCH'
    assert r['chain'].query("stage == 'SETTLEMENT_RETURN'").iloc[0]['status']=='EVIDENCED'
    assert 'MISSING_SETTLEMENT_EVIDENCE' not in set(r['issues']['code'])


def test_dwh_same_fx_source_row_creates_documented_purchase_to_payment_link(tmp_path):
    from gsi.cashflow.dwh import bundle_from_dwh
    from gsi.warehouse.business_dwh import build as build_business_dwh
    from gsi.warehouse.store import Warehouse
    wh=Warehouse(tmp_path/'warehouse.sqlite')
    sources={
        'moghavemat':{'main':pd.DataFrame([{'KEY_ORDER':'602164B','MOGH_PI_VALUE_SUM':100,'MOGH_CURRENCY':'EUR','MOGH_PO_SENT_DATE':'2026-01-01'}])},
        'ntsw':{'import_license':pd.DataFrame([{'KEY_ORDER':'602164B','KEY_REG':'11111111','NTSW_KEY_REG':'11111111'}])},
        'fx_transaction':{'main':pd.DataFrame([{
            'KEY_REG':'11111111','FX_AMOUNT':100,'FX_CURRENCY':'EUR','FX_BUY_DATE':'2026-01-10',
            'FX_PAID_AMOUNT':80,'FX_PAID_CURRENCY':'EUR','FX_RECEIPT_DATE':'2026-01-11'}])},
    }
    with wh.run({'reference_date':'2026-01-31','version':'29.7.4-test'}) as rid:
        build_business_dwh(wh,sources,rid)
    wh.publish(rid,slots=('dwh','report'))
    b=bundle_from_dwh('2026-01-31',wh)
    assert len(b['links'])==1
    assert b['links'].iloc[0]['relation_type']=='SOURCE_RECORD_FLOW'
    r=build_cashflow(b['events'],links=b['links'],measurements=b['measurements'],as_of='2026-01-31')
    eur=r['summary'].query("case_id == '11111111' and currency == 'EUR'").iloc[0]
    assert float(eur['paid'])==80.0
    assert float(eur['untraced_payment'])==0.0

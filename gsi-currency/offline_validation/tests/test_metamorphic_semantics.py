from __future__ import annotations
import itertools, math
from decimal import Decimal
import numpy as np
import pandas as pd
import pytest
from gsi.finance.equivalents import commitment_equivalents
from gsi.report.financial_summary import commitment_equivalent_summary
from gsi.cashflow.engine import build_cashflow


def _evt(eid,kind='PAYMENT',amount=100,currency='USD',case='12345678',**kw):
    r={'event_id':eid,'case_id':case,'kind':kind,'date':'2026-01-01','amount':amount,
       'currency':currency,'document':'DOC-'+eid,'source':'fixture','status':'SOURCE_FACT'}
    r.update(kw); return r

@pytest.mark.parametrize('unknown',[None,'',np.nan,pd.NA])
def test_unknown_commitment_never_becomes_covered_zero(unknown):
    df=pd.DataFrame([{'KEY_REG':'R1','FX_NTSW_BALANCE_EUR_EQ':0,
                      'FX_NTSW_BALANCE_RIAL_EQ':0,'FX_NTSW_BALANCE_UNKNOWN':True,
                      'FX_NTSW_BALANCE':unknown}])
    s=commitment_equivalent_summary(df)
    assert s.get('covered',0)==0
    assert s.get('eur') in (None,0) and s.get('irr') in (None,0)

@pytest.mark.parametrize('bad',[float('inf'),float('-inf'),'Infinity','-Infinity'])
def test_nonfinite_balance_cannot_produce_equivalent(bad):
    out=commitment_equivalents(reg='R1',currency='USD',balance=bad,
        fx_rows=pd.DataFrame([{'KEY_REG':'R1','FX_CURRENCY':'USD','FX_AMOUNT':100,
                              'FX_EUR_VALUE':90,'FX_RIAL_VALUE':60000000,'FX_STATUS':'ACTUAL'}]))
    assert out['FX_NTSW_BALANCE_EUR_EQ'] is None
    assert out['FX_NTSW_BALANCE_RIAL_EQ'] is None

@pytest.mark.parametrize('status',['PLANNED','FORECAST','DRAFT'])
def test_nonactual_purchase_does_not_change_actual_valuation(status):
    actual={'KEY_REG':'R1','FX_CURRENCY':'USD','FX_AMOUNT':100,'FX_EUR_VALUE':90,
            'FX_RIAL_VALUE':60000000,'FX_STATUS':'ACTUAL'}
    planned={'KEY_REG':'R1','FX_CURRENCY':'USD','FX_AMOUNT':900,'FX_EUR_VALUE':810,
             'FX_RIAL_VALUE':540000000,'FX_STATUS':status}
    base=commitment_equivalents(reg='R1',currency='USD',balance=10,fx_rows=pd.DataFrame([actual]))
    more=commitment_equivalents(reg='R1',currency='USD',balance=10,fx_rows=pd.DataFrame([actual,planned]))
    assert more['FX_NTSW_BALANCE_EUR_EQ']==base['FX_NTSW_BALANCE_EUR_EQ']
    assert more['FX_NTSW_BALANCE_RIAL_EQ']==base['FX_NTSW_BALANCE_RIAL_EQ']

@pytest.mark.parametrize('other_cur',['EUR','CNY','AED','JPY'])
def test_unrelated_currency_evidence_cannot_change_target_currency(other_cur):
    target={'KEY_REG':'R1','FX_CURRENCY':'USD','FX_AMOUNT':100,'FX_EUR_VALUE':90,'FX_RIAL_VALUE':60000000}
    other={'KEY_REG':'R1','FX_CURRENCY':other_cur,'FX_AMOUNT':1000,'FX_EUR_VALUE':999,'FX_RIAL_VALUE':999999999}
    a=commitment_equivalents(reg='R1',currency='USD',balance=10,fx_rows=pd.DataFrame([target]))
    b=commitment_equivalents(reg='R1',currency='USD',balance=10,fx_rows=pd.DataFrame([target,other]))
    assert a['FX_NTSW_BALANCE_EUR_EQ']==b['FX_NTSW_BALANCE_EUR_EQ']
    assert a['FX_NTSW_BALANCE_RIAL_EQ']==b['FX_NTSW_BALANCE_RIAL_EQ']

@pytest.mark.parametrize('other_reg',['R2','99999999','OTHER'])
def test_unrelated_registration_cannot_change_target_case(other_reg):
    target={'KEY_REG':'R1','FX_CURRENCY':'USD','FX_AMOUNT':100,'FX_EUR_VALUE':90,'FX_RIAL_VALUE':60000000}
    other={'KEY_REG':other_reg,'FX_CURRENCY':'USD','FX_AMOUNT':1,'FX_EUR_VALUE':999,'FX_RIAL_VALUE':999999999}
    a=commitment_equivalents(reg='R1',currency='USD',balance=10,fx_rows=pd.DataFrame([target]))
    b=commitment_equivalents(reg='R1',currency='USD',balance=10,fx_rows=pd.DataFrame([target,other]))
    assert a['FX_NTSW_BALANCE_EUR_EQ']==b['FX_NTSW_BALANCE_EUR_EQ']
    assert a['FX_NTSW_BALANCE_RIAL_EQ']==b['FX_NTSW_BALANCE_RIAL_EQ']

def test_allocation_conflict_is_permutation_invariant():
    rows=[
      {'KEY_REG':'R1','NTSW_REQ_CURRENCY':'USD','NTSW_FX_RATE_NUMERIC':10,'NTSW_ALLOC_DATE':'2026-01-01','NTSW_REQUEST_STATE':'ALLOCATED'},
      {'KEY_REG':'R1','NTSW_REQ_CURRENCY':'USD','NTSW_FX_RATE_NUMERIC':20,'NTSW_ALLOC_DATE':'2026-01-01','NTSW_REQUEST_STATE':'ALLOCATED'},
    ]
    vals=[]
    for perm in itertools.permutations(rows):
        o=commitment_equivalents(reg='R1',currency='USD',balance=10,allocation_rows=pd.DataFrame(list(perm)))
        vals.append((o['FX_NTSW_BALANCE_RIAL_EQ'],o.get('FX_NTSW_RIAL_EQ_BASIS')))
    assert len(set(vals))==1
    assert vals[0][0] is None

def test_cashflow_row_order_invariance_for_valid_events():
    rows=[_evt('A','ALLOCATION',60),_evt('B','FX_BUY',20),_evt('C','PAYMENT',10)]
    sig=[]
    for perm in itertools.permutations(rows):
        r=build_cashflow(pd.DataFrame(list(perm)),as_of='2026-09-24')
        s=r['summary'].iloc[0]
        sig.append((s.allocation,s.purchased,s.paid,len(r['events'])))
    assert len(set(sig))==1

def test_distinct_equal_events_different_currency_survive():
    rows=[_evt('A','FX_BUY',100,'USD'),_evt('B','FX_BUY',100,'EUR')]
    r=build_cashflow(pd.DataFrame(rows),as_of='2026-09-24')
    assert len(r['events'])==2
    assert set(r['events'].currency)=={'USD','EUR'}

def test_exact_source_replay_is_idempotent_but_distinct_ids_are_not():
    one=_evt('A',source_event_id='TX-1')
    replay=dict(one); replay['event_id']='B'
    r=build_cashflow(pd.DataFrame([one,replay]),as_of='2026-09-24')
    assert len(r['events'])==1
    x=build_cashflow(pd.DataFrame([_evt('A'),_evt('B')]),as_of='2026-09-24')
    assert len(x['events'])==2 and x['summary'].iloc[0].paid==Decimal(200)

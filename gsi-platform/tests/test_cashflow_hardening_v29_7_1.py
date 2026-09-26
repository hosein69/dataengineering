import pandas as pd
from test_cashflow_v29_7 import event, run, link, codes


def test_reversed_payment_links_are_not_counted():
    r=run(event('p','PAYMENT','40'),event('s','SHIPMENT','40'),
          event('r','REVERSAL','40',reversal_of='p',from_account='EXTERNAL:supplier',to_account='OWN:bank'),
          links=pd.DataFrame([link('l','p','s','40','40')]))
    assert r['links'].empty
    assert 'REVERSED_EVENT_LINK' in codes(r)


def test_source_replay_account_conflict_is_quarantined():
    a=event('a','PAYMENT',source_event_id='native',document='same')
    b=event('b','PAYMENT',source_event_id='native',document='same',from_account='OWN:other')
    assert run(a,b)['events'].empty


def test_payment_and_obligation_links_have_separate_capacity():
    r=run(event('p','PAYMENT'),event('c','COMMITMENT'),event('s','SETTLEMENT'),
          links=pd.DataFrame([link('a','p','s','100','100'),
                              link('b','c','s','100','100',relation_type='OBLIGATION_SETTLEMENT')]))
    assert len(r['links'])==2
    assert r['summary'].iloc[0]['commitment_remaining']==0


def test_snapshot_conflict_and_date_gap():
    m=dict(measurement_id='a',case_id='R1',metric='COMMITMENT_BALANCE',observed_at='2026-01-31',amount='100',currency='EUR',source='NTSW')
    r=run(event('c','COMMITMENT'),measurements=pd.DataFrame([m,dict(m,measurement_id='b',amount='90')]))
    assert r['reconciliation'].iloc[0]['status']=='CONFLICT'
    r=run(event('c','COMMITMENT'),measurements=pd.DataFrame([dict(m,observed_at='2026-01-20')]))
    assert r['reconciliation'].iloc[0]['status']=='DATE_MISMATCH'


def test_transfer_reversal_does_not_create_external_cashflow():
    r=run(event('t','TRANSFER',from_account='OWN:a',to_account='OWN:b'),
          event('r','REVERSAL',reversal_of='t',from_account='OWN:b',to_account='OWN:a'))
    assert r['periods']['net_movement'].sum()==0 if not r['periods'].empty else True

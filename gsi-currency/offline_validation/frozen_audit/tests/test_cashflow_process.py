"""Graph/event, transport, customs, payment and legal-metadata controls; no invented legal deadlines."""
from datetime import date
from decimal import Decimal
import itertools
import pandas as pd
import pytest
from gsi.cashflow.engine import build_cashflow,select_rate

def event(eid,kind='PAYMENT',amount='100',currency='USD',**kw):
    r=dict(event_id=eid,case_id='12345678',kind=kind,date='2026-01-01',amount=amount,currency=currency,document='DOC-'+eid,source='fixture',status='SOURCE_FACT');r.update(kw);return r

def run(rows,**kw):return build_cashflow(pd.DataFrame(rows),as_of='2026-09-24',**kw)
def codes(r):return set(r['issues'].code)
def link(a,b,amount=50,**kw):
    r=dict(link_id='L1',from_event=a,to_event=b,from_amount=amount,to_amount=amount,document='MATCH-DOC',relation_type='OBLIGATION_SETTLEMENT');r.update(kw);return r

@pytest.mark.parametrize('kind,metric',[('ALLOCATION','allocation'),('FX_BUY','purchased'),('PAYMENT','paid'),('SHIPMENT','shipment_value'),('CUSTOMS','customs_value')])
def test_each_event_preserves_own_amount(kind,metric):
    """Each event contributes only its own native amount and does not invent other events."""
    r=run([event('E1',kind)])
    assert r['events'].kind.tolist()==[kind]
    assert r['summary'].iloc[0][metric]==Decimal(100)
    for other in {'allocation','purchased','paid','shipment_value','customs_value'}-{metric}:
        assert pd.isna(r['summary'].iloc[0][other])

@pytest.mark.parametrize('kind',['SHIPMENT','CUSTOMS','CLEARANCE','WAREHOUSE','BANK_DOCS'])
def test_transport_customs_document_does_not_discharge_commitment(kind):
    """Transport/customs/clearance evidence alone is not a linked settlement event (user rules; CBI part7 §ب1-1 context)."""
    r=run([event('C','COMMITMENT',100),event('D',kind,100,bl_id='BL1')])
    s=r['summary'].iloc[0]
    assert s.commitment_remaining==100 and s.settled==0
    assert 'SETTLEMENT' not in set(r['events'].kind)

@pytest.mark.parametrize('kind',['CLEARANCE','WAREHOUSE','BANK_DOCS'])
def test_optional_nonmonetary_event_can_keep_unknown_amount(kind):
    """Presence of a nonmonetary document need not manufacture a financial amount."""
    r=run([event('D',kind,None,'')])
    assert len(r['events'])==1 and pd.isna(r['events'].amount.iloc[0])

def test_unlinked_settlement_does_not_reduce_obligation():
    """A settlement record without an explicit commitment relation remains evidence, not discharged amount."""
    r=run([event('C','COMMITMENT',100),event('S','SETTLEMENT',40)])
    assert r['summary'].iloc[0].commitment_remaining==100 and 'UNLINKED_SETTLEMENT' in codes(r)

@pytest.mark.parametrize('amount',[1,40,100])
def test_partial_discharge_exact_remaining(amount):
    """A documented same-case same-currency discharge reduces only its explicitly linked amount."""
    r=run([event('C','COMMITMENT',100),event('S','SETTLEMENT',amount)],links=pd.DataFrame([link('C','S',amount)]))
    assert r['summary'].iloc[0].commitment_remaining==Decimal(100)-Decimal(amount)
    assert r['summary'].iloc[0].settled==amount

@pytest.mark.parametrize('variant',['cross_reg','cross_currency','overcapacity','wrong_relation','backdated'])
def test_unsupported_settlement_link_is_excluded(variant):
    """Unauthorised case/currency transfer, excess amount, wrong relation and reversed event order cannot discharge."""
    a=event('C','COMMITMENT',100);b=event('S','SETTLEMENT',40);l=link('C','S',40)
    if variant=='cross_reg':b['case_id']='87654321'
    if variant=='cross_currency':b['currency']='EUR'
    if variant=='overcapacity':l['from_amount']=l['to_amount']=120;b['amount']=120
    if variant=='wrong_relation':l['relation_type']='SIMILAR_HEADER'
    if variant=='backdated':b['date']='2025-12-31'
    r=run([a,b],links=pd.DataFrame([l]))
    assert r['links'].empty
    assert r['summary'].query("case_id == '12345678' and currency == 'USD'").iloc[0].commitment_remaining==100

def test_settlement_and_return_share_obligation_capacity():
    """Settlement60 + return60 cannot consume commitment100 via separately valid-looking links."""
    r=run([event('C','COMMITMENT',100),event('S','SETTLEMENT',60),event('R','COMMITMENT_RETURN',60)],links=pd.DataFrame([link('C','S',60),link('C','R',60,link_id='L2',relation_type='OBLIGATION_RETURN')]))
    assert r['links'].empty and 'OVERALLOCATED_LINK' in codes(r)

def test_two_bls_do_not_duplicate_payment_capacity():
    """One payment100 cannot be matched at full value to two distinct BLs."""
    r=run([event('P',amount=100),event('S1','SHIPMENT',100,bl_id='BL1'),event('S2','SHIPMENT',100,bl_id='BL2')],links=pd.DataFrame([link('P','S1',100),link('P','S2',100,link_id='L2')]))
    assert r['links'].empty and r['summary'].iloc[0].paid==100

def test_split_shipments_reconcile_without_double_count():
    """Documented BL40 + BL60 links consume exactly payment100; two documents survive."""
    r=run([event('P',amount=100),event('S1','SHIPMENT',40,bl_id='BL1'),event('S2','SHIPMENT',60,bl_id='BL2')],links=pd.DataFrame([link('P','S1',40),link('P','S2',60,link_id='L2')]))
    assert len(r['documents'])==2 and len(r['links'])==2
    assert r['summary'].iloc[0].unmatched_payment==0

@pytest.mark.parametrize('n',[1,2,25])
def test_exact_event_replay_idempotency(n):
    """Replaying the same event identifier and content never multiplies amount."""
    r=run([event('P')]*n)
    assert len(r['events'])==1 and r['summary'].iloc[0].paid==100

def test_distinct_equal_payment_events_are_not_deduplicated():
    """Two distinct event IDs with equal amount/date remain two actual events."""
    r=run([event('P1'),event('P2')])
    assert len(r['events'])==2 and r['summary'].iloc[0].paid==200

def test_conflicting_event_id_quarantines_both_versions():
    """A reused event ID with differing amounts has no authoritative winner."""
    for vals in [[100,120],[120,100]]:
        r=run([event('P',amount=v) for v in vals])
        assert r['events'].empty and len(r['observations'])==2 and 'CONFLICTING_ID' in codes(r)

@pytest.mark.parametrize('amount',[None,'unknown','Infinity',-1])
def test_invalid_payment_retained_as_observation(amount):
    """Unknown, nonfinite and invalid negative payments are excluded with reason and raw observation retained."""
    r=run([event('P',amount=amount)])
    assert r['events'].empty and len(r['observations'])==1 and 'MISSING_AMOUNT_CURRENCY' in codes(r)

@pytest.mark.parametrize('currency',['IRT','TOMAN','ریال','US D','US1'])
def test_ambiguous_currency_unit_rejected(currency):
    """Rial/toman ambiguity and invalid currency labels cannot enter monetary totals."""
    r=run([event('P',currency=currency)])
    assert r['events'].empty and codes(r)&{'AMBIGUOUS_CURRENCY_UNIT','INVALID_CURRENCY_CODE'}

def test_zero_payment_is_distinct_from_unknown():
    """Explicit zero may remain an observed fact; it does not mean missing amount."""
    r=run([event('P',amount=0)])
    assert len(r['events'])==1 and r['summary'].iloc[0].paid==0

@pytest.mark.parametrize('field',['document','source','event_id','case_id','date'])
def test_missing_required_evidence_cannot_post(field):
    """Missing event identity, document, source, date or case makes financial posting unproven."""
    row=event('P');row[field]='';r=run([row])
    assert r['events'].empty and len(r['observations'])==1

def test_future_event_excluded_as_of_cutoff():
    """As-of report cannot include next-day payment."""
    r=run([event('P',date='2026-09-25')])
    assert r['events'].empty and 'FUTURE_EVENT' in codes(r)

def test_cash_balance_requires_opening():
    """Posted account movement without opening balance leaves closing unknown."""
    r=run([event('P',status='POSTED',from_account='OWN:USD',to_account='VENDOR:1')])
    assert r['accounts'].iloc[0].net_movement==-100
    assert pd.isna(r['accounts'].iloc[0].closing)

def test_decimal_payment_conservation():
    """Decimal0.1+0.2 produces exact0.3; no binary float oracle."""
    r=run([event('A',amount='0.1'),event('B',amount='0.2')])
    assert r['summary'].iloc[0].paid==Decimal('0.3')

def test_payment_only_does_not_prove_mandatory_upstream_stages():
    """Absent a process applicability contract, payment alone cannot imply obligatory PI/allocation/FX-buy stages."""
    r=run([event('P')])
    forbidden={'MISSING_PI_EVIDENCE','MISSING_ALLOCATION_REQUEST_EVIDENCE','MISSING_ALLOCATION_EVIDENCE','MISSING_FX_BUY_EVIDENCE'}
    assert not codes(r)&forbidden,sorted(codes(r)&forbidden)

def test_chain_linked_amount_never_adds_unlike_currencies():
    """A case-level linked amount must carry currency buckets; USD10+EUR20 cannot become naked30."""
    rows=[event('C1','COMMITMENT',10,'USD'),event('S1','SETTLEMENT',10,'USD'),event('C2','COMMITMENT',20,'EUR'),event('S2','SETTLEMENT',20,'EUR')]
    links=[link('C1','S1',10),link('C2','S2',20,link_id='L2')]
    r=run(rows,links=pd.DataFrame(links));cell=r['chain'].query("stage == 'SETTLEMENT_RETURN'").iloc[0].linked_amount
    assert cell!='30',f'mixed currency scalar: {cell!r}'

def test_allocation_and_purchase_remain_independent_partial_events():
    """Allocation60+40 and purchase20+30 preserve allocation100, purchased50, with no inferred payment."""
    rows=[event('A1','ALLOCATION',60),event('A2','ALLOCATION',40),event('F1','FX_BUY',20),event('F2','FX_BUY',30)]
    r=run(rows);s=r['summary'].iloc[0]
    assert len(r['events'])==4 and s.allocation==100 and s.purchased==50 and pd.isna(s.paid)

def test_native_source_replay_detected_across_import_ids():
    """Same source transaction under different ingestion IDs remains one source event."""
    a=event('I1',source_event_id='TX1');b=event('I2',source_event_id='TX1');b['document']=a['document']
    r=run([a,b])
    assert len(r['events'])==1 and r['summary'].iloc[0].paid==100 and 'SOURCE_REPLAY_REMOVED' in codes(r)

def test_partial_payment_reversal_is_additional_auditable_event():
    """Payment100 plus documented reversal40 leaves paid60 while retaining both immutable events."""
    a=event('P',status='POSTED',from_account='OWN:USD',to_account='VENDOR:1')
    b=event('R','REVERSAL',40,status='POSTED',from_account='VENDOR:1',to_account='OWN:USD',reversal_of='P',date='2026-01-02')
    r=run([a,b])
    assert len(r['events'])==2 and r['summary'].iloc[0].paid==60

@pytest.mark.parametrize('change',[{'case_id':'87654321'},{'currency':'EUR'},{'amount':101},{'date':'2025-12-31'},{'reversal_of':'ABSENT'}])
def test_invalid_reversal_cannot_change_original_payment(change):
    """Reversal cannot exceed or cross the original amount, case, currency, identity or chronology."""
    a=event('P',status='POSTED',from_account='OWN:USD',to_account='VENDOR:1')
    b=event('R','REVERSAL',40,status='POSTED',from_account='VENDOR:1',to_account='OWN:USD',reversal_of='P',date='2026-01-02');b.update(change)
    r=run([a,b])
    assert r['events'].event_id.tolist()==['P'] and r['summary'].iloc[0].paid==100

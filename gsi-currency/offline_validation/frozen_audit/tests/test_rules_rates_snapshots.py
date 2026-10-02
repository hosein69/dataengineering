"""Validate rule metadata, effective scope, reference-rate selection and snapshot semantics.
Synthetic rule records test the software gate, not the substantive legality of a deadline.
"""
from datetime import date
from decimal import Decimal
import pandas as pd
import pytest
from gsi.cashflow.engine import build_cashflow,select_rate

def evt(**kw):
    r=dict(event_id='C',case_id='12345678',kind='COMMITMENT',date='2026-01-01',amount=100,currency='USD',document='DOC',source='fixture',status='SOURCE_FACT',rule_id='R1',due_date='2026-09-30');r.update(kw);return r

def rule(**kw):
    r=dict(rule_id='R1',kind='COMMITMENT',jurisdiction='IR',authority='SYNTHETIC_TEST_AUTHORITY',circular_no='FIXTURE',publication_date='2025-12-01',effective_from='2026-01-01',effective_to='2026-12-31',source='synthetic-fixture',source_url='https://example.invalid/fixture',source_hash='0'*64,approved='true',approved_by='fixture-reviewer',approved_at='2026-01-01');r.update(kw);return r

def rate(**kw):
    r=dict(base='USD',quote='IRR',rate=10,purpose='accounting',regime='',approved='true',date='2026-09-24',max_age_days=1,source='fixture');r.update(kw);return r

@pytest.mark.parametrize('field',['source_hash','authority','source_url','approved_by','approved_at','effective_from','effective_to'])
def test_incomplete_rule_provenance_never_verifies(field):
    """A declared due date cannot be legally verified if mandatory rule metadata is absent."""
    rr=rule();rr[field]=''
    out=build_cashflow(pd.DataFrame([evt()]),rules=pd.DataFrame([rr]),as_of='2026-09-24')
    assert out['rule_register'].iloc[0].verification_status=='UNVERIFIED'
    assert 'تأیید نشده' in out['deadlines'].iloc[0].basis

@pytest.mark.parametrize('override',[{'effective_to':'2026-01-31'},{'effective_from':'2026-02-01'},{'kind':'PAYMENT'},{'approved':'false'}])
def test_rule_scope_and_validity_cannot_be_bypassed(override):
    """Expired, not-effective-at-event, wrong-event-kind or unapproved rules cannot verify the event deadline."""
    out=build_cashflow(pd.DataFrame([evt()]),rules=pd.DataFrame([rule(**override)]),as_of='2026-09-24')
    assert 'تأیید نشده' in out['deadlines'].iloc[0].basis

def test_duplicate_active_rule_is_ambiguous():
    """Two competing active rule entries cannot silently select the last entry."""
    out=build_cashflow(pd.DataFrame([evt()]),rules=pd.DataFrame([rule(),rule(circular_no='OTHER')]),as_of='2026-09-24')
    assert 'تأیید نشده' in out['deadlines'].iloc[0].basis

@pytest.mark.parametrize('change',[{'base':'EUR'},{'quote':'EUR'},{'purpose':'customs'},{'regime':'other'},{'approved':'false'},{'source':''},{'date':'2026-09-25'},{'date':'2026-09-01'},{'rate':0},{'rate':'Infinity'}])
def test_reference_rate_context_guards(change):
    """Reference rate must match currency pair, date, authority approval, purpose/regime and validity."""
    value,_,_=select_rate(pd.DataFrame([rate(**change)]),'USD','IRR',date(2026,9,24))
    assert value is None

def test_conflicting_reference_rate_withheld():
    """Conflicting latest reference rates are unknown independent of row ordering."""
    for rows in [[rate(rate=10),rate(rate=20)],[rate(rate=20),rate(rate=10)]]:
        v,_,status=select_rate(pd.DataFrame(rows),'USD','IRR',date(2026,9,24))
        assert v is None and status=='CONFLICTING_RATE'

def test_exact_reference_rate_boundary():
    """One-day-old approved rate with one-day validity is valid at the inclusive boundary."""
    v,_,_=select_rate(pd.DataFrame([rate(date='2026-09-23')]),'USD','IRR',date(2026,9,24))
    assert v==Decimal(10)

def measure(mid,amount,when='2026-09-24'):
    return dict(measurement_id=mid,case_id='12345678',metric='COMMITMENT_BALANCE',observed_at=when,amount=amount,currency='USD',source='fixture',source_record_id=mid,document='DOC-'+mid,status='SOURCE_FACT')

def test_snapshot_is_not_incremental_event():
    """Two historical balance snapshots cannot be summed into commitment or discharge events."""
    out=build_cashflow(pd.DataFrame([evt()]),measurements=pd.DataFrame([measure('M1',80,'2026-09-23'),measure('M2',60)]),as_of='2026-09-24')
    assert len(out['events'])==1 and out['summary'].iloc[0].commitment_remaining==100
    assert len(out['reconciliation'])==1 and out['reconciliation'].iloc[0].reported_value==60

def test_same_date_snapshot_conflict_visible():
    """Same-grain same-date competing snapshots remain an explicit conflict."""
    out=build_cashflow(pd.DataFrame([evt()]),measurements=pd.DataFrame([measure('M1',80),measure('M2',60)]),as_of='2026-09-24')
    assert out['reconciliation'].iloc[0].status=='CONFLICT'
    assert 'CONFLICTING_SNAPSHOT' in set(out['issues'].code)

def test_historical_snapshot_not_compared_to_today_ledger():
    """A yesterday balance must not be treated as a same-date reconciliation with today ledger."""
    out=build_cashflow(pd.DataFrame([evt()]),measurements=pd.DataFrame([measure('M1',100,'2026-09-23')]),as_of='2026-09-24')
    assert out['reconciliation'].iloc[0].status=='DATE_MISMATCH' and pd.isna(out['reconciliation'].iloc[0].variance)

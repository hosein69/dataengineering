"""Requirements 11–20, 28–33. Oracles are explicit fixture arithmetic, never baseline totals."""
import itertools
from decimal import Decimal
import pandas as pd
import pytest
from gsi.finance.equivalents import commitment_equivalents,summarize_fx_purchases,summarize_credit_equivalents
from gsi.report.financial_summary import commitment_equivalent_summary,commitment_display,commitment_status_summary

def purchase(**kw):
    return dict(KEY_REG='12345678',FX_CURRENCY='USD',FX_AMOUNT=100,FX_EUR_VALUE=90,FX_RIAL_VALUE=1000,**kw)

def equivalent(rows=None,alloc=None,**kw):
    args=dict(reg='12345678',currency='USD',balance=50,fx_rows=pd.DataFrame(rows or []),allocation_rows=pd.DataFrame(alloc or []));args.update(kw)
    return commitment_equivalents(**args)

@pytest.mark.parametrize('currency',['USD','EUR','CNY'])
def test_single_currency_native_totals(currency):
    """Native amounts add only inside a single known currency; equivalents remain independent."""
    rows=[dict(FX_CURRENCY=currency,FX_AMOUNT=a,FX_EUR_VALUE=e) for a,e in [(100,90),(200,180)]]
    r=summarize_fx_purchases(pd.DataFrame(rows))
    assert r.single_currency==currency and r.single_native_amount==300 and r.source_eur_total==270

def test_multi_currency_has_no_dimensionless_native_total():
    """EUR100 + USD200 is not native300; source EUR equivalents may add to EUR280."""
    r=summarize_fx_purchases(pd.DataFrame([dict(FX_CURRENCY='EUR',FX_AMOUNT=100,FX_EUR_VALUE=100),dict(FX_CURRENCY='USD',FX_AMOUNT=200,FX_EUR_VALUE=180)]))
    assert r.single_native_amount is None and r.single_currency=='' and r.source_eur_total==280

@pytest.mark.parametrize('state',['PLANNED'])
def test_planned_purchase_not_actual_purchase(state):
    """A declared planned purchase supplies neither actual totals nor actual purchase rate evidence."""
    rows=[purchase(FX_PURCHASE_STATE=state)]
    r=summarize_fx_purchases(pd.DataFrame(rows));e=equivalent(rows)
    assert r.source_eur_total is None and r.single_native_amount is None
    assert e['FX_NTSW_BALANCE_EUR_EQ'] is None and e['FX_NTSW_BALANCE_RIAL_EQ'] is None

@pytest.mark.parametrize('field,value',[('KEY_REG','87654321'),('FX_CURRENCY','CNY'),('KEY_REG',None),('FX_CURRENCY','')])
def test_foreign_or_missing_identity_never_supplies_rate(field,value):
    """Rates are scoped to the same REG and native currency, including missing identity rejection."""
    row=purchase();row[field]=value;r=equivalent([row])
    assert r['FX_NTSW_BALANCE_EUR_EQ'] is None and r['FX_NTSW_BALANCE_RIAL_EQ'] is None

@pytest.mark.parametrize('field',['KEY_REG','FX_CURRENCY'])
def test_absent_identity_column_never_supplies_rate(field):
    """An absent identity column is not a wildcard for same-case FX authority."""
    row=purchase();del row[field];r=equivalent([row])
    assert r['FX_NTSW_BALANCE_EUR_EQ'] is None and r['FX_NTSW_BALANCE_RIAL_EQ'] is None

def test_source_reported_equivalent_precedes_conflicting_rate():
    """Source IRR1000/USD100 takes priority over FX_RATE999 for the same transaction."""
    r=equivalent([purchase(FX_RATE=999)])
    assert r['FX_NTSW_BALANCE_RIAL_EQ']==500
    assert 'SOURCE_REPORTED' in r['FX_NTSW_RIAL_EQ_BASIS']

def test_weighted_conversion_has_independent_decimal_oracle():
    """Same-case partial purchases USD100/EUR80 and USD300/EUR270 imply EUR87.5 for USD100."""
    rows=[dict(KEY_REG='12345678',FX_CURRENCY='USD',FX_AMOUNT=a,FX_EUR_VALUE=e) for a,e in [(100,80),(300,270)]]
    r=equivalent(rows,balance=100)
    expected=Decimal('100')*(Decimal('80')+Decimal('270'))/(Decimal('100')+Decimal('300'))
    assert Decimal(str(r['FX_NTSW_BALANCE_EUR_EQ']))==expected

@pytest.mark.parametrize('currency,field',[('EUR','FX_NTSW_BALANCE_EUR_EQ'),('IRR','FX_NTSW_BALANCE_RIAL_EQ')])
def test_zero_is_valid_but_null_is_unknown(currency,field):
    """Authoritative zero remains zero; absent native balance never becomes zero equivalent."""
    assert equivalent(currency=currency,balance=0)[field]==0
    assert equivalent(currency=currency,balance=None)[field] is None

@pytest.mark.parametrize('value',[float('inf'),float('-inf'),'Infinity'])
def test_nonfinite_native_balance_cannot_enter_kpi(value):
    """Nonfinite values are invalid financial facts even for identity EUR conversion."""
    assert equivalent(currency='EUR',balance=value)['FX_NTSW_BALANCE_EUR_EQ'] is None

@pytest.mark.parametrize('column',['FX_EUR_VALUE','FX_RIAL_VALUE'])
def test_nonfinite_source_equivalent_retains_coverage_gap(column):
    """One finite and one infinite equivalent yields only the finite total with 50% row coverage."""
    a=purchase();b=purchase();b[column]=float('inf');r=summarize_fx_purchases(pd.DataFrame([a,b]))
    total,cov=('source_eur_total','eur_coverage_pct') if column=='FX_EUR_VALUE' else ('source_rial_total','rial_coverage_pct')
    assert getattr(r,total)==a[column] and getattr(r,cov)==50

@pytest.mark.parametrize('state',['OPEN','REJECTED','AMBIGUOUS'])
def test_nonapproved_allocation_cannot_supply_valuation_rate(state):
    """An explicitly nonallocated request cannot be promoted to approved allocation rate evidence."""
    r=equivalent(alloc=[dict(KEY_REG='12345678',NTSW_REQ_CURRENCY='USD',NTSW_FX_RATE_NUMERIC=10,NTSW_REQUEST_STATE=state)])
    assert r['FX_NTSW_BALANCE_RIAL_EQ'] is None

@pytest.mark.parametrize('dt',['2026-01-01',''])
def test_allocation_rate_conflict_is_order_invariant(dt):
    """Conflicting same-date/undated rates must be withheld and flagged, never resolved by input ordering."""
    rows=[dict(KEY_REG='12345678',NTSW_REQ_CURRENCY='USD',NTSW_FX_RATE_NUMERIC=r,NTSW_REQ_DATE=dt) for r in [10,20]]
    for perm in itertools.permutations(rows):
        r=equivalent(alloc=list(perm))
        assert r['FX_NTSW_BALANCE_RIAL_EQ'] is None and 'CONFLICT' in r['FX_NTSW_RIAL_EQ_BASIS']

def test_credit_duplicate_snapshot_does_not_double_amount():
    """Two identical snapshots of LC1 remain one logical credit and EUR100."""
    f=pd.DataFrame([dict(CRD_LC_NO='LC1',CRD_EUR_AMOUNT=100,CRD_RIAL_AMOUNT=1000)]*2)
    r=summarize_credit_equivalents(f)
    assert r.source_eur_total==100 and r.logical_credit_count==1

def test_multiple_credit_events_remain_multiple():
    """Two distinct LC identifiers with equal values are two credits, EUR200 total."""
    r=summarize_credit_equivalents(pd.DataFrame([dict(CRD_LC_NO=lc,CRD_EUR_AMOUNT=100) for lc in ['LC1','LC2']]))
    assert r.logical_credit_count==2 and r.source_eur_total==200

def test_unversioned_lc_amendment_cannot_be_summed_or_last_selected():
    """Conflicting LC snapshots without amendment version/date cannot be resolved by row order."""
    for amounts in [[100,120],[120,100]]:
        r=summarize_credit_equivalents(pd.DataFrame([dict(CRD_LC_NO='LC1',CRD_EUR_AMOUNT=x) for x in amounts]))
        assert r.source_eur_total is None and 'CONFLICT' in r.status

def test_credit_partial_equivalent_is_disclosed():
    """One of two LC EUR equivalents missing must yield a partial status and 50% coverage."""
    r=summarize_credit_equivalents(pd.DataFrame([dict(CRD_LC_NO='LC1',CRD_EUR_AMOUNT=100),dict(CRD_LC_NO='LC2',CRD_EUR_AMOUNT=None)]))
    assert r.source_eur_total==100
    assert 'PARTIAL' in r.status and getattr(r,'eur_coverage_pct',None)==50

@pytest.mark.parametrize('key',[None,float('nan'),pd.NA,''])
def test_unidentified_equivalent_is_excluded_and_accounted(key):
    """Missing REG is excluded from financial total with explicit missing-key population accounting."""
    r=commitment_equivalent_summary(pd.DataFrame([dict(KEY_REG=key,FX_NTSW_BALANCE_EUR_EQ=100)]))
    assert r['eur'] is None and r.get('missing_key_rows')==1

def test_coverage_requires_joint_intersection():
    """EUR-only A and IRR-only B means zero jointly covered REG, not min(1,1)."""
    r=commitment_equivalent_summary(pd.DataFrame([dict(KEY_REG='A',FX_NTSW_BALANCE_EUR_EQ=10),dict(KEY_REG='B',FX_NTSW_BALANCE_RIAL_EQ=100)]))
    assert r['covered']==0 and r['eur_covered']==r['irr_covered']==1

def test_unknown_zero_placeholder_not_covered():
    """BALANCE_IS_UNKNOWN dominates a legacy zero placeholder; known zero remains included."""
    r=commitment_equivalent_summary(pd.DataFrame([dict(KEY_REG=k,FX_NTSW_BALANCE_EUR_EQ=0,BALANCE_IS_UNKNOWN=u) for k,u in [('A',True),('B',False)]]))
    assert r['total']==2 and r['eur_covered']==1 and r.get('unknown')==1

def test_same_reg_multi_currency_needs_proven_grain():
    """Equal EUR equivalents of two native currency rows cannot be silently collapsed at REG grain."""
    r=commitment_equivalent_summary(pd.DataFrame([dict(KEY_REG='A',FX_NTSW_CURRENCY=c,FX_NTSW_BALANCE_EUR_EQ=100) for c in ['EUR','USD']]))
    assert r['eur'] is None and r.get('conflicted')==1

@pytest.mark.parametrize('fanout',[1,2,17,101])
def test_reg_commitment_fanout_never_multiplies_native_total(fanout):
    """Repeating a REG balance across BL/material rows leaves EUR100, regardless of row multiplicity."""
    f=pd.DataFrame([dict(KEY_REG='A',NTSW_CURRENCY='EUR',NTSW_BALANCE=100)]*fanout)
    assert commitment_display(f)=='100.00 EUR'
    result,diag=commitment_status_summary(f)
    assert result.amount.sum()==100 and sum(diag.values())==0

def test_conflict_population_stays_in_denominator():
    """A conflicting REG is excluded from total but retained in coverage population."""
    f=pd.DataFrame([dict(KEY_REG=k,FX_NTSW_BALANCE_EUR_EQ=a) for k,a in [('A',10),('A',20),('B',30)]])
    r=commitment_equivalent_summary(f)
    assert r['total']==2 and r['conflicted']==1 and r['eur']==30 and r['status']=='PARTIAL'

@pytest.mark.parametrize('balance',[None,'',float('nan')])
def test_legacy_commitment_engine_preserves_unknown_balance(balance):
    """Legacy commitment output must not silently turn an unknown input balance into numerical zero."""
    from datetime import date
    from gsi.engines.commitment import CommitmentEngine
    r=CommitmentEngine().evaluate({'BALANCE':balance},date(2026,9,24))
    assert pd.isna(r.outstanding) or bool(getattr(r,'balance_is_unknown',False)),r.as_dict()

def test_legacy_known_zero_stays_zero():
    """A source-reported zero is valid, distinct from the legacy unknown case."""
    from datetime import date
    from gsi.engines.commitment import CommitmentEngine
    assert CommitmentEngine().evaluate({'BALANCE':0},date(2026,9,24)).outstanding==0

def test_planned_fx_cannot_supply_actual_commitment_valuation_rate():
    """An explicitly planned transaction cannot serve as completed-purchase exchange-rate authority."""
    r=equivalent([purchase(FX_PURCHASE_STATE='PLANNED')])
    assert r['FX_NTSW_BALANCE_EUR_EQ'] is None and r['FX_NTSW_BALANCE_RIAL_EQ'] is None,r

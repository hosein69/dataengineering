"""Exact-decimal evidence ledger. No FIFO inference, implicit FX or legal deadlines."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import pandas as pd
from ..core.jalali import CalendarEngine
from ..core.numeric_parse import parse_decimal

ZERO = Decimal('0')
CASH = {'FUNDING', 'PAYMENT', 'REFUND', 'FEE', 'FX_SELL', 'FX_BUY', 'TRANSFER', 'OPENING', 'REVERSAL'}
NONCASH = {'FILE', 'REGISTRATION', 'QUEUE', 'ALLOCATION', 'ALLOCATION_CANCEL',
           'ALLOCATION_USE', 'QUOTA', 'QUOTA_USE', 'COMMITMENT', 'SETTLEMENT',
           'COMMITMENT_RETURN', 'SHIPMENT', 'CUSTOMS', 'CLEARANCE', 'WAREHOUSE', 'BANK_DOCS'}
EVENT_COLUMNS = ['event_id','source_event_id','case_id','order_id','bl_id','kind','date','recorded_at',
                 'amount','currency','from_account','to_account','document','source','status','group_id',
                 'reversal_of','due_date','rule_id','note','rate_regime','rate_side','rate_market','settlement_method']
LINK_COLUMNS = ['link_id','relation_type','from_event','to_event','from_amount','to_amount','document',
                'authorization','rate_id','conversion_basis']
RATE_COLUMNS = ['rate_id','date','value_date','published_at','base','quote','rate','purpose','side','market',
                'source','source_url','source_document','source_hash','approved','approved_by','approved_at',
                'max_age_days','regime']
MEASUREMENT_COLUMNS = ['measurement_id','case_id','order_id','bl_id','metric','observed_at','amount','currency',
                       'source','source_record_id','document','status','rate_regime','note']
RULE_COLUMNS = ['rule_id','kind','jurisdiction','authority','circular_no','publication_date','effective_from',
                'effective_to','source','source_url','source_hash','approved','approved_by','approved_at','note']
STAGES = ['FILE','REGISTRATION','QUEUE','ALLOCATION','FX_BUY','PAYMENT','SHIPMENT',
          'CUSTOMS','CLEARANCE','WAREHOUSE','BANK_DOCS','SETTLEMENT']


def text(v):
    if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
        return ''
    return str(v).strip()


def number(v):
    # Strict: «1,5» is ambiguous (1.5 or 15) and is rejected instead of guessed.
    return parse_decimal(v, strict=True)


def day(v):
    return CalendarEngine.parse(v) if text(v) else None


def frame(rows, columns=None):
    return pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame(rows)


def records(df):
    return [] if df is None else df.to_dict('records')


class PreparedRates:
    """Rate register parsed once and indexed by (base, quote, purpose, regime).

    ``select_rate`` used to convert the whole rate DataFrame to dicts and re-parse
    every date/number on *each* call; it is called once per cash event, so a real
    DWH run was O(events × rates) DataFrame conversions.  Eligibility rules are
    unchanged; only static per-row checks are hoisted out of the per-call loop.
    """
    __slots__ = ('groups',)

    def __init__(self, rates):
        self.groups = defaultdict(list)
        for r in records(rates):
            # A blank value_date falls back to date. Before V29.9 a NaN value_date
            # (column present, cell empty) was truthy and silently disqualified
            # an otherwise valid rate.
            dt = day(text(r.get('value_date')) or text(r.get('date')))
            value, age = number(r.get('rate')), number(r.get('max_age_days'))
            if (text(r.get('approved')).lower() != 'true' or not text(r.get('source')) or not dt
                    or value is None or not value > 0 or age is None or not age >= 0):
                continue
            key = (text(r.get('base')).upper(), text(r.get('quote')).upper(),
                   text(r.get('purpose')), text(r.get('regime')))
            self.groups[key].append((dt, value, age, text(r.get('side')).upper(),
                                     text(r.get('market')), text(r.get('source'))))


def select_rate(rates, currency, target, when, purpose='accounting', regime='', side='', market=''):
    if currency == target:
        return Decimal(1), when, 'IDENTITY'
    book = rates if isinstance(rates, PreparedRates) else PreparedRates(rates)
    candidates = []
    for dt, value, age, r_side, r_market, source in book.groups.get((currency, target, purpose, regime), ()):
        if ((not side or r_side == side.upper()) and (not market or r_market == market)
                and dt <= when and (when-dt).days <= age):
            candidates.append((dt, value, source))
    if not candidates:
        return None, None, 'MISSING_RATE'
    latest = max(r[0] for r in candidates)
    best = [r for r in candidates if r[0] == latest]
    if len({r[1] for r in best}) != 1:
        return None, latest, 'CONFLICTING_RATE'
    return best[0][1], latest, ' | '.join(sorted({r[2] for r in best}))


def build_cashflow(events, links=None, rates=None, *, as_of=None, reporting_currency='IRR', rules=None, measurements=None):
    """All events are incremental, not cumulative snapshots; case_id is legal REG/file ID.

    A bank-journal event is posted only with status POSTED + source + document + stable ID.
    SOURCE_FACT is reserved for native DWH evidence: it may contribute to amount/stage summaries,
    but never creates account movements unless explicit accounts are present. Evidence presence is
    validation, not independent authentication. Incomplete opening => unknown balance.
    """
    if as_of is not None and day(as_of) is None:raise ValueError('تاریخ گزارش معتبر نیست')
    as_of = day(as_of) or date.today()
    reporting_currency=text(reporting_currency).upper()
    rate_book=PreparedRates(rates)
    rate_memo={}
    def rate_for(currency,target,when,purpose='accounting',regime='',side='',market=''):
        k=(currency,target,when,purpose,regime,side,market)
        if k not in rate_memo:
            rate_memo[k]=select_rate(rate_book,currency,target,when,purpose,regime,side,market)
        return rate_memo[k]
    issues, accepted, observations = [], [], []
    def issue(code, ref, detail, severity='WARNING'):
        issues.append(dict(code=code, reference=ref, severity=severity, detail=detail))
    grouped = defaultdict(list)
    for raw in records(events):
        r = {k:text(raw.get(k)) for k in EVENT_COLUMNS}
        r['currency']=r['currency'].upper()
        grouped[r['event_id']].append(r)
    for eid, rows in grouped.items():
        if not eid:
            for r in rows:
                observations.append(r); issue('MISSING_ID', '', 'شناسه پایدار تراکنش موجود نیست')
            continue
        unique = {tuple(r.items()) for r in rows}
        if len(unique) > 1:
            observations.extend(rows); issue('CONFLICTING_ID', eid, 'مقادیر متناقض؛ تمام نسخه‌ها از محاسبه خارج شدند', 'ERROR'); continue
        r = rows[0]
        if len(rows) > 1: issue('DUPLICATE_REMOVED', eid, f'{len(rows)-1} تکرار دقیق حذف شد', 'INFO')
        dt, amt = day(r['date']), number(r['amount'])
        reason = None
        if r['kind'] not in CASH | NONCASH: reason = 'UNKNOWN_EVENT'
        elif not r['case_id']: reason = 'MISSING_CASE'
        elif not dt: reason = 'MISSING_DATE'
        elif dt > as_of: reason = 'FUTURE_EVENT'
        elif r['status'] not in {'POSTED','SOURCE_FACT'} or not r['document'] or not r['source']: reason = 'UNVERIFIED_EVIDENCE'
        elif r['currency'] in {'IRT','TOMAN','تومان','RIAL','ریال'}: reason = 'AMBIGUOUS_CURRENCY_UNIT'
        elif r['currency'] and (len(r['currency']) != 3 or not r['currency'].isascii() or not r['currency'].isalpha()): reason = 'INVALID_CURRENCY_CODE'
        elif r['kind'] not in {'FILE','REGISTRATION','QUEUE','WAREHOUSE','BANK_DOCS','CLEARANCE'} and (amt is None or amt < 0 or not r['currency']): reason = 'MISSING_AMOUNT_CURRENCY'
        elif r['kind'] in CASH and r['status']=='POSTED' and (not (r['from_account'].startswith('OWN:') or r['to_account'].startswith('OWN:')) or not r['from_account'] or not r['to_account'] or r['from_account']==r['to_account']): reason = 'MISSING_ACCOUNTS'
        elif r['kind']=='OPENING' and r['status']=='POSTED' and (r['from_account'].startswith('OWN:') or not r['to_account'].startswith('OWN:')): reason='INVALID_OPENING'
        elif r['kind'] in {'PAYMENT','FEE','FX_SELL'} and r['status']=='POSTED' and (not r['from_account'].startswith('OWN:') or r['to_account'].startswith('OWN:')): reason='INVALID_CASH_DIRECTION'
        elif r['kind'] in {'FUNDING','REFUND','FX_BUY'} and r['status']=='POSTED' and (r['from_account'].startswith('OWN:') or not r['to_account'].startswith('OWN:')): reason='INVALID_CASH_DIRECTION'
        elif r['kind']=='TRANSFER' and r['status']=='POSTED' and not (r['from_account'].startswith('OWN:') and r['to_account'].startswith('OWN:')): reason='INVALID_TRANSFER'
        elif r['kind']=='REVERSAL' and not r['reversal_of']: reason='MISSING_REVERSAL_TARGET'
        if reason:
            observations.append(r); issue(reason, eid, 'رویداد قابل احتساب نیست؛ اصل داده حفظ شد'); continue
        r['amount'], r['date'] = amt, dt.isoformat()
        if r['status']=='SOURCE_FACT' and r['kind'] in CASH and not (r['from_account'] or r['to_account']):
            issue('ACCOUNT_DETAIL_GAP',eid,'مبلغ منبع در جریان وجوه لحاظ شد، اما گردش حساب ساخته نشد چون حساب بانکی در شاهد منبع وجود ندارد','INFO')
        accepted.append(r)
    # Source-native IDs detect replay across imports. Conflicting replays are quarantined.
    source_ids=defaultdict(list)
    for r in accepted:
        if r['source_event_id']:source_ids[(r['source'],r['source_event_id'])].append(r)
    rejected=set()
    for key,rows in source_ids.items():
        if len(rows)>1:
            fingerprints={tuple((k,v) for k,v in r.items() if k!='event_id') for r in rows}
            if len(fingerprints)>1:
                rejected.update(r['event_id'] for r in rows)
                issue('CONFLICTING_SOURCE_EVENT_ID',' / '.join(key),'شناسه بومی منبع با دو محتوای متفاوت تکرار شده است','ERROR')
            else:
                rejected.update(r['event_id'] for r in rows[1:])
                issue('SOURCE_REPLAY_REMOVED',' / '.join(key),f'{len(rows)-1} بازپخش یکسان منبع حذف شد','INFO')
    if rejected:
        observations.extend(r for r in accepted if r['event_id'] in rejected)
        accepted=[r for r in accepted if r['event_id'] not in rejected]
    # Reversal is a new immutable event, never an overwrite of history.
    by_id={r['event_id']:r for r in accepted}
    reversal_totals=defaultdict(lambda:ZERO);bad_reversals=set()
    for r in accepted:
        if r['kind']!='REVERSAL':continue
        original=by_id.get(r['reversal_of'])
        reversal_totals[r['reversal_of']]+=r['amount'] or ZERO
        ok=(original and original['kind'] in CASH-{'OPENING','REVERSAL'} and original['case_id']==r['case_id']
            and original['currency']==r['currency'] and original['date']<=r['date']
            and original['from_account']==r['to_account'] and original['to_account']==r['from_account'])
        if not ok:
            bad_reversals.add(r['event_id']);issue('INVALID_REVERSAL',r['event_id'],'ابطال باید رویداد نقدی موجود را با همان پرونده/ارز و حساب‌های معکوس ارجاع دهد','ERROR')
    for target,total in reversal_totals.items():
        if target in by_id and total>by_id[target]['amount']:
            bad_reversals.update(r['event_id'] for r in accepted if r['reversal_of']==target)
            issue('OVER_REVERSAL',target,'جمع ابطال‌ها بیش از مبلغ رویداد اصلی است','ERROR')
    if bad_reversals:
        observations.extend(r for r in accepted if r['event_id'] in bad_reversals)
        accepted=[r for r in accepted if r['event_id'] not in bad_reversals]
    # An FX conversion requires exactly two documented legs on same case/date/group.
    fx = defaultdict(list)
    for r in accepted:
        if r['kind'] in {'FX_SELL','FX_BUY'}: fx[r['group_id']].append(r)
    bad_fx = set()
    for gid, rs in fx.items():
        ok = (gid and len(rs)==2 and {r['kind'] for r in rs}=={'FX_SELL','FX_BUY'}
              and len({r['case_id'] for r in rs})==1 and len({r['date'] for r in rs})==1
              and len({r['currency'] for r in rs})==2 and all(r['amount'] > 0 for r in rs))
        if ok:
            sell=next(r for r in rs if r['kind']=='FX_SELL');buy=next(r for r in rs if r['kind']=='FX_BUY')
            ok=sell['to_account']==buy['from_account']
        if not ok:
            bad_fx.update(r['event_id'] for r in rs)
            issue('INCOMPLETE_FX_PAIR', gid, 'تبدیل ارز دو پای معتبر هم‌تاریخ و هم‌پرونده لازم دارد', 'ERROR')
    # A documented debit/credit remains a cash fact even if the other FX leg is missing.
    # Only the conversion calculation and conversion links require a complete pair.
    by_id = {r['event_id']:r for r in accepted}
    reversed_ids={r['reversal_of'] for r in accepted if r['kind']=='REVERSAL'}
    # Validate links independently; they attribute money, never create a new cash movement.
    proposed, valid_links = [], []
    link_groups = defaultdict(list)
    for raw in records(links):
        r = {k:text(raw.get(k)) for k in LINK_COLUMNS};link_groups[r['link_id']].append(r)
    for lid, rows in link_groups.items():
        if not lid or len({tuple(r.items()) for r in rows}) > 1:
            issue('INVALID_LINK_ID', lid, 'شناسه ارتباط خالی یا متناقض است'); continue
        r=rows[0];a,b=by_id.get(r['from_event']),by_id.get(r['to_event'])
        if r['from_event'] in reversed_ids or r['to_event'] in reversed_ids:
            issue('REVERSED_EVENT_LINK',lid,'ارتباط سند دارای ابطال باید پس از تطبیق مجدد بازسازی شود');continue
        x,y=number(r['from_amount']),number(r['to_amount'])
        if not a or not b or not r['document'] or not x or not y or x<=0 or y<=0:
            issue('INVALID_LINK',lid,'رویداد، مبلغ مثبت یا سند ارتباط موجود نیست');continue
        allowed = ((a['kind'] in {'FUNDING','REFUND','FX_BUY','OPENING','TRANSFER'} and b['kind'] in {'PAYMENT','FEE','FX_SELL','TRANSFER'})
                   or (a['kind']=='PAYMENT' and b['kind'] in {'SHIPMENT','CUSTOMS','SETTLEMENT'})
                   or (a['kind']=='COMMITMENT' and b['kind'] in {'SETTLEMENT','COMMITMENT_RETURN'})
                   or (a['kind']=='FX_SELL' and b['kind']=='FX_BUY'))
        if not allowed or a['event_id']==b['event_id']:
            issue('INVALID_LINK_KIND',lid,'نوع مبدأ و مقصد ارتباط مالی سازگار نیست');continue
        if a['kind'] in {'FUNDING','REFUND','FX_BUY','OPENING','TRANSFER'} and b['kind'] in CASH and (a['currency']!=b['currency'] or a['to_account']!=b['from_account']):
            issue('ACCOUNT_PATH_GAP',lid,'برای تغییر حساب/ارز باید انتقال یا تبدیل مستقل ثبت شود');continue
        if a['kind']=='FX_SELL' and (a['event_id'] in bad_fx or b['event_id'] in bad_fx or a['group_id']!=b['group_id'] or a['to_account']!=b['from_account']):
            issue('FX_LINK_GROUP_MISMATCH',lid,'دو پای تبدیل هم‌گروه نیستند');continue
        if a['case_id'] != b['case_id'] and not r['authorization']:
            issue('UNAUTHORIZED_REALLOCATION',lid,'جابجایی میان پرونده‌ها بدون مرجع مجوز');continue
        if a['kind']=='COMMITMENT':
            expected='OBLIGATION_SETTLEMENT' if b['kind']=='SETTLEMENT' else 'OBLIGATION_RETURN'
            if r['relation_type']!=expected:
                issue('INVALID_OBLIGATION_LINK',lid,'رابطه تعهد باید نوع صریح ایفای تعهد یا عودت تعهد داشته باشد');continue
            if a['currency']!=b['currency'] and (not r['authorization'] or not r['conversion_basis']):
                issue('UNSUPPORTED_CROSS_CURRENCY_SETTLEMENT',lid,'ایفای تعهد با ارز متفاوت، مجوز و مبنای تبدیل مستند می‌خواهد','ERROR');continue
        if a['date'] > b['date']:
            issue('REVERSED_LINK_DATE',lid,'مصرف پیش از رویداد تأمین است');continue
        if a['currency']==b['currency'] and x!=y:
            issue('LINK_AMOUNT_MISMATCH',lid,'مبالغ ارتباط هم‌ارز برابر نیستند');continue
        r.update(from_amount=x,to_amount=y,from_currency=a['currency'],to_currency=b['currency'],
                 source_case=a['case_id'],target_case=b['case_id'],target_kind=b['kind'],
                 order_id=b['order_id'],bl_id=b['bl_id'],implied_rate=y/x)
        proposed.append(r)
    # A payment may be matched separately to shipment, customs and settlement evidence.
    outtot, intot = defaultdict(lambda:ZERO), defaultdict(lambda:ZERO)
    for r in proposed:
        outtot[(r['from_event'],r['target_kind'])]+=r['from_amount']
        domain='OBLIGATION' if by_id[r['from_event']]['kind']=='COMMITMENT' else 'MONEY'
        intot[(r['to_event'],domain)]+=r['to_amount']
    used_all, used_cash = defaultdict(lambda:ZERO), defaultdict(lambda:ZERO)
    for z in proposed:
        used_all[z['from_event']]+=z['from_amount']
        if by_id[z['to_event']]['kind'] in CASH: used_cash[z['from_event']]+=z['from_amount']
    for r in proposed:
        a,b=by_id[r['from_event']],by_id[r['to_event']]
        # Funding capacity covers all cash consumers; one obligation covers settlement and return together.
        if a['kind']=='PAYMENT':used=outtot[(a['event_id'],r['target_kind'])]
        elif a['kind']=='COMMITMENT':used=used_all[a['event_id']]
        else:used=used_cash[a['event_id']]
        domain='OBLIGATION' if a['kind']=='COMMITMENT' else 'MONEY'
        if a['amount'] is None or b['amount'] is None or used>a['amount'] or intot[(b['event_id'],domain)]>b['amount']:
            issue('OVERALLOCATED_LINK',r['link_id'],'تخصیص بیش از ظرفیت؛ ارتباط از جمع حذف شد','ERROR')
        else: valid_links.append(r)
    conversions=[]
    for gid,rs in fx.items():
        if any(r['event_id'] in bad_fx for r in rs):continue
        sold=next(r for r in rs if r['kind']=='FX_SELL');bought=next(r for r in rs if r['kind']=='FX_BUY')
        rr,rd,src=rate_for(sold['currency'],bought['currency'],day(sold['date']),regime=sold['rate_regime'],side=sold['rate_side'],market=sold['rate_market'])
        conversions.append(dict(case_id=sold['case_id'],group_id=gid,date=sold['date'],from_event=sold['event_id'],to_event=bought['event_id'],from_currency=sold['currency'],to_currency=bought['currency'],from_amount=sold['amount'],to_amount=bought['amount'],implied_rate=bought['amount']/sold['amount'],reference_rate=rr,rate_date=rd,rate_source=src,reference_difference=bought['amount']-sold['amount']*rr if rr is not None else None))
    # Account movement ledger: opening is explicit, balances are not guessed.
    accounts=defaultdict(lambda:dict(opening=[],inflow=ZERO,outflow=ZERO))
    movements=[]; valuations=[]
    for r in accepted:
        if r['kind'] not in CASH:continue
        for account,sign in [(r['from_account'],-1),(r['to_account'],1)]:
            if not account.startswith('OWN:'):continue
            key=(r['case_id'],account,r['currency']);a=accounts[key]
            if r['kind']=='OPENING':
                if sign>0:a['opening'].append((r['date'],r['amount']))
                else: issue('INVALID_OPENING',r['event_id'],'مانده ابتدا باید به حساب OWN وارد شود')
            else:a['inflow' if sign>0 else 'outflow']+=r['amount']
            movements.append(dict(case_id=r['case_id'],event_id=r['event_id'],date=r['date'],kind=r['kind'],account=account,currency=r['currency'],signed_amount=r['amount']*sign,document=r['document']))
        rate,rd,src=rate_for(r['currency'],reporting_currency,day(r['date']),regime=r['rate_regime'],side=r['rate_side'],market=r['rate_market'])
        valuations.append(dict(event_id=r['event_id'],case_id=r['case_id'],date=r['date'],kind=r['kind'],amount=r['amount'],currency=r['currency'],reporting_currency=reporting_currency,rate=rate,rate_date=rd,rate_source=src,value=r['amount']*rate if rate is not None else None))
        if rate is None:issue('VALUATION_GAP',r['event_id'],src)
    for r in accepted:
        if r['kind'] not in {'CUSTOMS','SETTLEMENT','COMMITMENT_RETURN','COMMITMENT'} or r['amount'] is None:continue
        purpose='customs' if r['kind']=='CUSTOMS' else 'settlement' if r['kind'] in {'SETTLEMENT','COMMITMENT_RETURN'} else 'accounting'
        rate,rd,src=rate_for(r['currency'],reporting_currency,day(r['date']),purpose,regime=r['rate_regime'],side=r['rate_side'],market=r['rate_market'])
        valuations.append(dict(event_id=r['event_id'],case_id=r['case_id'],date=r['date'],kind=r['kind'],amount=r['amount'],currency=r['currency'],reporting_currency=reporting_currency,rate=rate,rate_date=rd,rate_source=src,value=r['amount']*rate if rate is not None else None))
        if rate is None:issue('VALUATION_GAP',r['event_id'],purpose+' / '+src)
    balances=[]
    movements_by_account=defaultdict(list)
    for m in movements:
        if m['kind']!='OPENING':movements_by_account[(m['case_id'],m['account'],m['currency'])].append(m)
    for (case,account,cur),a in accounts.items():
        movements_for=movements_by_account.get((case,account,cur),[])
        opening_ok=len(a['opening'])==1 and all(m['date']>=a['opening'][0][0] for m in movements_for)
        opening=a['opening'][0][1] if opening_ok else None
        closing=opening+a['inflow']-a['outflow'] if opening is not None else None
        rate,rd,src=rate_for(cur,reporting_currency,as_of)
        if opening is None:issue('OPENING_GAP',case+' / '+account,'مانده اول دوره یکتا و مقدم بر حرکات نیست؛ فقط خالص حرکت معلوم است')
        if closing is not None and closing<0:issue('NEGATIVE_BALANCE',case+' / '+account,'مصارف بیش از منابع ثبت‌شده','ERROR')
        balances.append(dict(case_id=case,account=account,currency=cur,opening=opening,inflow=a['inflow'],outflow=a['outflow'],net_movement=a['inflow']-a['outflow'],closing=closing,closing_rate=rate,rate_date=rd,rate_source=src,closing_value=closing*rate if closing is not None and rate is not None else None))
    # Separate commitments, quota, allocation, customs and settlement currencies.
    summaries=[]
    groups=defaultdict(list)
    for r in accepted:
        if r['currency']:groups[(r['case_id'],r['currency'])].append(r)
    # One pass each, in the original iteration order, instead of rescanning every
    # accepted event / valid link for every (case, currency) group.
    reversed_by=defaultdict(lambda:ZERO)
    for r in accepted:
        if r['kind']=='REVERSAL':
            reversed_by[(r['case_id'],r['currency'],by_id.get(r['reversal_of'],{}).get('kind'))]+=r['amount']
    link_from=defaultdict(lambda:ZERO); link_to=defaultdict(lambda:ZERO)
    link_from_commit=defaultdict(lambda:ZERO); link_to_commit=defaultdict(lambda:ZERO)
    link_doc=defaultdict(lambda:ZERO)
    for r in valid_links:
        from_commit=by_id[r['from_event']]['kind']=='COMMITMENT'
        link_from[(r['source_case'],r['from_currency'],r['target_kind'])]+=r['from_amount']
        link_to[(r['target_case'],r['to_currency'],r['target_kind'])]+=r['to_amount']
        if from_commit:
            link_from_commit[(r['source_case'],r['from_currency'],r['target_kind'])]+=r['from_amount']
            link_to_commit[(r['target_case'],r['to_currency'],r['target_kind'])]+=r['to_amount']
        if r['target_kind']=='SHIPMENT':
            link_doc[(r['target_case'],r['bl_id'],r['order_id'],r['to_currency'])]+=r['to_amount']
    for (case,cur),rs in groups.items():
        def total(kind):
            vals=[r['amount'] for r in rs if r['kind']==kind]
            return sum(vals,ZERO) if vals and all(v is not None for v in vals) else None
        def net_total(kind):
            gross=total(kind)
            if gross is None:return None
            reversed_amount=reversed_by.get((case,cur,kind),ZERO)
            return gross-reversed_amount
        def remaining(base,plus,minus):
            v=total(base)
            return None if v is None else v+sum((total(k) or ZERO for k in plus),ZERO)-sum((total(k) or ZERO for k in minus),ZERO)
        commitment=total('COMMITMENT')
        linked_settled=link_from_commit.get((case,cur,'SETTLEMENT'),ZERO)
        linked_return=link_from_commit.get((case,cur,'COMMITMENT_RETURN'),ZERO)
        bal=None if commitment is None else commitment-linked_settled-linked_return
        alloc=remaining('ALLOCATION',[],['ALLOCATION_CANCEL','ALLOCATION_USE'])
        quota=remaining('QUOTA',[],['QUOTA_USE'])
        paid=net_total('PAYMENT')
        traced=link_to.get((case,cur,'PAYMENT'),ZERO)
        matched=link_from.get((case,cur,'SHIPMENT'),ZERO)
        raw_settlement=total('SETTLEMENT')
        raw_return=total('COMMITMENT_RETURN')
        summaries.append(dict(case_id=case,currency=cur,registration_value=total('REGISTRATION'),allocation_requested=total('QUEUE'),funding=net_total('FUNDING'),purchased=net_total('FX_BUY'),paid=paid,refund=net_total('REFUND'),fees=net_total('FEE'),allocation=total('ALLOCATION'),allocation_used=total('ALLOCATION_USE'),allocation_remaining=alloc,quota=total('QUOTA'),quota_used=total('QUOTA_USE'),quota_remaining=quota,commitment=commitment,settled=linked_settled,accepted_return=linked_return,settlement_evidence=raw_settlement,return_evidence=raw_return,commitment_remaining=bal,customs_value=total('CUSTOMS'),shipment_value=total('SHIPMENT'),untraced_payment=paid-traced if paid is not None else None,unmatched_payment=paid-matched if paid is not None else None))
        if raw_settlement is not None:
            linked_target=link_to_commit.get((case,cur,'SETTLEMENT'),ZERO)
            if raw_settlement>linked_target:issue('UNLINKED_SETTLEMENT',case+' / '+cur,'سند رفع تعهد ثبت شده اما تمام مبلغ آن به تعهد مشخص متصل نیست')
        if paid is not None and paid-traced>0:issue('UNTRACED_PAYMENT',case+' / '+cur,'بخشی از پرداخت به منبع وجه متصل نیست')
        if paid is not None and paid-matched>0:issue('UNMATCHED_PAYMENT',case+' / '+cur,'بخشی از پرداخت به بارنامه متصل نیست')
        for label,value in [('COMMITMENT',bal),('ALLOCATION',alloc),('QUOTA',quota)]:
            if value is not None and value<0:issue('EXCESS_'+label,case+' / '+cur,'مصرف/تسویه از مبنای ثبت‌شده بیشتر است','ERROR')
    document_rows=[]
    docgroups=defaultdict(list)
    for r in accepted:
        if r['bl_id']:docgroups[(r['case_id'],r['order_id'],r['bl_id'],r['currency'])].append(r)
    for (case,order,bl,cur),rs in docgroups.items():
        def docsum(kind):
            vals=[r['amount'] for r in rs if r['kind']==kind]
            return sum(vals,ZERO) if vals and all(v is not None for v in vals) else None
        matched=link_doc.get((case,bl,order,cur),ZERO)
        shipment=docsum('SHIPMENT')
        document_rows.append(dict(case_id=case,order_id=order,bl_id=bl,currency=cur,shipment_value=shipment,customs_value=docsum('CUSTOMS'),settled=docsum('SETTLEMENT'),matched_in_shipment_currency=matched if shipment is not None else None,unfunded_shipment=shipment-matched if shipment is not None else None,warehouse_evidence=' | '.join(r['document'] for r in rs if r['kind']=='WAREHOUSE')))
    timeline=[]
    by_case_kind=defaultdict(list)
    for r in accepted:by_case_kind[(r['case_id'],r['kind'])].append(r)
    for case in sorted({r['case_id'] for r in accepted+observations if r['case_id']}):
        for stage in STAGES:
            rs=by_case_kind.get((case,stage),[])
            timeline.append(dict(case_id=case,stage=stage,status='شاهد ثبت‌شده' if rs else 'شاهد معتبر موجود نیست',dates=' | '.join(sorted({r['date'] for r in rs})),documents=' | '.join(sorted({r['document'] for r in rs}))))
    periodic=defaultdict(lambda:dict(inflow=ZERO,outflow=ZERO,fx_in=ZERO,fx_out=ZERO))
    for r in accepted:
        if r['kind'] not in CASH or r['kind'] in {'OPENING','TRANSFER'}:continue
        g=periodic[(r['case_id'],r['date'][:7],r['currency'])]
        if r['kind']=='REVERSAL':
            original=by_id.get(r['reversal_of'],{})
            if original.get('kind')=='TRANSFER':continue
            side='inflow' if r['to_account'].startswith('OWN:') else 'outflow'
            if original.get('kind')=='FX_BUY':side='fx_out'
            elif original.get('kind')=='FX_SELL':side='fx_in'
        else:side='fx_in' if r['kind']=='FX_BUY' else 'fx_out' if r['kind']=='FX_SELL' else 'inflow' if r['kind'] in {'FUNDING','REFUND'} else 'outflow'
        g[side]+=r['amount']
    periods=[dict(case_id=k[0],period=k[1],currency=k[2],**v,net_movement=v['inflow']+v['fx_in']-v['outflow']-v['fx_out']) for k,v in sorted(periodic.items())]
    deadlines=[]
    rule_register=[]
    for q in records(rules):
        row={k:text(q.get(k)) for k in RULE_COLUMNS}
        verified=(row['approved'].lower()=='true' and row['authority'] and row['source'] and row['source_url']
                  and len(row['source_hash'])>=32 and row['approved_by'] and day(row['approved_at'])
                  and day(row['effective_from']) and day(row['effective_to']))
        row['verification_status']='VERIFIED' if verified else 'UNVERIFIED'
        rule_register.append(row)
    rules_by_id=defaultdict(list)
    for q in rule_register:rules_by_id[q['rule_id']].append(q)
    for r in accepted:
        if not r['due_date']:continue
        due=day(r['due_date'])
        candidates=[q for q in rules_by_id.get(r['rule_id'],[]) if q['verification_status']=='VERIFIED'
                    and day(q['effective_from'])<=day(r['date'])<=day(q['effective_to']) and day(q['effective_to'])>=as_of and q['kind']==r['kind']]
        verified=len(candidates)==1
        deadlines.append(dict(case_id=r['case_id'],event_id=r['event_id'],due_date=due,days_remaining=(due-as_of).days if due else None,rule_id=r['rule_id'],basis='قاعده تأییدشده ورودی' if verified else 'مهلت اعلامی؛ اعتبار قانونی تأیید نشده'))
    # Snapshots/measurements reconcile the ledger but never create financial events.
    measurement_rows=[];measurement_groups=defaultdict(list)
    for raw in records(measurements):
        m={k:text(raw.get(k)) for k in MEASUREMENT_COLUMNS};m['currency']=m['currency'].upper()
        dt=day(m['observed_at']);amt=number(m['amount'])
        if not m['measurement_id'] or not m['case_id'] or not m['metric'] or not dt or dt>as_of or amt is None or amt<0 or not m['currency'] or not m['source']:
            issue('INVALID_MEASUREMENT',m['measurement_id'],'Snapshot ناقص است و فقط در ورودی خام باقی می‌ماند');continue
        if m['currency'] in {'IRT','TOMAN','تومان','RIAL','ریال'}:
            issue('AMBIGUOUS_CURRENCY_UNIT',m['measurement_id'],'Snapshot با واحد مبهم ریال/تومان رد شد');continue
        m['amount']=amt;m['observed_at']=dt.isoformat();measurement_groups[m['measurement_id']].append(m)
    for mid,rows in measurement_groups.items():
        if len({tuple(r.items()) for r in rows})>1:
            issue('CONFLICTING_MEASUREMENT_ID',mid,'شناسه Snapshot محتوای متناقض دارد','ERROR');continue
        if len(rows)>1:issue('DUPLICATE_MEASUREMENT_REMOVED',mid,f'{len(rows)-1} Snapshot تکراری حذف شد','INFO')
        measurement_rows.append(rows[0])
    latest={}
    for m in measurement_rows:
        key=(m['case_id'],m['metric'],m['currency'],m['source'])
        if key not in latest or m['observed_at']>latest[key]['observed_at']:latest[key]=m
    summary_lookup={(r['case_id'],r['currency']):r for r in summaries}
    metric_map={'COMMITMENT_BALANCE':'commitment_remaining','ALLOCATION_BALANCE':'allocation_remaining',
                'QUOTA_BALANCE':'quota_remaining','PAYMENT_TOTAL':'paid','CUSTOMS_VALUE':'customs_value'}
    reconciliation=[]
    peers_by=defaultdict(list)
    for z in measurement_rows:peers_by[((z['case_id'],z['metric'],z['currency'],z['source']),z['observed_at'])].append(z)
    for key,m in latest.items():
        field=metric_map.get(m['metric']);ledger=summary_lookup.get((m['case_id'],m['currency']),{}).get(field) if field else None
        peers=peers_by.get((key,m['observed_at']),[])
        conflict=len({z['amount'] for z in peers})>1
        if conflict:
            issue('CONFLICTING_SNAPSHOT',m['measurement_id'],'Snapshotهای هم‌تاریخ یک منبع متناقض‌اند؛ انتخاب خودکار ممنوع','ERROR')
            ledger=None
        historical=m['observed_at']!=as_of.isoformat()
        if historical:ledger=None
        variance=m['amount']-ledger if ledger is not None else None
        status='CONFLICT' if conflict else 'DATE_MISMATCH' if historical else 'MATCH' if variance==0 else 'MISMATCH' if variance is not None else 'NO_LEDGER_COMPARATOR'
        reconciliation.append(dict(case_id=m['case_id'],currency=m['currency'],metric=m['metric'],source=m['source'],
                                   observed_at=m['observed_at'],reported_value=m['amount'],ledger_value=ledger,variance=variance,status=status,
                                   measurement_id=m['measurement_id'],document=m['document']))
        if status=='MISMATCH':issue('SNAPSHOT_LEDGER_MISMATCH',m['measurement_id'],'مانده گزارش‌شده با دفتر رویداد اختلاف دارد')
    # End-to-end obligation chain. This view never fabricates missing events or
    # relationships: it exposes what is evidenced, what is linked, and where a
    # downstream fact exists without its expected upstream documentary evidence.
    chain_rows=[]
    chain_specs=[
        (1,'PI','REGISTRATION','MISSING_PI_EVIDENCE','شاهد PI/ثبت تجاری'),
        (2,'ALLOCATION_REQUEST','QUEUE','MISSING_ALLOCATION_REQUEST_EVIDENCE','درخواست تخصیص'),
        (3,'ALLOCATION','ALLOCATION','MISSING_ALLOCATION_EVIDENCE','تخصیص'),
        (4,'COMMITMENT','COMMITMENT','MISSING_COMMITMENT_EVIDENCE','تعهد ارزی'),
        (5,'FX_BUY','FX_BUY','MISSING_FX_BUY_EVIDENCE','خرید ارز'),
        (6,'FUNDING','FUNDING','MISSING_FUNDING_EVIDENCE','تأمین وجه'),
        (7,'PAYMENT','PAYMENT','MISSING_PAYMENT_EVIDENCE','پرداخت ذی‌نفع'),
        (8,'SETTLEMENT_RETURN','SETTLEMENT|COMMITMENT_RETURN','MISSING_SETTLEMENT_EVIDENCE','رفع/عودت تعهد'),
    ]
    accepted_cases=sorted({r['case_id'] for r in accepted if r['case_id']} | {m['case_id'] for m in measurement_rows if m['case_id']})
    rec_by_case=defaultdict(list)
    for rr in reconciliation:rec_by_case[rr['case_id']].append(rr)
    sum_by_case=defaultdict(list)
    for rr in summaries:sum_by_case[rr['case_id']].append(rr)

    def _amount_text(rows):
        buckets=defaultdict(lambda:ZERO); unknown=set()
        for z in rows:
            if z.get('amount') is None: unknown.add(z.get('currency') or '')
            else:buckets[z.get('currency') or '']+=z['amount']
        parts=[((cur+' ') if cur else '')+format(val,'f') for cur,val in sorted(buckets.items())]
        parts.extend(((cur+' ') if cur else '')+'?' for cur in sorted(unknown) if cur not in buckets)
        return ' | '.join(parts)

    def _linked_amount_text(rows):
        """Currency-bearing display for links; never add unlike currencies."""
        buckets=defaultdict(lambda:ZERO)
        for cur,amount in rows:
            buckets[cur or ''] += amount
        if not buckets:
            return ''
        if len(buckets)==1:
            cur,val=next(iter(buckets.items()))
            return format(val,'f') if not cur else cur+' '+format(val,'f')
        return ' | '.join(((cur+' ') if cur else '')+format(val,'f') for cur,val in sorted(buckets.items()))

    accepted_by_case=defaultdict(list)
    for r in accepted:accepted_by_case[r['case_id']].append(r)
    links_by_target=defaultdict(list); links_by_source=defaultdict(list)
    for l in valid_links:
        links_by_target[l['target_case']].append(l); links_by_source[l['source_case']].append(l)
    for case in accepted_cases:
        evs=accepted_by_case.get(case,[])
        stage_events={}
        for seq,stage,kinds,gap_code,desc in chain_specs:
            kset=set(kinds.split('|'))
            stage_events[seq]=[r for r in evs if r['kind'] in kset]
        # A reduced NTSW balance is evidence that settlement/return happened in the
        # external system, but it is not itself a settlement event; the snapshot is
        # reported separately as stage 9 below. (A computed-but-unused
        # ``reduced_balance`` flag was removed in V29.9.)
        case_recs=[r for r in rec_by_case.get(case,[]) if r.get('metric')=='COMMITMENT_BALANCE']

        for seq,stage,kinds,gap_code,desc in chain_specs:
            rows=stage_events[seq]
            if rows:
                status='EVIDENCED'
                linked=''
                if stage=='PAYMENT':
                    paid_by_currency=defaultdict(lambda:ZERO)
                    for r in rows:
                        if r['amount'] is not None: paid_by_currency[r['currency']]+=r['amount']
                    link_rows=[(l['to_currency'],l['to_amount']) for l in links_by_target.get(case,[])
                               if l['target_kind']=='PAYMENT']
                    traced_by_currency=defaultdict(lambda:ZERO)
                    for cur,amount in link_rows: traced_by_currency[cur]+=amount
                    linked=_linked_amount_text(link_rows)
                    if any(traced_by_currency[cur] < amount for cur,amount in paid_by_currency.items()):
                        status='PARTIALLY_LINKED' if any(traced_by_currency.values()) else 'UNLINKED'
                elif stage=='SETTLEMENT_RETURN':
                    link_rows=[(l['from_currency'],l['from_amount']) for l in links_by_source.get(case,[])
                               if by_id[l['from_event']]['kind']=='COMMITMENT'
                               and l['target_kind'] in {'SETTLEMENT','COMMITMENT_RETURN'}]
                    settled=sum((amount for _,amount in link_rows),ZERO)
                    linked=_linked_amount_text(link_rows)
                    if settled==0:status='UNLINKED'
                chain_rows.append(dict(case_id=case,stage_no=seq,stage=stage,status=status,event_count=len(rows),amounts=_amount_text(rows),
                                       dates=' | '.join(sorted({r['date'] for r in rows if r['date']})),
                                       documents=' | '.join(sorted({r['document'] for r in rows if r['document']})),
                                       linked_amount=linked,gap_code='',detail=desc))
                continue
            # Absence is not a compliance/process gap without an explicit
            # applicability contract proving this stage was mandatory for the case.
            # Downstream evidence is informative, but it cannot create an upstream
            # obligation by inference alone.
            status='NOT_YET_EVIDENCED'
            code=''
            chain_rows.append(dict(case_id=case,stage_no=seq,stage=stage,status=status,event_count=0,amounts='',dates='',documents='',linked_amount='',gap_code=code,detail=desc))

        # Final stage: system snapshot versus event-ledger remaining commitment.
        recs=case_recs
        if recs:
            for rr in recs:
                chain_rows.append(dict(case_id=case,stage_no=9,stage='REMAINING_COMMITMENT',status=rr['status'],event_count=1,
                    amounts=f"{rr['currency']} {rr['reported_value']}",dates=rr['observed_at'],documents=rr['document'],
                    linked_amount='' if rr['ledger_value'] is None else format(rr['ledger_value'],'f'),gap_code='' if rr['status']=='MATCH' else ('COMMITMENT_BALANCE_RECONCILIATION_'+rr['status']),
                    detail='مانده گزارش‌شده سامانه در برابر مانده دفتر رویداد'))
        else:
            ledger_rows=[x for x in sum_by_case.get(case,[]) if x.get('commitment') is not None]
            if ledger_rows:
                vals=' | '.join(f"{x['currency']} {format(x['commitment_remaining'],'f') if x.get('commitment_remaining') is not None else '?'}" for x in ledger_rows)
                chain_rows.append(dict(case_id=case,stage_no=9,stage='REMAINING_COMMITMENT',status='LEDGER_ONLY',event_count=0,amounts=vals,dates='',documents='',linked_amount='',gap_code='MISSING_COMMITMENT_BALANCE_SNAPSHOT',detail='مانده دفتر موجود است ولی Snapshot سامانه برای تاریخ گزارش موجود نیست'))
                issue('MISSING_COMMITMENT_BALANCE_SNAPSHOT',case,'تعهد در دفتر وجود دارد ولی Snapshot مانده NTSW برای تطبیق موجود نیست')
            else:
                chain_rows.append(dict(case_id=case,stage_no=9,stage='REMAINING_COMMITMENT',status='NOT_APPLICABLE',event_count=0,amounts='',dates='',documents='',linked_amount='',gap_code='',detail='تعهد قابل محاسبه در دفتر موجود نیست'))

    rate_register=[]
    for q in records(rates):
        row={k:text(q.get(k)) for k in RATE_COLUMNS}
        row['provenance_status']='COMPLETE' if row['source'] and row['source_document'] and len(row['source_hash'])>=32 and row['approved_by'] and day(row['approved_at']) else 'INCOMPLETE'
        rate_register.append(row)
    return {'chain':frame(chain_rows),'documents':frame(document_rows),'conversions':frame(conversions),'periods':frame(periods),'summary':frame(summaries),'accounts':frame(balances),'events':frame(accepted,EVENT_COLUMNS),
            'links':frame(valid_links),'movements':frame(movements),'valuation':frame(valuations),
            'timeline':frame(timeline),'deadlines':frame(deadlines),'observations':frame(observations,EVENT_COLUMNS),
            'measurements':frame(measurement_rows,MEASUREMENT_COLUMNS),'reconciliation':frame(reconciliation),
            'rate_register':frame(rate_register),'rule_register':frame(rule_register),
            'issues':frame(issues,['code','reference','severity','detail']),
            'meta':{'as_of':as_of.isoformat(),'reporting_currency':reporting_currency,'legal_status':'قواعد فقط با مرجع رسمی، بازه اثر، هش سند و تأییدکننده معتبر می‌شوند؛ کانال‌ها صرفاً سرنخ پژوهشی‌اند','method':'Decimal; زنجیره PI→تخصیص→تعهد→خرید ارز→تامین وجه→پرداخت→رفع تعهد؛ رویداد و Snapshot جدا؛ SOURCE_FACT بدون جعل حساب بانکی؛ رفع تعهد فقط با لینک صریح؛ Gapها بدون حدس ثبت می‌شوند؛ بدون FIFO یا تبدیل ضمنی؛ مبالغ ناموجود صفر نیستند'}}

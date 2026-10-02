"""Display-only financial view models. No ledger calculations or source mutation."""
from __future__ import annotations
from html import escape
import pandas as pd

STAGE_LABELS = {'PI':'پیش‌فاکتور','ALLOCATION_REQUEST':'درخواست تخصیص','ALLOCATION':'تخصیص ارز',
    'COMMITMENT':'تعهد ارزی','FX_BUY':'خرید ارز','FUNDING':'تأمین وجه','PAYMENT':'پرداخت',
    'SETTLEMENT_RETURN':'رفع / عودت تعهد','REMAINING_COMMITMENT':'مانده تعهد','SWIFT_SENT':'ارسال سوئیفت'}
STATUS_LABELS = {'OBSERVED':'شاهد موجود','COMPLETED':'تکمیل مستند','EVIDENCE_GAP':'شکاف شواهد',
    'NOT_OBSERVED':'شاهد مشاهده نشده','NOT_MEASURED':'اندازه‌گیری نشده','NOT_APPLICABLE':'شاهد قابل محاسبه موجود نیست',
    'NO_LEDGER_COMPARATOR':'دفتر قابل تطبیق نیست','MATCH':'منطبق','MISMATCH':'اختلاف مبلغ',
    'CONFLICT':'شواهد متعارض','AMBIGUOUS':'مبهم','LEDGER_ONLY':'فقط دفتر رویداد',
    'DATE_MISMATCH':'تاریخ مشاهده متفاوت','SOURCE_COVERAGE_GAP':'پوشش منبع ناقص',
    'OBSERVED_UNLINKED':'شاهد بدون ارتباط قطعی','OBSERVED_WITH_GAPS':'شاهد با شکاف',
    'OBSERVED_NOT_LINKED':'شاهد بدون ارتباط قطعی','LINKED':'ارتباط مستند'}
SUMMARY_COLUMNS = ['case_id','currency','registration_value','allocation_requested','allocation','purchased','funding','paid']
SETTLEMENT_COLUMNS = ['case_id','currency','commitment','settled','accepted_return','commitment_remaining']

CSS = """
.fin-hero{direction:rtl;background:#102f39;color:#fff;border-radius:18px;padding:28px 30px;margin:16px 0 22px;border-top:4px solid #64d4bd}
.fin-hero h2{color:#fff!important;margin:8px 0;font-size:28px;letter-spacing:-.5px}
.fin-hero p{color:#cfdddd;line-height:1.9;margin:4px 0}.fin-eyebrow{font-size:11px;letter-spacing:2px;color:#86dcca;direction:ltr;text-align:right}
.fin-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;direction:rtl;margin:18px 0}
.fin-step{background:#f7f9fa;border:1px solid #dce5e7;border-radius:12px;padding:15px;min-height:96px;color:#193840}
.fin-step b{display:block;margin:5px 0 8px;font-size:14px}.fin-step small{color:#53686e;line-height:1.7}
.fin-status{display:inline-block;font-size:11px;padding:3px 8px;border-radius:6px;background:#e7eeee;color:#385158}
.fin-status.ok{background:#d8f1e8;color:#145c47}.fin-status.gap{background:#fff0d8;color:#825413}
.fin-step .fin-number{color:#82989d;font-size:11px}.fin-note{direction:rtl;border-right:3px solid #d7a75c;background:#fff9ed;color:#674d25;padding:13px 18px;line-height:1.9;border-radius:8px;margin:12px 0}
@media(max-width:650px){.fin-steps{grid-template-columns:repeat(2,minmax(0,1fr))}.fin-hero{padding:20px}.fin-hero h2{font-size:23px}}
"""

def cases(result):
    values=set()
    for key in ('events','observations','measurements','summary','chain'):
        df=result.get(key)
        if isinstance(df,pd.DataFrame) and 'case_id' in df:
            values.update(str(v) for v in df.case_id if pd.notna(v) and str(v))
    return sorted(values)

def select_rows(df, case='', currency=''):
    if not isinstance(df,pd.DataFrame):return pd.DataFrame()
    out=df.copy()
    if case and 'case_id' in out:out=out[out.case_id.astype(str).eq(case)]
    if currency and 'currency' in out:out=out[out.currency.astype(str).eq(currency)]
    return out

def display_frame(df, columns=None):
    from .report import LABELS, display
    if columns is not None:df=df[[c for c in columns if c in df]].copy()
    else:df=df.copy()
    for c in ('stage','status'):
        if c in df:df[c]=df[c].map(lambda v:(STAGE_LABELS if c=='stage' else STATUS_LABELS).get(str(v),v))
    for c in df:df[c]=df[c].map(display)
    return df.rename(columns=LABELS)

def stage_cards(df):
    cards=[]
    for _,r in df.iterrows():
        state=str(r.get('status',''));tone='ok' if state in {'OBSERVED','COMPLETED','MATCH','LINKED'} else 'gap' if 'GAP' in state or state in {'MISMATCH','CONFLICT'} else ''
        cards.append('<div class="fin-step"><span class="fin-number">'+escape(str(r.get('stage_no','')))+
            '</span><b>'+escape(STAGE_LABELS.get(str(r.get('stage','')),str(r.get('stage',''))))+'</b><span class="fin-status '+tone+'">'+
            escape(STATUS_LABELS.get(state,state))+'</span><br><small>'+escape(str(r.get('amounts','') or 'مبلغ قابل اتکا موجود نیست'))+'</small></div>')
    return '<div class="fin-steps">'+''.join(cards)+'</div>'

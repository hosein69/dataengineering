"""Evidence-based flow widgets. No fabricated velocity, completion or sprint burndown."""
import html
from collections import Counter
from datetime import date
LABELS={'KEY_REG':'ثبت سفارش','CANONICAL_ORDER':'سفارش','CANONICAL_BL':'بارنامه','KEY_MATERIAL':'شماره فنی','NEXT_ACTION_TITLE':'اقدام بعدی','NEXT_ACTION_DUE_DATE':'موعد اقدام','NEXT_ACTION_OWNER':'مسئول اقدام','FX_CURRENT_STAGE':'مرحله ارزی','FX_ACTION_TITLE':'اقدام ارزی','FX_ACTION_DUE_DATE':'موعد اقدام ارزی','recipient_name':'نام و نام خانوادگی','recipient_management':'مدیریت','recipient_department':'اداره','recipient_position':'جایگاه سازمانی'}

def actions(records):
    result=[];seen=set()
    for r in records:
        action=r.get('NEXT_ACTION_TITLE') or r.get('FX_ACTION_TITLE')
        if not action:continue
        case=r.get('CANONICAL_ORDER') or r.get('KEY_REG') or r.get('CANONICAL_BL') or 'شناسه ثبت نشده'
        due=r.get('NEXT_ACTION_DUE_DATE') or r.get('FX_ACTION_DUE_DATE') or ''
        owner=r.get('NEXT_ACTION_OWNER') or ''
        key=(str(case),str(action),str(due),str(owner))
        if key in seen:continue
        seen.add(key)
        result.append({'پرونده':case,'اقدام':action,'مسئول':owner or 'نیازمند تعیین مسئول','موعد':due or 'تعیین نشده','مانع':r.get('مانع فعلی') or '', 'اولویت':r.get('NEXT_ACTION_PRIORITY') or r.get('FX_ACTION_PRIORITY') or 'تعیین نشده'})
    return result

def extra_widget(kind,records,level,ref,table):
    from gsi.core.jalali import CalendarEngine
    rows=actions(records)
    if kind=='learning':
        text={'expert':'برای هر اقدام، نتیجه مورد انتظار، مسئول و موعد را مشخص کنید. اگر منتظر پاسخ هستید، مانع و زمان پیگیری بعدی را ثبت کنید.',
              'manager':'در مرور کوتاه تیم، ابتدا موانع را بررسی کنید؛ سپس اقدام‌های بدون مسئول و موعد را تعیین تکلیف کنید. تعداد پرونده‌ها به‌تنهایی معیار بهره‌وری افراد نیست.',
              'executive':'اولویت مرور: تصمیم موردنیاز، پیامد تعویق، مسئول تصمیم و موعد. مرحله فرایند نشان‌دهنده پیشرفت قطعی یا درصد تکمیل نیست.'}[level]
        return '<h2 style="font-size:20px">راهنمای کوتاه پیگیری</h2><p>'+html.escape(text)+'</p>'
    if kind=='commitments':
        today=CalendarEngine.parse(ref)
        for r in rows:
            due=CalendarEngine.parse(r['موعد'])
            r['وضعیت موعد']='موعد نامشخص' if due is None or today is None else ('عقب‌افتاده' if due<today else 'امروز' if due==today else 'پیش رو')
        rows.sort(key=lambda r:({'عقب‌افتاده':0,'امروز':1,'موعد نامشخص':2,'پیش رو':3}[r['وضعیت موعد']],str(r['موعد'])))
        title='تعهدهای نیازمند پیگیری';fields=['پرونده','اقدام','مسئول','موعد','وضعیت موعد']
    elif kind=='decisions':
        rows=[dict(r,**{'موضوع بررسی':'رفع مانع' if r['مانع'] else 'تعیین مسئول'}) for r in rows if r['مانع'] or r['مسئول']=='نیازمند تعیین مسئول']
        title='موارد پیشنهادی برای مرور مدیر';fields=['پرونده','موضوع بررسی','اقدام','مانع','مسئول']
    else:
        title='تابلوی اقدام';fields=['پرونده','اقدام','وضعیت پیگیری','مسئول','موعد']
        for r in rows:r['وضعیت پیگیری']='دارای مانع' if r['مانع'] else 'اقدام ثبت‌شده'
    return '<h2 style="font-size:20px">'+title+'</h2>'+table(rows,fields)

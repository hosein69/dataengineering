"""Presentation contracts: preserve metric meaning and missing values."""
import numpy as np
import pandas as pd


def bottleneck_view(frame, limit=12):
    label=next((c for c in ('میانه روز','میانگین روز') if frame is not None and c in frame.columns),None)
    if label is None or not {'از فعالیت','به فعالیت'}.issubset(frame.columns):
        return pd.DataFrame(), None
    result=frame.copy()
    result[label]=pd.to_numeric(result[label],errors='coerce')
    result=result.loc[np.isfinite(result[label]) & result[label].ge(0)]
    return result.sort_values(label,ascending=False).head(limit),label


def resistance_diagnostic(frame):
    if frame.empty:return 'در فیلتر فعلی هیچ ردیفی وجود ندارد؛ فیلترها را بازتر کنید.'
    if 'مقاومت (روز)' not in frame:return 'ستون مقاومت در خروجی وجود ندارد؛ اجرای مرحله بحرانی‌بودن و ورودی‌های آن را بررسی کنید.'
    codes=frame.get('کد طبقه بحرانی',pd.Series('',index=frame.index)).fillna('').astype(str)
    parts=[]
    unknown=int(codes.eq('UNKNOWN').sum());no_need=int(codes.eq('NO_CONSUMPTION').sum())
    if unknown:parts.append(f'{unknown} ردیف با ورودی نامعلوم یا ناقص')
    if no_need:parts.append(f'{no_need} ردیف بدون مصرف روزانه مثبت')
    return ('مقاومت قابل رسم موجود نیست. '+('؛ '.join(parts)+'. ' if parts else '')+
            'موجودی قابل مصرف و نیاز روزانه را در جدول داده و کیفیت بررسی کنید؛ مقدار نامعلوم صفر محسوب نشده است.')

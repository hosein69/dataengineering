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


def _numeric_from(frame, *candidates):
    """اولین ستون موجود را عددی برمی‌گرداند؛ نبود ستون = NaN واقعی، نه صفر."""
    for col in candidates:
        if col in frame.columns:
            return pd.to_numeric(frame[col], errors='coerce')
    return pd.Series(np.nan, index=frame.index, dtype='float64')


def ensure_resistance_columns(frame):
    """قرارداد دفاعی لایه ارائه برای مقاومت قطعه.

    منبع حقیقت موتور criticality است. ولی Dashboard ممکن است `main` ذخیره‌شده
    از Warehouse قدیمی را بخواند که ستون نمایشی «مقاومت (روز)» در آن خالی است
    در حالی‌که ورودی‌های خام موجودند. در این حالت فقط خانه‌های خالی با فرمول
    رسمی `(IKCO + SAPCO) / DAILY_NEED` ترمیم می‌شوند. هیچ مقدار معتبر موجود
    بازنویسی نمی‌شود و Missing هرگز صفر فرض نمی‌شود.
    """
    if frame is None:
        return frame
    out = frame.copy()
    ikco = _numeric_from(out, 'STOCK_IKCO', 'موجودی ایران خودرو')
    sapco = _numeric_from(out, 'STOCK_SAPCO', 'موجودی ساپکو')
    need = _numeric_from(out, 'DAILY_NEED', 'نیاز روزانه')
    stock = pd.concat([ikco, sapco], axis=1).sum(axis=1, min_count=2)
    computed = (stock / need.where(need > 0)).replace([np.inf, -np.inf], np.nan).round(1)

    existing = _numeric_from(out, 'مقاومت (روز)')
    # مقاومت انبار همان تعریف رسمی بحرانی است؛ اگر موتور آن را نوشته باشد،
    # نسبت به recompute ارائه‌ای اولویت دارد.
    warehouse = _numeric_from(out, 'مقاومت انبار (روز)')
    repaired = existing.combine_first(warehouse).combine_first(computed)
    out['مقاومت (روز)'] = repaired
    if 'مقاومت انبار (روز)' not in out.columns:
        out['مقاومت انبار (روز)'] = repaired
    else:
        out['مقاومت انبار (روز)'] = warehouse.combine_first(repaired)
    return out



def ensure_criticality_columns(frame):
    """Repair stale/UNKNOWN presentation bands from the official resistance.

    The pipeline CriticalityEngine remains the source of truth. This function is only
    a defensive presentation-layer repair for persisted/older ``main`` frames where
    resistance was recoverable but the criticality labels remained UNKNOWN. Existing
    non-UNKNOWN bands are never overwritten.
    """
    if frame is None:
        return frame
    out = ensure_resistance_columns(frame)
    if out is None or out.empty:
        return out

    from gsi.engines.criticality import CriticalityEngine
    eng = CriticalityEngine()

    resistance = pd.to_numeric(out.get('مقاومت (روز)'), errors='coerce')
    need = _numeric_from(out, 'DAILY_NEED', 'نیاز روزانه')

    existing_code = out.get('کد طبقه بحرانی', pd.Series('', index=out.index)).fillna('').astype(str).str.strip()
    existing_short = out.get('بحرانی (کوتاه)', pd.Series('', index=out.index)).fillna('').astype(str).str.strip()
    existing_full = out.get('طبقه بحرانی', pd.Series('', index=out.index)).fillna('').astype(str).str.strip()

    stale = existing_code.isin(['', 'UNKNOWN', 'nan', 'None']) | existing_short.isin(['', 'نامشخص', 'nan', 'None'])
    can_classify = resistance.notna() | need.le(0).fillna(False)
    repair_mask = stale & can_classify

    code = existing_code.copy()
    short = existing_short.copy()
    full = existing_full.copy()
    sort_rank = pd.to_numeric(out.get('CRITICALITY_SORT', pd.Series(np.nan, index=out.index)), errors='coerce')
    action = out.get('اقدام پیشنهادی مقاومت', pd.Series('', index=out.index)).fillna('').astype(str).copy()

    for idx in out.index[repair_mask]:
        n = need.loc[idx] if idx in need.index else np.nan
        d = resistance.loc[idx] if idx in resistance.index else np.nan
        if pd.notna(n) and float(n) <= 0:
            band = eng._band('NO_CONSUMPTION')
        elif pd.notna(d):
            band = eng.band_for_days(float(d))
        else:
            continue
        code.loc[idx] = str(band.get('code', 'UNKNOWN'))
        short.loc[idx] = str(band.get('short_fa', band.get('code', 'UNKNOWN')))
        full.loc[idx] = str(band.get('fa', band.get('code', 'UNKNOWN')))
        sort_rank.loc[idx] = float(band.get('sort', 9))
        action.loc[idx] = str(band.get('action', ''))

    out['کد طبقه بحرانی'] = code
    out['بحرانی (کوتاه)'] = short
    out['طبقه بحرانی'] = full
    out['CRITICALITY_SORT'] = sort_rank
    out['اقدام پیشنهادی مقاومت'] = action
    return out

def resistance_diagnostic(frame):
    if frame.empty:return 'در فیلتر فعلی هیچ ردیفی وجود ندارد؛ فیلترها را بازتر کنید.'
    work = ensure_resistance_columns(frame)
    resistance = pd.to_numeric(work.get('مقاومت (روز)'), errors='coerce')
    finite = np.isfinite(resistance)
    if finite.any():
        return f'{int(finite.sum())} ردیف مقاومت قابل رسم دارد.'
    ikco = _numeric_from(work, 'STOCK_IKCO', 'موجودی ایران خودرو')
    sapco = _numeric_from(work, 'STOCK_SAPCO', 'موجودی ساپکو')
    need = _numeric_from(work, 'DAILY_NEED', 'نیاز روزانه')
    parts=[]
    miss_stock=int((ikco.isna() | sapco.isna()).sum())
    miss_need=int((need.isna() | need.le(0)).sum())
    if miss_stock: parts.append(f'{miss_stock} ردیف بدون موجودی کامل IKCO/SAPCO')
    if miss_need: parts.append(f'{miss_need} ردیف بدون نیاز روزانه مثبت')
    # Preserve business semantics already present in the classified frame. A
    # NO_CONSUMPTION row is not the same thing as an unknown row even though
    # neither produces a finite resistance bar.
    codes=work.get('کد طبقه بحرانی',pd.Series('',index=work.index)).fillna('').astype(str).str.strip()
    no_consumption=int(codes.eq('NO_CONSUMPTION').sum())
    unknown=int(codes.isin(['','UNKNOWN','nan','None']).sum())
    if no_consumption: parts.append(f'{no_consumption} ردیف بدون مصرف')
    if unknown: parts.append(f'{unknown} ردیف نامعلوم')
    return ('مقاومت قابل رسم موجود نیست. '+('؛ '.join(parts)+'. ' if parts else '')+
            'فرمول رسمی داشبورد (IKCO + SAPCO) ÷ نیاز روزانه است؛ مقدار نامعلوم صفر محسوب نشده است.')

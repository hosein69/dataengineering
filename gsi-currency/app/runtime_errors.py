"""Context-aware user-facing runtime diagnostics for Streamlit."""
from __future__ import annotations


def classify_pipeline_exception(ex):
    try:
        from gsi.warehouse.writer_lock import WarehouseBusyError
    except Exception:
        WarehouseBusyError = ()
    if WarehouseBusyError and isinstance(ex, WarehouseBusyError):
        d = ex.as_dict()
        return {
            'code': d.get('code','WAREHOUSE_WRITER_BUSY'),
            'category': 'همزمانی / قفل نویسنده',
            'severity': 'اطلاعاتی',
            'title': 'اجرای دوم عمداً شروع نشد',
            'message': str(ex),
            'impact': 'هیچ داده‌ای خراب یا حذف نشده؛ اجرای فعال مالک نوشتن است.',
            'action': 'منتظر پایان اجرای فعال بمانید. برای این خطا بررسی مسیر سورس‌ها با gsi.doctor لازم نیست.',
            'details': d,
            'doctor': False,
        }
    try:
        from gsi.warehouse.store import QualityGateBlockedError
    except Exception:
        QualityGateBlockedError = ()
    if QualityGateBlockedError and isinstance(ex, QualityGateBlockedError):
        d = ex.as_dict()
        return {
            'code': 'QUALITY_GATE_BLOCKED',
            'category': 'کیفیت داده / انتشار',
            'severity': 'هشدار',
            'title': 'Snapshot جدید منتشر نشد',
            'message': str(ex),
            'impact': 'اجرای جدید برای بررسی نگه داشته شد؛ Snapshot سالم قبلی باید همچنان نمایش داده شود.',
            'action': 'در DWH Control Room فقط کنترل‌های مسدودکننده را بررسی کنید؛ اجرای doctor برای این خطا لازم نیست.',
            'details': d,
            'doctor': False,
        }
    msg = str(ex)
    source_markers = ('No such file','پیدا نشد','source','مسیر','Path','فایل سورس')
    source_like = isinstance(ex, FileNotFoundError) or any(x.lower() in msg.lower() for x in source_markers)
    return {
        'code': type(ex).__name__.upper(),
        'category': 'سورس/محیط' if source_like else 'اجرای خط لوله',
        'severity': 'خطا',
        'title': 'خط لوله کامل نشد',
        'message': msg,
        'impact': 'Snapshot جدید منتشر نشده است؛ آخرین Snapshot سالم باید مبنای مشاهده باقی بماند.',
        'action': ('مسیرها و محیط را با python -m gsi.doctor بررسی کنید.' if source_like
                   else 'جزئیات فنی و DWH Control Room را بررسی کنید؛ gsi.doctor فقط در صورت خطای مسیر/محیط لازم است.'),
        'details': {'exception_type': type(ex).__name__},
        'doctor': source_like,
    }


def render_pipeline_exception(st, ex):
    info = classify_pipeline_exception(ex)
    if info['severity'] == 'اطلاعاتی':
        st.warning(f"{info['title']}: {info['message']}")
    else:
        st.error(f"{info['title']}: {info['message']}")
    st.caption(f"اثر: {info['impact']}")
    st.info(info['action'])
    with st.expander('جزئیات تشخیصی', expanded=False):
        st.json({'code':info['code'],'category':info['category'],**info['details']})
    return info

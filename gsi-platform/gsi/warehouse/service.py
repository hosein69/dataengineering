from .store import Warehouse,RUN,dumps,loads
from .excel import capture,frame
from .numeric import decimal_text
from collections.abc import MutableMapping
import logging
import pandas as pd
import sqlite3

_LOG = logging.getLogger(__name__)


class LazyFrameExtras(MutableMapping):
    """Dict-like extras that deserialize mart frames only when a view asks for them.

    Scalar metadata is available immediately. DataFrame extras stay as frame ids
    until ``get``/indexing touches that key. This keeps Streamlit startup focused
    on the main analytical frame instead of rebuilding every Event/FX/Process mart.
    """
    def __init__(self, warehouse_path, values=None, frame_ids=None):
        self._warehouse_path = str(warehouse_path)
        self._values = dict(values or {})
        self._frame_ids = dict(frame_ids or {})
        self._load_errors = {}
        self._transform = None

    def __getitem__(self, key):
        if key in self._values:
            return self._values[key]
        if key not in self._frame_ids:
            raise KeyError(key)
        try:
            # Reader-only construction: never initialize/DDL from Streamlit lazy
            # access. read_frame itself is cache-first and query-only on fallback.
            value = Warehouse(self._warehouse_path, initialize=False).read_frame(self._frame_ids[key])
        except sqlite3.OperationalError as ex:
            if 'locked' not in str(ex).lower() and 'busy' not in str(ex).lower():
                raise
            # One unavailable analytical extra must not blank the whole cockpit.
            # Missing stays Missing; it is never converted to zero.
            self._load_errors[key] = {'code':'DWH_READ_BUSY','detail':str(ex)}
            _LOG.warning('Lazy mart %s unavailable because warehouse is busy: %s', key, ex)
            value = None
        if self._transform is not None and isinstance(value, pd.DataFrame):
            value = self._transform(key, value)
        self._values[key] = value
        return value

    def __setitem__(self, key, value):
        self._values[key] = value
        self._frame_ids.pop(key, None)

    def __delitem__(self, key):
        existed = key in self._values or key in self._frame_ids
        self._values.pop(key, None); self._frame_ids.pop(key, None)
        if not existed: raise KeyError(key)

    def __iter__(self):
        return iter(dict.fromkeys([*self._values.keys(), *self._frame_ids.keys()]))

    def __len__(self):
        return len(set(self._values) | set(self._frame_ids))

    def with_frame_transform(self, fn):
        """نگاشت تنبلِ تازه که هر فریم را هنگام اولین دسترسی از ``fn`` می‌گذراند.

        محدودکردن دامنهٔ دسترسی (scope) باید روی **همهٔ** فریم‌ها اعمال شود، ولی
        لازم نیست همان لحظه همهٔ آن‌ها از SQLite باز شوند. بدون این متد،
        ``dict(extras)`` در مسیر رندر، ده‌ها mart را می‌ساخت — یعنی همان کندی‌ای
        که Snapshot منتشرشده برای حذفش وجود دارد.

        ``fn(name, frame)`` باید فریمِ محدودشده را برگرداند. مقادیری که همین حالا
        ساخته شده‌اند هم از همان تابع می‌گذرند تا هیچ فریمی بدون scope نماند.
        """
        clone = LazyFrameExtras(self._warehouse_path)
        clone._frame_ids = dict(self._frame_ids)
        clone._transform = fn
        for key, value in self._values.items():
            clone._values[key] = fn(key, value) if isinstance(value, pd.DataFrame) else value
        return clone

    def materialized_keys(self):
        return tuple(self._values.keys())

    def load_errors(self):
        return dict(self._load_errors)


def ingest_file(path,source):
    wh=Warehouse()
    with wh.run({'operation':'ingest','source':source}) as rid:
        fid,blob,sheets=capture(path,source)
        result={}
        for name,rows in sheets.items():
            df=frame(rows,source,name,fid)
            # Raw bytes/cells retain the original evidence; prohibited Oracle values
            # are excluded from every analytical/staging frame.
            if source=='oracle':
                forbidden={'وضعیت','قطعه بحرانی','شماره نامه','تاریخ ثبت','توضیحات','شماره پرسنلی','کارشناس خرید خارجی','ریسک پذیری','Column18'}
                df=df.drop(columns=[c for c in df if c in forbidden],errors='ignore')
            if not df.empty:
                from .marts import stage
                stage(df,source,name,fid)
                result[name]=df
                wh.frame(df,'staging',source+'/'+name)
        if source in ('oracle','fx_transaction','ntsw'):
            from ..adapters import discover as discover_adapters
            adapter=discover_adapters()[source]()
            outputs=adapter.transform(result)
            for name,df in outputs.items():wh.frame(df,'standardized',source+'/'+name)
        wh.audit('ingest_complete',{'file_id':fid,'source':source,'sheets':len(sheets)})
    return rid,fid

def published_reference_date():
    """Reference date of the currently published report (``YYYY-MM-DD``) or None.

    Cheap: reads only the run context, no frames. UIs use it as their default
    date so the latest snapshot is not labelled *stale* just because today's
    date differs from the day the refresh ran.
    """
    wh=Warehouse(initialize=False)
    if not wh.path.exists(): return None
    try:
        with wh.read_db() as c:
            row=c.execute("SELECT r.context FROM wh_current v JOIN wh_run r ON r.id=v.run_id WHERE v.slot='report' AND r.status='completed'").fetchone()
    except Exception:
        return None
    if not row: return None
    value=loads(row[0]).get('reference_date')
    return str(value) if value else None


def last_report(ref_date=None):
    wh=Warehouse(initialize=False)
    if not wh.path.exists(): return None
    with wh.read_db() as c:
        row=c.execute("SELECT r.id,r.context FROM wh_current v JOIN wh_run r ON r.id=v.run_id WHERE v.slot='report' AND r.status='completed'").fetchone()
        if not row:return None
        published_ref = loads(row[1]).get('reference_date')
        if ref_date is not None and published_ref!=ref_date:return None
        frames=c.execute("SELECT name,id FROM wh_frame WHERE run_id=? AND layer='mart' ORDER BY created",(row[0],)).fetchall()
        metadata=c.execute("SELECT payload FROM wh_audit WHERE run_id=? AND kind='report_metadata' ORDER BY id DESC LIMIT 1",(row[0],)).fetchone()

    # Studio needs only df/main to draw the first frame.  Older releases also
    # deserialized audit, excluded, to_resolve, mogh_lines and *every* extras
    # DataFrame here although most tabs never touched them.
    frame_map={name:fid for name,fid in frames}
    if 'df' not in frame_map or 'main' not in frame_map:
        return None
    df=wh.read_frame(frame_map['df'])
    main=wh.read_frame(frame_map['main'])
    meta=loads(metadata[0]) if metadata else {}
    scalar_extras=dict(meta.get('extras',{}))
    scalar_extras['warehouse_run_id']=row[0]
    scalar_extras['published_reference_date']=published_ref
    lazy_ids={name[7:]:fid for name,fid in frames if name.startswith('extras/')}
    # Commercial Expert line evidence is intentionally NOT merged into the BL-grain
    # authoritative mart. Expose it lazily so global search can still find every
    # source row (including orders outside the current Abbasi/base population).
    if 'mogh_lines' in frame_map:
        lazy_ids['commercial_lines'] = frame_map['mogh_lines']
    if 'material_evidence' in frame_map:
        lazy_ids['material_evidence'] = frame_map['material_evidence']
    extras=LazyFrameExtras(wh.path, scalar_extras, lazy_ids)
    return df,main,extras,meta.get('report','')

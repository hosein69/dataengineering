"""انبار داده GSI نسخه ۲: SQLite در حالت WAL + پوشه بایگانی با اثرانگشت.

چه عوض شد نسبت به نسخه ۱ و چرا
------------------------------
* هر اجرا یک شماره پیوسته (``wh_run.seq``) دارد؛ سوابق و جدول‌های کسب‌وکار با بازه
  ``from_seq``..``to_seq`` نسخه‌بندی می‌شوند و هیچ ردیفی پاک نمی‌شود.
* بایت‌های فایل‌های منبع، فریم‌ها (Parquet) و بایگانی خانه‌های فیزیکی کاربرگ‌ها در
  ``<db>.objects`` می‌نشینند، هر محتوا فقط یک‌بار. SQLite کوچک می‌ماند و بررسی سلامتش
  ثانیه‌ای است نه دقیقه‌ای.
* WAL: Studio هنگام Refresh می‌خواند و نویسنده را معطل نمی‌کند، و برعکس.
* انتشار فقط اشاره‌گر ``wh_current`` را جابه‌جا می‌کند؛ کپی Snapshot دیگر ساخته نمی‌شود
  و خواننده‌ها با نماهای موقت «به تاریخ اجرای منتشرشده» می‌خوانند (``snapshots.py``).

فایل انبار نسخه ۱ هرگز پاک یا بازنویسی نمی‌شود: اولین نویسنده نسخه ۲ آن را کنار همان
پوشه با نام ``*.v1-archive-<زمان>.sqlite`` بایگانی می‌کند و انبار تازه می‌سازد.
"""
from __future__ import annotations
import contextvars
import hashlib
import json
import math
import os
import gc
import shutil
import sqlite3
import time
import uuid
from contextlib import contextmanager, closing
from datetime import date, datetime, timezone
from pathlib import Path

from .objects import ObjectStore, objects_root, clean_ext

RUN = contextvars.ContextVar('warehouse_run', default=None)
RUN_SEQ = contextvars.ContextVar('warehouse_run_seq', default=None)

#: نسخه قالب انبار. ۱ = نسخه قبلی (کپی Snapshot، فریم JSON، بایت‌ها داخل SQLite).
SCHEMA_VERSION = 2


class QualityGateBlockedError(ValueError):
    """Publication was refused while the previous good snapshot remains valid."""
    def __init__(self, run_id, failures):
        self.run_id = str(run_id)
        self.failures = tuple((str(a), str(b)) for a,b in failures)
        detail = ', '.join(f'{a}:{b}' for a,b in self.failures[:12])
        super().__init__('Quality gate blocked publish: ' + detail)

    def as_dict(self):
        return {
            'code':'QUALITY_GATE_BLOCKED',
            'category':'DATA_QUALITY',
            'run_id':self.run_id,
            'blocking_checks':[f'{a}:{b}' for a,b in self.failures],
        }


class LegacyWarehouseError(RuntimeError):
    """The configured file is a version-1 warehouse that v2 readers cannot interpret."""


def now(): return datetime.now(timezone.utc).isoformat()
def encode(x):
    # Fast path for the overwhelmingly common plain cell values (exact types
    # only: subclasses such as numpy.str_ still take the general path below).
    t=type(x)
    if t is str or t is int or t is bool or x is None: return x
    if t is float: return x if math.isfinite(x) else {'$type':'float','value':repr(x)}
    import numpy as np
    import pandas as pd
    if x is pd.NA: return {'$type':'NA'}
    if x is pd.NaT: return {'$type':'NaT'}
    if isinstance(x, np.generic): x=x.item()
    if isinstance(x, float) and not math.isfinite(x): return {'$type':'float','value':repr(x)}
    if isinstance(x, (datetime,date)): return {'$type':type(x).__name__,'value':x.isoformat()}
    if isinstance(x, tuple): return {'$type':'tuple','value':[encode(v) for v in x]}
    if isinstance(x, list): return [encode(v) for v in x]
    if isinstance(x, dict): return {str(k):encode(v) for k,v in x.items()}
    if x is None or isinstance(x,(str,int,float,bool)): return x
    raise TypeError(f'Unsupported warehouse value: {type(x).__name__}')
def decode(x):
    import pandas as pd
    if isinstance(x,list): return [decode(v) for v in x]
    if not isinstance(x,dict): return x
    kind=x.get('$type')
    if kind=='NA': return pd.NA
    if kind=='NaT': return pd.NaT
    if kind=='float': return float(x['value'])
    if kind in ('datetime','Timestamp'): return pd.Timestamp(x['value'])
    if kind=='date': return date.fromisoformat(x['value'])
    if kind=='tuple': return tuple(decode(v) for v in x['value'])
    return {k:decode(v) for k,v in x.items()}
def dumps(x): return json.dumps(encode(x),ensure_ascii=False,allow_nan=False,separators=(',',':'))
def loads(x): return decode(json.loads(x))
def local_path(value):
    raw=str(value)
    if raw.startswith(('\\\\','//')): raise ValueError('SQLite باید روی دیسک محلی اتاق کنترل باشد؛ نه فولدر شبکه.')
    p=Path(raw).expanduser().resolve()
    if os.name=='nt':
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(p.anchor))==4:
            raise ValueError('درایو نگاشت‌شده شبکه برای SQLite مجاز نیست.')
    return p

SCHEMA='''
CREATE TABLE IF NOT EXISTS wh_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_run(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,
 id TEXT NOT NULL UNIQUE,
 started TEXT NOT NULL,
 finished TEXT,
 status TEXT NOT NULL,
 context TEXT NOT NULL,
 error TEXT,
 timings TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS wh_audit(id INTEGER PRIMARY KEY,at TEXT NOT NULL,run_id TEXT,kind TEXT NOT NULL,actor TEXT NOT NULL,payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS wh_audit_run ON wh_audit(run_id,id);
CREATE TABLE IF NOT EXISTS wh_object(
 sha TEXT PRIMARY KEY,
 ext TEXT NOT NULL,
 kind TEXT NOT NULL,
 size INTEGER NOT NULL,
 created_run TEXT,
 created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_file(
 id TEXT PRIMARY KEY REFERENCES wh_object(sha),
 name TEXT NOT NULL,
 size INTEGER NOT NULL,
 created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_ingest(
 id INTEGER PRIMARY KEY,
 run_id TEXT,
 source TEXT NOT NULL,
 path TEXT NOT NULL,
 file_id TEXT NOT NULL REFERENCES wh_file(id),
 at TEXT NOT NULL,
 change TEXT NOT NULL DEFAULT 'new');
CREATE INDEX IF NOT EXISTS wh_ingest_run ON wh_ingest(run_id,source);
CREATE INDEX IF NOT EXISTS wh_ingest_path ON wh_ingest(source,path,id);
CREATE TABLE IF NOT EXISTS wh_sheet(
 file_id TEXT NOT NULL REFERENCES wh_file(id),
 name TEXT NOT NULL,
 metadata TEXT NOT NULL,
 object_sha TEXT REFERENCES wh_object(sha),
 PRIMARY KEY(file_id,name));
CREATE TABLE IF NOT EXISTS wh_issue(id INTEGER PRIMARY KEY,run_id TEXT,file_id TEXT,sheet TEXT,row_no INTEGER,code TEXT NOT NULL,detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_frame(
 id TEXT PRIMARY KEY,
 run_id TEXT REFERENCES wh_run(id),
 layer TEXT NOT NULL,
 name TEXT NOT NULL,
 metadata TEXT NOT NULL,
 row_count INTEGER NOT NULL,
 created TEXT NOT NULL,
 object_sha TEXT NOT NULL REFERENCES wh_object(sha));
CREATE INDEX IF NOT EXISTS wh_frame_run ON wh_frame(run_id,layer,name);
CREATE TABLE IF NOT EXISTS wh_config(namespace TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_current(slot TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES wh_run(id));
CREATE TABLE IF NOT EXISTS wh_quality_check(
 run_id TEXT NOT NULL REFERENCES wh_run(id),
 seq INTEGER NOT NULL,
 contract TEXT NOT NULL,
 code TEXT NOT NULL,
 severity TEXT NOT NULL,
 passed INTEGER NOT NULL,
 detail TEXT NOT NULL,
 PRIMARY KEY(run_id,seq));
CREATE INDEX IF NOT EXISTS wh_quality_check_run ON wh_quality_check(run_id,severity,passed);
CREATE TABLE IF NOT EXISTS wh_schema_baseline(
 contract TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, columns_json TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_schema_candidate(
 run_id TEXT,contract TEXT,fingerprint TEXT,columns_json TEXT,updated TEXT,PRIMARY KEY(run_id,contract));
CREATE TABLE IF NOT EXISTS wh_publish_event(
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES wh_run(id), slots TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_health_check(
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, run_id TEXT, kind TEXT NOT NULL, passed INTEGER NOT NULL,
 seconds REAL NOT NULL, detail TEXT NOT NULL);

-- دفتر بارگذاری هر سورس در هر اجرا: فایل‌ها، اثرانگشت ورودی و اینکه دوباره خوانده شد یا نه
CREATE TABLE IF NOT EXISTS wh_source_load(
 run_id TEXT NOT NULL REFERENCES wh_run(id),
 source TEXT NOT NULL,
 input_sig TEXT NOT NULL,
 program_sig TEXT NOT NULL DEFAULT '',
 mode TEXT NOT NULL,
 reused_run TEXT,
 files TEXT NOT NULL,
 frames TEXT NOT NULL,
 health TEXT NOT NULL DEFAULT '{}',
 seconds REAL NOT NULL DEFAULT 0,
 PRIMARY KEY(run_id,source));
CREATE INDEX IF NOT EXISTS wh_source_load_sig ON wh_source_load(source,input_sig);

-- سوابق ردیف‌های منبع: هر نسخه یک ردیف با بازه اعتبار [from_seq, to_seq)؛ ردیف‌ها فقط بسته می‌شوند
CREATE TABLE IF NOT EXISTS src_frame_state(
 source TEXT NOT NULL,
 frame TEXT NOT NULL,
 key_spec TEXT NOT NULL,
 columns_json TEXT NOT NULL,
 baseline_seq INTEGER NOT NULL,
 last_seq INTEGER NOT NULL,
 last_sha TEXT,
 last_input TEXT NOT NULL DEFAULT '{}',
 rows INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(source,frame));
-- فرهنگ فشرده‌سازی هر فریم (نمونه ردیف‌ها)؛ محتوای هر نسخه با آن فشرده می‌شود و تغییر نمی‌کند
CREATE TABLE IF NOT EXISTS src_zdict(
 id INTEGER PRIMARY KEY,
 source TEXT NOT NULL,
 frame TEXT NOT NULL,
 seq INTEGER NOT NULL,
 data BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS src_zdict_frame ON src_zdict(source,frame,id);
CREATE TABLE IF NOT EXISTS src_record(
 id INTEGER PRIMARY KEY,
 source TEXT NOT NULL,
 frame TEXT NOT NULL,
 rkey TEXT NOT NULL,
 occ INTEGER NOT NULL DEFAULT 0,
 from_seq INTEGER NOT NULL,
 to_seq INTEGER,
 vhash TEXT NOT NULL,
 fhash INTEGER NOT NULL,
 payload BLOB NOT NULL,
 zdict INTEGER REFERENCES src_zdict(id),
 loc TEXT NOT NULL DEFAULT '{}',
 prev_id INTEGER REFERENCES src_record(id),
 UNIQUE(source,frame,rkey,occ,from_seq));
CREATE INDEX IF NOT EXISTS src_record_open ON src_record(source,frame,rkey,occ,fhash,vhash) WHERE to_seq IS NULL;
CREATE INDEX IF NOT EXISTS src_record_closed ON src_record(source,frame,rkey,occ,to_seq) WHERE to_seq IS NOT NULL;
CREATE TABLE IF NOT EXISTS src_change(
 id INTEGER PRIMARY KEY,
 seq INTEGER NOT NULL,
 run_id TEXT NOT NULL,
 source TEXT NOT NULL,
 frame TEXT NOT NULL,
 rkey TEXT,
 occ INTEGER,
 kind TEXT NOT NULL,
 field TEXT,
 old TEXT,
 new TEXT,
 cause TEXT NOT NULL DEFAULT 'data',
 record_id INTEGER);
CREATE INDEX IF NOT EXISTS src_change_seq ON src_change(seq,source,frame,kind);
CREATE INDEX IF NOT EXISTS src_change_key ON src_change(source,frame,rkey,occ);

CREATE TRIGGER IF NOT EXISTS src_record_append_only BEFORE DELETE ON src_record
BEGIN SELECT RAISE(ABORT,'GSI history is append-only: src_record'); END;
-- تنها ویرایش مجاز: بستن یک‌باره نسخه باز (to_seq) و تازه کردن fhash که فقط میان‌بر مقایسه است
CREATE TRIGGER IF NOT EXISTS src_record_close_once BEFORE UPDATE ON src_record
WHEN (OLD.to_seq IS NOT NULL AND (NEW.to_seq IS NOT OLD.to_seq OR NEW.fhash IS NOT OLD.fhash))
  OR (NEW.to_seq IS NOT NULL AND NEW.to_seq <= OLD.from_seq)
  OR NEW.id IS NOT OLD.id OR NEW.source IS NOT OLD.source OR NEW.frame IS NOT OLD.frame
  OR NEW.rkey IS NOT OLD.rkey OR NEW.occ IS NOT OLD.occ OR NEW.from_seq IS NOT OLD.from_seq
  OR NEW.vhash IS NOT OLD.vhash OR NEW.payload IS NOT OLD.payload OR NEW.zdict IS NOT OLD.zdict
  OR NEW.loc IS NOT OLD.loc OR NEW.prev_id IS NOT OLD.prev_id
BEGIN SELECT RAISE(ABORT,'GSI history rows are closed once and never edited: src_record'); END;
CREATE TRIGGER IF NOT EXISTS src_zdict_keep_d BEFORE DELETE ON src_zdict
BEGIN SELECT RAISE(ABORT,'GSI history is append-only: src_zdict'); END;
CREATE TRIGGER IF NOT EXISTS src_zdict_keep_u BEFORE UPDATE ON src_zdict
BEGIN SELECT RAISE(ABORT,'GSI history is append-only: src_zdict'); END;
CREATE TRIGGER IF NOT EXISTS src_change_append_only_d BEFORE DELETE ON src_change
BEGIN SELECT RAISE(ABORT,'GSI change log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS src_change_append_only_u BEFORE UPDATE ON src_change
BEGIN SELECT RAISE(ABORT,'GSI change log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wh_run_keep BEFORE DELETE ON wh_run
BEGIN SELECT RAISE(ABORT,'GSI run history is append-only'); END;

DROP VIEW IF EXISTS wh_source_reconciliation;
CREATE VIEW wh_source_reconciliation AS
SELECT i.id,i.run_id,i.source,i.path,i.file_id,s.name AS sheet,
       json_extract(s.metadata,'$.nonempty_rows') AS nonempty_rows,
       json_extract(s.metadata,'$.stored_rows') AS stored_rows
FROM wh_ingest i JOIN wh_sheet s ON s.file_id=i.file_id;
'''

#: جدول‌هایی که انبار نسخه ۲ بی‌آن‌ها کامل نیست (برای مسیر سریع بازکردن)
CORE_TABLES = frozenset({'wh_meta', 'wh_run', 'wh_object', 'wh_frame', 'wh_current', 'wh_quality_check',
                         'wh_publish_event', 'wh_source_load', 'src_record', 'src_change', 'src_zdict',
                         'dwh_entity'})


def _unlink_with_retry(path, attempts: int = 5, delay: float = 0.15) -> bool:
    """Delete a file, tolerating a briefly-held handle.

    On POSIX the first attempt always succeeds. On Windows a handle that a
    just-closed connection has not yet released makes ``unlink`` raise
    ``PermissionError`` (WinError 32); a short backoff after ``gc.collect()``
    clears the common case, because CPython closes an unreferenced sqlite
    connection in its finalizer. Returns whether the file is gone.
    """
    for attempt in range(attempts):
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            if attempt == attempts - 1:
                return not path.exists()
            gc.collect()
            time.sleep(delay * (attempt + 1))
    return not path.exists()


def _rename_with_retry(src: Path, dst: Path, attempts: int = 6, delay: float = 0.2) -> None:
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            gc.collect()
            time.sleep(delay * (attempt + 1))


def default_data_root() -> Path:
    """Operational data root: ``GSI_DATA_ROOT`` or the documented default.

    ``D:\\GSI_DATA`` is the documented Windows deployment root. On any other OS
    that literal is a *relative* directory name, so a doctor probe or test run
    used to create a folder literally named ``D:\\GSI_DATA`` inside the package
    (and it was later shipped in a release ZIP). Non-Windows hosts use
    ``~/GSI_DATA`` instead; Windows behaviour is unchanged.
    """
    configured = (os.getenv('GSI_DATA_ROOT') or '').strip()
    if configured:
        return Path(configured)
    return Path(r'D:\GSI_DATA') if os.name == 'nt' else Path.home() / 'GSI_DATA'


def _inspect(path: Path):
    """(user_version, tables) of an existing file, read-only; never creates anything."""
    with closing(sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True, timeout=5)) as c:
        c.execute('PRAGMA query_only=ON')
        version = c.execute('PRAGMA user_version').fetchone()[0]
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return version, tables


class Warehouse:
    def __init__(self,path=None,initialize=True):
        default_path = default_data_root() / 'warehouse.sqlite'
        self.path=local_path(path or os.getenv('GSI_DWH_PATH') or default_path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        # IMPORTANT: dashboard readers must never run schema DDL.  Older builds
        # executed CREATE TABLE/PRAGMA user_version in every Warehouse(...)
        # constructor; a lazy Streamlit frame read could therefore compete with
        # the pipeline writer and fail with ``database is locked``.
        if initialize:
            self._ensure_schema()

    # ─────────────────────────── ساختار ───────────────────────────
    @property
    def objects(self) -> ObjectStore:
        return ObjectStore(objects_root(self.path))

    def _ensure_schema(self):
        # Fast path for an already-created v2 warehouse: read-only inspection,
        # no DDL and no transaction. This keeps repeated constructors harmless.
        if self.path.exists() and self.path.stat().st_size:
            try:
                version, existing = _inspect(self.path)
            except sqlite3.OperationalError:
                version, existing = None, None
            if existing is not None:
                if existing and 'wh_meta' not in existing:
                    raise ValueError('فایل انتخابی دیتاورهوس GSI نیست؛ دیتابیس قبلی بازنویسی نمی‌شود.')
                if version == SCHEMA_VERSION and CORE_TABLES.issubset(existing):
                    return
                if version not in (0, 1, SCHEMA_VERSION):
                    raise RuntimeError('Unsupported warehouse schema version')
                if 'wh_meta' in existing and version in (0, 1):
                    self._archive_legacy()
        self._create_schema()

    def _create_schema(self):
        from .business_dwh import BUSINESS_SCHEMA
        from .marts import DDL as MARTS_SCHEMA
        with self.db() as c:
            version=c.execute('PRAGMA user_version').fetchone()[0]
            existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if existing and 'wh_meta' not in existing:
                raise ValueError('فایل انتخابی دیتاورهوس GSI نیست؛ دیتابیس قبلی بازنویسی نمی‌شود.')
            if version not in (0, SCHEMA_VERSION):
                raise RuntimeError('Unsupported warehouse schema version')
            c.executescript(SCHEMA + BUSINESS_SCHEMA + MARTS_SCHEMA)
            c.execute("INSERT OR IGNORE INTO wh_meta VALUES('schema',?)", (str(SCHEMA_VERSION),))
            c.execute("INSERT OR IGNORE INTO wh_meta VALUES('created',?)", (now(),))
            c.execute(f'PRAGMA user_version={SCHEMA_VERSION}')

    def _archive_legacy(self):
        """Keep a v1 warehouse untouched under a new name, then let v2 start clean."""
        from .writer_lock import WriterLock
        with WriterLock(self.path.with_suffix('.writer.lock'), timeout=5,
                        metadata={'operation': 'archive_v1', 'warehouse': str(self.path)}):
            if not self.path.exists():
                return
            version, tables = _inspect(self.path)
            if not ('wh_meta' in tables and version in (0, 1)):
                return
            # A hot rollback journal from an interrupted v1 write must be applied to the
            # file it belongs to before that file moves.
            with closing(sqlite3.connect(self.path, timeout=30)) as c:
                c.execute('SELECT count(*) FROM sqlite_master').fetchone()
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            stem = self.path.stem
            target = self.path.with_name(f'{stem}.v1-archive-{stamp}{self.path.suffix}')
            _rename_with_retry(self.path, target)
            moved = [target.name]
            cache = self.path.with_suffix(self.path.suffix + '.frame_cache')
            if cache.is_dir():
                cache_target = target.with_suffix(target.suffix + '.frame_cache')
                try:
                    _rename_with_retry(cache, cache_target)
                    moved.append(cache_target.name)
                except OSError:
                    pass
            self._legacy_archive = {'archived_to': str(target), 'moved': moved, 'at': now()}
        self._create_schema()
        with self.db() as c:
            c.execute("INSERT OR REPLACE INTO wh_meta VALUES('legacy_v1_archive',?)", (dumps(self._legacy_archive),))
            c.execute('INSERT INTO wh_audit(at,run_id,kind,actor,payload) VALUES(?,?,?,?,?)',
                      (now(), None, 'legacy_v1_archived', 'system', dumps(self._legacy_archive)))

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=30)
        try:
            c.execute('PRAGMA busy_timeout=30000')
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('PRAGMA synchronous=NORMAL')
            c.execute('PRAGMA journal_size_limit=67108864')
            c.execute('PRAGMA foreign_keys=ON')
            with c: yield c
        finally: c.close()

    def schema_version(self):
        if not self.path.exists() or not self.path.stat().st_size:
            return None
        return _inspect(self.path)[0]

    @contextmanager
    def read_db(self, timeout_ms=8000, bind=True):
        """Strict read-only connection for UI/report hydration.

        No schema DDL, no implicit write transaction. With WAL the writer never
        blocks this reader; ``BEGIN`` pins one consistent snapshot for the whole
        block. ``bind=True`` pins every business table to the published run.
        """
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        uri=f'file:{self.path.as_posix()}?mode=ro'
        c=sqlite3.connect(uri, uri=True, timeout=max(0.1, timeout_ms/1000))
        try:
            c.execute(f'PRAGMA busy_timeout={int(timeout_ms)}')
            version=c.execute('PRAGMA user_version').fetchone()[0]
            if version != SCHEMA_VERSION:
                raise LegacyWarehouseError(
                    'انبار داده نسخه جدید هنوز ساخته نشده است؛ یک‌بار «اجرای مجدد خط لوله» یا '
                    'REFRESH_GSI_DATA.cmd را اجرا کنید. انبار قبلی دست‌نخورده بایگانی می‌شود.')
            c.execute('BEGIN')
            if bind:
                from .snapshots import bind_published
                bind_published(c)
            c.execute('PRAGMA query_only=ON')
            c.execute('PRAGMA foreign_keys=ON')
            yield c
        finally:
            c.close()

    # ─────────────────────────── ثبت ───────────────────────────
    def audit(self,kind,payload,actor='operator'):
        with self.db() as c: c.execute('INSERT INTO wh_audit(at,run_id,kind,actor,payload) VALUES(?,?,?,?,?)',(now(),RUN.get(),kind,actor,dumps(payload)))
    def issue(self,code,detail,file_id=None,sheet=None,row=None):
        with self.db() as c: c.execute('INSERT INTO wh_issue(run_id,file_id,sheet,row_no,code,detail) VALUES(?,?,?,?,?,?)',(RUN.get(),file_id,sheet,row,code,dumps(detail)))
    @contextmanager
    def run(self,context):
        from .writer_lock import WriterLock
        lock_meta = {
            'warehouse': str(self.path),
            'operation': str((context or {}).get('operation') or 'pipeline'),
            'context': dict(context or {}),
        }
        with WriterLock(self.path.with_suffix('.writer.lock'), timeout=5, metadata=lock_meta) as lock:
            with self._run(context) as rid:
                lock.update(run_id=rid)
                yield rid

    @contextmanager
    def _run(self,context):
        rid=uuid.uuid4().hex
        with self.db() as c:
            cur=c.execute('INSERT INTO wh_run(id,started,finished,status,context,error) VALUES(?,?,NULL,?,?,NULL)',
                          (rid,now(),'running',dumps(context)))
            seq=cur.lastrowid
        token=RUN.set(rid); seq_token=RUN_SEQ.set(seq)
        try:
            yield rid
        except BaseException as ex:
            with self.db() as c: c.execute('UPDATE wh_run SET status=?,finished=?,error=? WHERE id=?',('failed',now(),str(ex),rid))
            raise
        else:
            with self.db() as c: c.execute('UPDATE wh_run SET status=?,finished=? WHERE id=?',('completed',now(),rid))
        finally:
            RUN.reset(token); RUN_SEQ.reset(seq_token)

    def run_seq(self, rid=None):
        rid = rid or RUN.get()
        if rid is None:
            return None
        if rid == RUN.get() and RUN_SEQ.get() is not None:
            return RUN_SEQ.get()
        with self.db() as c:
            row = c.execute('SELECT seq FROM wh_run WHERE id=?', (rid,)).fetchone()
        return int(row[0]) if row else None

    def record_timings(self, rid, timings):
        with self.db() as c:
            c.execute('UPDATE wh_run SET timings=? WHERE id=?', (dumps(dict(timings)), rid))

    def record_quality(self, rid, checks):
        rows=[]
        for i,ch in enumerate(checks):
            rows.append((rid,i,ch.contract,ch.code,ch.severity,1 if ch.passed else 0,dumps(ch.detail)))
        with self.db() as c:
            c.execute('DELETE FROM wh_quality_check WHERE run_id=?',(rid,))
            c.executemany('INSERT INTO wh_quality_check(run_id,seq,contract,code,severity,passed,detail) VALUES(?,?,?,?,?,?,?)',rows)

    def current_run(self, slot='report'):
        with self.read_db(bind=False) as c:
            row=c.execute('SELECT run_id FROM wh_current WHERE slot=?',(slot,)).fetchone()
        return row[0] if row else None

    def published_frames(self, source, slot='report', layer='standardized'):
        """Return last published standardized frames for one source.

        This is a continuity fallback only. Callers must record that the frame is
        stale; it must never be presented as newly fetched data.
        """
        rid=self.current_run(slot)
        if not rid:
            return {}, None
        prefix=str(source).rstrip('/')+'/'
        with self.read_db(bind=False) as c:
            rows=c.execute('''SELECT id,name FROM wh_frame
                              WHERE run_id=? AND layer=? AND name LIKE ?
                              ORDER BY created DESC''',(rid,layer,prefix+'%')).fetchall()
            run=c.execute('SELECT finished,context FROM wh_run WHERE id=?',(rid,)).fetchone()
        out={}
        seen=set()
        for fid,name in rows:
            frame=name[len(prefix):]
            if frame in seen: continue
            seen.add(frame); out[frame]=self.read_frame(fid)
        meta={'run_id':rid,'finished':run[0] if run else None,'context':loads(run[1]) if run else {}}
        return out,meta

    def publish(self,rid,slots=('report','dwh')):
        """Atomically move all current pointers after a completed, passing run."""
        slots=tuple(dict.fromkeys(slots))
        if not slots: raise ValueError('At least one publish slot is required')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            newer=c.execute("SELECT 1 FROM wh_current p JOIN wh_run old ON old.id=p.run_id JOIN wh_run candidate ON candidate.id=? WHERE old.seq > candidate.seq LIMIT 1",(rid,)).fetchone()
            if newer: raise ValueError('Publication cannot move backwards to an older run')
            if c.execute('SELECT status FROM wh_run WHERE id=?',(rid,)).fetchone()!=('completed',):
                raise ValueError('Only completed runs may be published')
            failed=c.execute("SELECT contract,code FROM wh_quality_check WHERE run_id=? AND severity IN ('BLOCK','CRITICAL','FATAL') AND passed=0",(rid,)).fetchall()
            if failed:
                raise QualityGateBlockedError(rid, failed)
            c.execute("INSERT OR IGNORE INTO wh_schema_baseline SELECT contract,fingerprint,columns_json,updated FROM wh_schema_candidate WHERE run_id=?", (rid,))
            for slot in slots:
                c.execute('INSERT INTO wh_current(slot,run_id) VALUES(?,?) ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id',(slot,rid))
            c.execute('INSERT INTO wh_publish_event(at,run_id,slots) VALUES(?,?,?)',(now(),rid,dumps(list(slots))))

    # ─────────────────────────── بایگانی ───────────────────────────
    def put_object(self, conn, data: bytes, ext: str, kind: str) -> str:
        """بایت‌ها را در پوشه بایگانی می‌گذارد و در همان تراکنش ``conn`` فهرست می‌کند."""
        ext = clean_ext(ext)
        sha = self.objects.put(data, ext)
        conn.execute('INSERT OR IGNORE INTO wh_object(sha,ext,kind,size,created_run,created) VALUES(?,?,?,?,?,?)',
                     (sha, ext, kind, len(data), RUN.get(), now()))
        return sha

    def object_bytes(self, sha: str, conn=None) -> bytes:
        if conn is None:
            with self.read_db(bind=False) as c:
                return self.object_bytes(sha, c)
        row = conn.execute('SELECT ext FROM wh_object WHERE sha=?', (sha,)).fetchone()
        if row is None:
            raise KeyError(sha)
        return self.objects.get(sha, row[0])

    def blob(self,content,name,source,path=''):
        content=bytes(content)
        ext=Path(str(name)).suffix or '.bin'
        with self.db() as c:
            fid=self.put_object(c, content, ext, 'file')
            c.execute('INSERT OR IGNORE INTO wh_file(id,name,size,created) VALUES(?,?,?,?)',(fid,name,len(content),now()))
            previous=c.execute('SELECT file_id FROM wh_ingest WHERE source=? AND path=? ORDER BY id DESC LIMIT 1',
                               (source,str(path))).fetchone()
            change='new' if previous is None else ('same' if previous[0]==fid else 'changed')
            c.execute('INSERT INTO wh_ingest(run_id,source,path,file_id,at,change) VALUES(?,?,?,?,?,?)',
                      (RUN.get(),source,str(path),fid,now(),change))
        return fid

    @staticmethod
    def _frame_meta(df, nbytes):
        from .framecodec import CODEC
        return {'codec':CODEC,'columns':[str(c) for c in df.columns],'dtypes':[str(d) for d in df.dtypes],
                'index_names':[None if n is None else str(n) for n in df.index.names],
                'attrs':sorted(str(k) for k in df.attrs),'bytes':nbytes}

    def frame(self,df,layer,name):
        from .framecodec import encode_frame
        if not df.columns.is_unique: raise ValueError('Duplicate frame columns must be disambiguated before storage')
        data=encode_frame(df)
        fid=uuid.uuid4().hex
        meta=self._frame_meta(df,len(data))
        with self.db() as c:
            sha=self.put_object(c, data, 'parquet', 'frame')
            c.execute('INSERT INTO wh_frame(id,run_id,layer,name,metadata,row_count,created,object_sha) VALUES(?,?,?,?,?,?,?,?)',
                      (fid,RUN.get(),layer,name,dumps(meta),len(df),now(),sha))
        return fid

    def keep_frames(self, layer, frames):
        """``[(name, df)]`` را به‌عنوان فریم‌های این اجرا ثبت می‌کند و ``{name: sha}`` برمی‌گرداند.

        هر فریم از روی همان داده‌ای که در حافظه است رمزگذاری می‌شود، پس بایگانی دقیقاً همان
        چیزی است که مصرف شد. رمزگذاری قطعی است: محتوای یکسان همان اثرانگشت را می‌گیرد و
        بایت تکراری دوباره نوشته نمی‌شود. همه ثبت‌ها در یک تراکنش‌اند.
        """
        from .framecodec import encode_frame
        pending = []
        for name, df in frames:
            if not df.columns.is_unique:
                raise ValueError('Duplicate frame columns must be disambiguated before storage')
            data = encode_frame(df)
            pending.append((str(name), len(df), data, dumps(self._frame_meta(df, len(data)))))
        out = {}
        with self.db() as c:
            for name, rows, data, meta in pending:
                sha = self.put_object(c, data, 'parquet', 'frame')
                c.execute('INSERT INTO wh_frame(id,run_id,layer,name,metadata,row_count,created,object_sha) '
                          'VALUES(?,?,?,?,?,?,?,?)', (uuid.uuid4().hex, RUN.get(), layer, name, meta, rows, now(), sha))
                out[name] = sha
        return out

    def link_frame(self, conn, sha, layer, name, row_count, metadata):
        """Record an already-archived frame object as this run's frame (no bytes written)."""
        fid=uuid.uuid4().hex
        conn.execute('INSERT INTO wh_frame(id,run_id,layer,name,metadata,row_count,created,object_sha) VALUES(?,?,?,?,?,?,?,?)',
                     (fid,RUN.get(),layer,name,metadata,int(row_count),now(),sha))
        return fid

    def read_frame(self,fid):
        from .framecodec import decode_frame
        with self.read_db(bind=False) as c:
            row=c.execute('SELECT object_sha,row_count FROM wh_frame WHERE id=?',(fid,)).fetchone()
        if row is None: raise KeyError(fid)
        df=decode_frame(self.objects.get(row[0],'parquet'))
        if len(df)!=row[1]: raise RuntimeError('Warehouse row count mismatch')
        return df

    # ─────────────────────────── نگهداری ───────────────────────────
    def checkpoint(self):
        """Fold the WAL back into the main file after a refresh (best effort)."""
        try:
            with closing(sqlite3.connect(self.path, timeout=5)) as c:
                c.execute('PRAGMA busy_timeout=5000')
                return c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        except sqlite3.Error:
            return None

    def reset(self, *, confirm=False, backup_to=None, keep_backup=True):
        """Reset exclusively; the stable OS lock file is retained to avoid inode races."""
        if not confirm:
            raise ValueError('reset نیازمند confirm=True است؛ حذف انبار داده پیش‌فرض نیست.')
        from .writer_lock import WriterLock
        with WriterLock(self.path.with_suffix('.writer.lock'), timeout=0.5,
                        metadata={'operation':'reset','warehouse':str(self.path)}):
            return self._reset_locked(backup_to=backup_to, keep_backup=keep_backup)

    def _reset_locked(self, *, backup_to=None, keep_backup=True):
        """پاک‌کردن فهرست‌های انبار داده و ساخت دوبارهٔ آن از صفر.

        قواعد ایمنی — هر سه عمدی‌اند:
          * ``confirm=True`` اجباری است. حذف داده هرگز پیش‌فرض نیست.
          * اگر فایل، انبار دادهٔ GSI نباشد، هیچ چیز پاک نمی‌شود.
          * پیش از حذف، یک نسخهٔ پشتیبان (همراه شیءهای بایگانی) ساخته می‌شود مگر صریحاً رد شود.

        پوشه بایگانی با اثرانگشت دست نمی‌خورد: شیءها تغییرناپذیرند، پشتیبان به آن‌ها
        اشاره می‌کند و انبار تازه محتوای تکراری را دوباره نمی‌نویسد.
        """
        report={'path':str(self.path),'existed':self.path.exists(),'backup':None,'removed':[],'objects_kept':True}
        if self.path.exists() and self.path.stat().st_size:
            # نگذار یک فایل غیر-GSI با این دستور نابود شود.
            version, tables = _inspect(self.path)
            if tables and 'wh_meta' not in tables:
                raise ValueError('فایل انتخابی دیتاورهوس GSI نیست؛ پاک نمی‌شود.')
            if keep_backup:
                dest=local_path(backup_to) if backup_to else self.path.with_suffix(
                    self.path.suffix+f'.{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.bak')
                report['backup']=str(self.backup(dest))
        cache=self.path.with_suffix(self.path.suffix+'.frame_cache')
        for extra in (self.path,
                      self.path.with_suffix(self.path.suffix+'-wal'),
                      self.path.with_suffix(self.path.suffix+'-shm')):
            # Never unlink WAL/SHM if the database survived: SQLite owns them.
            if extra != self.path and self.path.exists(): continue
            if not extra.exists(): continue
            if _unlink_with_retry(extra): report['removed'].append(extra.name)
            else: report.setdefault('undeleted',[]).append(extra.name)
        if cache.is_dir():
            shutil.rmtree(cache,ignore_errors=True)
            if not cache.exists(): report['removed'].append(cache.name+'/')
            else: report.setdefault('undeleted',[]).append(cache.name+'/')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.exists():
            # Windows refuses to delete a file any process still has open, and a
            # real run reported exactly that (WinError 32) from this method. The
            # contract of reset is "the warehouse is empty", not "the inode is
            # gone", so when the file survives, empty it in place through SQL.
            self._drop_all_objects()
            report['emptied_in_place']=True
        self._create_schema()
        report['writer_lock_retained']=True
        report['recreated']=True
        self.audit('warehouse_reset',report)
        return report

    def _drop_all_objects(self):
        """Empty an existing warehouse file without deleting it."""
        with self.db() as c:
            c.execute('PRAGMA foreign_keys=OFF')
            c.execute('BEGIN IMMEDIATE')
            objs=c.execute("SELECT type,name FROM sqlite_master "
                           "WHERE name NOT LIKE 'sqlite_%'").fetchall()
            for kind,name in objs:
                if kind in ('table','view','index','trigger'):
                    c.execute(f'DROP {kind.upper()} IF EXISTS "' + name.replace('"', '""') + '"')
            c.execute('PRAGMA user_version=0')
        with self.db() as c:
            c.execute('VACUUM')

    def backup(self,path):
        """Consistent copy of the SQLite file plus every archived object it names.

        Objects go to ``<dest>.objects`` as hard links when the disk allows (they are
        immutable), otherwise as copies.
        """
        dest=local_path(path)
        if dest==self.path or dest.exists(): raise ValueError('Backup destination must be a new local file')
        dest.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as c:
            target=sqlite3.connect(dest)
            try: c.backup(target)
            finally: target.close()
            try:
                objects=c.execute('SELECT sha,ext FROM wh_object').fetchall()
            except sqlite3.OperationalError:
                objects=[]
        store=self.objects
        other=ObjectStore(objects_root(dest))
        for sha,ext in objects:
            if store.exists(sha,ext):
                store.link_or_copy(sha,ext,other)
        return dest

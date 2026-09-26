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

RUN = contextvars.ContextVar('warehouse_run', default=None)

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
def now(): return datetime.now(timezone.utc).isoformat()
def encode(x):
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
CREATE TABLE IF NOT EXISTS wh_run(id TEXT PRIMARY KEY,started TEXT NOT NULL,finished TEXT,status TEXT NOT NULL,context TEXT NOT NULL,error TEXT);
CREATE TABLE IF NOT EXISTS wh_audit(id INTEGER PRIMARY KEY,at TEXT NOT NULL,run_id TEXT,kind TEXT NOT NULL,actor TEXT NOT NULL,payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS wh_audit_run ON wh_audit(run_id,id);
CREATE TABLE IF NOT EXISTS wh_file(id TEXT PRIMARY KEY,name TEXT NOT NULL,content BLOB NOT NULL,size INTEGER NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_ingest(id INTEGER PRIMARY KEY,run_id TEXT,source TEXT NOT NULL,path TEXT NOT NULL,file_id TEXT NOT NULL REFERENCES wh_file(id),at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_sheet(file_id TEXT NOT NULL REFERENCES wh_file(id),name TEXT NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(file_id,name));
CREATE TABLE IF NOT EXISTS wh_raw_row(file_id TEXT NOT NULL,sheet TEXT NOT NULL,row_no INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(file_id,sheet,row_no),FOREIGN KEY(file_id,sheet) REFERENCES wh_sheet(file_id,name));
CREATE TABLE IF NOT EXISTS wh_issue(id INTEGER PRIMARY KEY,run_id TEXT,file_id TEXT,sheet TEXT,row_no INTEGER,code TEXT NOT NULL,detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wh_frame(id TEXT PRIMARY KEY,run_id TEXT REFERENCES wh_run(id),layer TEXT NOT NULL,name TEXT NOT NULL,metadata TEXT NOT NULL,row_count INTEGER NOT NULL,created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS wh_frame_run ON wh_frame(run_id,layer,name);
CREATE TABLE IF NOT EXISTS wh_frame_row(frame_id TEXT NOT NULL REFERENCES wh_frame(id),row_no INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(frame_id,row_no));
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
CREATE TABLE IF NOT EXISTS wh_publish_event(
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES wh_run(id), slots TEXT NOT NULL);
CREATE VIEW IF NOT EXISTS wh_source_reconciliation AS SELECT i.id,i.run_id,i.source,i.path,i.file_id,s.name AS sheet,json_extract(s.metadata,'$.nonempty_rows') AS nonempty_rows,(SELECT count(*) FROM wh_raw_row r WHERE r.file_id=s.file_id AND r.sheet=s.name) AS stored_rows FROM wh_ingest i JOIN wh_sheet s ON s.file_id=i.file_id;
'''
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


class Warehouse:
    def __init__(self,path=None,initialize=True):
        default_path = Path(os.getenv('GSI_DATA_ROOT', r'D:\GSI_DATA')) / 'warehouse.sqlite'
        self.path=local_path(path or os.getenv('GSI_DWH_PATH') or default_path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        # IMPORTANT: dashboard readers must never run schema DDL.  Older builds
        # executed CREATE TABLE/PRAGMA user_version in every Warehouse(...)
        # constructor; a lazy Streamlit frame read could therefore compete with
        # the pipeline writer and fail with ``database is locked``.
        if initialize:
            self._ensure_schema()

    def _ensure_schema(self):
        # Fast path for an already-created GSI warehouse: read-only inspection,
        # no DDL and no transaction. This keeps repeated constructors harmless.
        if self.path.exists() and self.path.stat().st_size:
            try:
                with closing(sqlite3.connect(f'file:{self.path.as_posix()}?mode=ro', uri=True, timeout=5)) as c:
                    c.execute('PRAGMA query_only=ON')
                    version=c.execute('PRAGMA user_version').fetchone()[0]
                    existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if version not in (0,1):
                    raise RuntimeError('Unsupported warehouse schema version')
                if existing and 'wh_meta' not in existing:
                    raise ValueError('فایل انتخابی دیتاورهوس GSI نیست؛ دیتابیس قبلی بازنویسی نمی‌شود.')
                if 'wh_meta' in existing and version==1 and {'wh_quality_check','wh_schema_baseline','wh_publish_event'}.issubset(existing):
                    return
            except sqlite3.OperationalError:
                # Initialization callers may legitimately race a writer. Use the
                # normal busy timeout below instead of turning a transient lock
                # into a schema/format diagnosis.
                pass
        with self.db() as c:
            version=c.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1): raise RuntimeError('Unsupported warehouse schema version')
            existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if existing and 'wh_meta' not in existing: raise ValueError('فایل انتخابی دیتاورهوس GSI نیست؛ دیتابیس قبلی بازنویسی نمی‌شود.')
            c.executescript(SCHEMA)
            c.execute("INSERT OR IGNORE INTO wh_meta VALUES('schema','1')")
            c.execute('PRAGMA user_version=1')

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=30)
        try:
            c.execute('PRAGMA busy_timeout=30000')
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA synchronous=FULL')
            with c: yield c
        finally: c.close()

    @contextmanager
    def read_db(self, timeout_ms=8000):
        """Strict read-only connection for UI/report hydration.

        No schema DDL, no implicit write transaction, and bounded waiting for a
        short writer transaction.  This is intentionally separate from ``db``.
        """
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        uri=f'file:{self.path.as_posix()}?mode=ro'
        c=sqlite3.connect(uri, uri=True, timeout=max(0.1, timeout_ms/1000))
        try:
            c.execute(f'PRAGMA busy_timeout={int(timeout_ms)}')
            c.execute('BEGIN')
            from .snapshots import bind_published
            bind_published(c)
            c.execute('PRAGMA query_only=ON')
            c.execute('PRAGMA foreign_keys=ON')
            yield c
        finally:
            c.close()
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
        with self.db() as c: c.execute('INSERT INTO wh_run VALUES(?,?,NULL,?,?,NULL)',(rid,now(),'running',dumps(context)))
        token=RUN.set(rid)
        try:
            yield rid
        except BaseException as ex:
            with self.db() as c: c.execute('UPDATE wh_run SET status=?,finished=?,error=? WHERE id=?',('failed',now(),str(ex),rid))
            raise
        else:
            with self.db() as c: c.execute('UPDATE wh_run SET status=?,finished=? WHERE id=?',('completed',now(),rid))
        finally: RUN.reset(token)
    def record_quality(self, rid, checks):
        rows=[]
        for i,ch in enumerate(checks):
            rows.append((rid,i,ch.contract,ch.code,ch.severity,1 if ch.passed else 0,dumps(ch.detail)))
        with self.db() as c:
            c.execute('DELETE FROM wh_quality_check WHERE run_id=?',(rid,))
            c.executemany('INSERT INTO wh_quality_check(run_id,seq,contract,code,severity,passed,detail) VALUES(?,?,?,?,?,?,?)',rows)

    def current_run(self, slot='report'):
        with self.read_db() as c:
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
        with self.read_db() as c:
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
            newer=c.execute("SELECT 1 FROM wh_current p JOIN wh_run old ON old.id=p.run_id JOIN wh_run candidate ON candidate.id=? WHERE old.started > candidate.started LIMIT 1",(rid,)).fetchone()
            if newer: raise ValueError('Publication cannot move backwards to an older run')
            if c.execute('SELECT status FROM wh_run WHERE id=?',(rid,)).fetchone()!=('completed',):
                raise ValueError('Only completed runs may be published')
            failed=c.execute("SELECT contract,code FROM wh_quality_check WHERE run_id=? AND severity IN ('BLOCK','CRITICAL','FATAL') AND passed=0",(rid,)).fetchall()
            if failed:
                raise QualityGateBlockedError(rid, failed)
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='wh_schema_candidate'").fetchone():
                c.execute("INSERT OR IGNORE INTO wh_schema_baseline SELECT contract,fingerprint,columns_json,updated FROM wh_schema_candidate WHERE run_id=?", (rid,))
            for slot in slots:
                c.execute('INSERT INTO wh_current(slot,run_id) VALUES(?,?) ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id',(slot,rid))
            c.execute('INSERT INTO wh_publish_event(at,run_id,slots) VALUES(?,?,?)',(now(),rid,dumps(list(slots))))
    def blob(self,content,name,source,path=''):
        fid=hashlib.sha256(content).hexdigest()
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO wh_file VALUES(?,?,?,?,?)',(fid,name,content,len(content),now()))
            c.execute('INSERT INTO wh_ingest(run_id,source,path,file_id,at) VALUES(?,?,?,?,?)',(RUN.get(),source,path,fid,now()))
        return fid
    def _frame_cache_path(self,fid):
        # Disposable local acceleration cache. SQLite remains the source of truth.
        root=self.path.with_suffix(self.path.suffix+'.frame_cache')
        return root/(str(fid)+'.pkl')

    def _write_frame_cache(self,fid,df):
        if os.environ.get('GSI_FRAME_CACHE','1').strip().lower() in ('0','false','no','off'):
            return
        path=self._frame_cache_path(fid)
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            tmp=path.with_suffix('.tmp')
            df.to_pickle(tmp,protocol=5)
            os.replace(tmp,path)
        except Exception:
            # Cache failure must never affect the transactional warehouse.
            try:
                if tmp.exists(): tmp.unlink()
            except Exception:
                pass

    def frame(self,df,layer,name):
        if not df.columns.is_unique: raise ValueError('Duplicate frame columns must be disambiguated before storage')
        fid=uuid.uuid4().hex
        meta={'columns':list(df.columns),'dtypes':[str(d) for d in df.dtypes],'index':list(df.index),'index_name':df.index.name,'index_dtype':str(df.index.dtype),'attrs':dict(df.attrs)}

        # Do not materialize the serialized form of an entire wide mart in RAM.
        # On the production-scale report (hundreds of thousands of rows and
        # hundreds of columns) the old ``rows=[...]`` temporarily duplicated the
        # DataFrame as Python tuples + JSON strings before SQLite saw the first
        # row.  Chunking changes only the write shape; the same row_no/payload
        # contract and one atomic transaction are preserved.
        try:
            chunk_rows=max(1,int(os.environ.get('GSI_WAREHOUSE_FRAME_CHUNK_ROWS','1000')))
        except (TypeError,ValueError):
            chunk_rows=1000
        iterator=enumerate(df.itertuples(index=False,name=None))
        with self.db() as c:
            c.execute('INSERT INTO wh_frame VALUES(?,?,?,?,?,?,?)',(fid,RUN.get(),layer,name,dumps(meta),len(df),now()))
            batch=[]
            for i,row in iterator:
                batch.append((fid,i,dumps(list(row))))
                if len(batch)>=chunk_rows:
                    c.executemany('INSERT INTO wh_frame_row VALUES(?,?,?)',batch)
                    batch.clear()
            if batch:
                c.executemany('INSERT INTO wh_frame_row VALUES(?,?,?)',batch)
        # Write the already-in-memory frame once for fast UI rehydration. This is
        # disposable; all auditability and reconstruction still come from SQLite.
        self._write_frame_cache(fid,df)
        return fid
    def _read_cached_frame(self, fid):
        """Best-effort local cache read requiring no SQLite connection."""
        import pandas as pd
        cache=self._frame_cache_path(fid)
        if not cache.exists():
            return None
        try:
            df=pd.read_pickle(cache)
            return df if isinstance(df,pd.DataFrame) else None
        except Exception:
            try: cache.unlink(missing_ok=True)
            except Exception: pass
            return None

    def read_frame(self,fid):
        import pandas as pd
        # The frame id itself comes from the published SQLite snapshot.  A valid
        # local cache can therefore satisfy a Streamlit lazy read without touching
        # the database at all -- crucial while a writer is committing another mart.
        cached=self._read_cached_frame(fid)
        if cached is not None:
            return cached
        with self.read_db() as c:
            row=c.execute('SELECT metadata,row_count FROM wh_frame WHERE id=?',(fid,)).fetchone()
            if row is None: raise KeyError(fid)
            meta=loads(row[0]); expected_rows=row[1]
            data=[loads(r[0]) for r in c.execute('SELECT payload FROM wh_frame_row WHERE frame_id=? ORDER BY row_no',(fid,))]
        if len(data)!=expected_rows: raise RuntimeError('Warehouse row count mismatch')
        df=pd.DataFrame(data,columns=meta['columns'],index=pd.Index(meta['index'],dtype=meta.get('index_dtype')));df.index.name=meta['index_name']
        for col,dtype in zip(meta['columns'],meta['dtypes']): df[col]=df[col].astype(dtype)
        df.attrs.update(meta.get('attrs', {}))
        self._write_frame_cache(fid,df)
        return df
    def reset(self, *, confirm=False, backup_to=None, keep_backup=True):
        """Reset exclusively; the stable OS lock file is retained to avoid inode races."""
        if not confirm:
            raise ValueError('reset نیازمند confirm=True است؛ حذف انبار داده پیش‌فرض نیست.')
        from .writer_lock import WriterLock
        with WriterLock(self.path.with_suffix('.writer.lock'), timeout=0.5,
                        metadata={'operation':'reset','warehouse':str(self.path)}):
            return self._reset_locked(backup_to=backup_to, keep_backup=keep_backup)

    def _reset_locked(self, *, backup_to=None, keep_backup=True):
        """پاک‌کردن کامل انبار داده و ساخت دوبارهٔ آن از صفر.

        چرا این متد لازم است: تا پیش از این هیچ مسیر پشتیبانی‌شده‌ای برای
        «از اول ساختن» وجود نداشت و تنها راه، پاک‌کردن دستی فایل بود. پاک‌کردن
        دستی سه چیز را جا می‌گذارد که بعداً به شکل خطای گمراه‌کننده برمی‌گردند:
        کش فریم‌ها و وضعیت قفل نویسنده. فایل قفل پایدار نگه داشته می‌شود؛
        قفل سیستم‌عامل پس از پایان عملیات آزاد می‌شود.

        قواعد ایمنی — هر سه عمدی‌اند:
          * ``confirm=True`` اجباری است. حذف داده هرگز پیش‌فرض نیست.
          * اگر فایل، انبار دادهٔ GSI نباشد، هیچ چیز پاک نمی‌شود.
          * پیش از حذف، یک نسخهٔ پشتیبان ساخته می‌شود مگر صریحاً رد شود.

        خروجی: گزارشی از آنچه واقعاً حذف شد، برای ثبت در سابقه.
        """
        report={'path':str(self.path),'existed':self.path.exists(),'backup':None,'removed':[]}
        if self.path.exists() and self.path.stat().st_size:
            # نگذار یک فایل غیر-GSI با این دستور نابود شود.
            with closing(sqlite3.connect(f'file:{self.path.as_posix()}?mode=ro',uri=True,timeout=5)) as c:
                c.execute('PRAGMA query_only=ON')
                tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and 'wh_meta' not in tables:
                raise ValueError('فایل انتخابی دیتاورهوس GSI نیست؛ پاک نمی‌شود.')
            if keep_backup:
                dest=local_path(backup_to) if backup_to else self.path.with_suffix(
                    self.path.suffix+f'.{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.bak')
                report['backup']=str(self.backup(dest))
        cache=self.path.with_suffix(self.path.suffix+'.frame_cache')
        lock=self.path.with_suffix('.writer.lock')
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
        self._ensure_schema()
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
        dest=local_path(path)
        if dest==self.path or dest.exists(): raise ValueError('Backup destination must be a new local file')
        dest.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as c:
            target=sqlite3.connect(dest)
            try: c.backup(target)
            finally: target.close()
        return dest

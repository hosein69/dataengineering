from __future__ import annotations
import contextvars
import hashlib
import json
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

RUN = contextvars.ContextVar('warehouse_run', default=None)
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
CREATE VIEW IF NOT EXISTS wh_source_reconciliation AS SELECT i.id,i.run_id,i.source,i.path,i.file_id,s.name AS sheet,json_extract(s.metadata,'$.nonempty_rows') AS nonempty_rows,(SELECT count(*) FROM wh_raw_row r WHERE r.file_id=s.file_id AND r.sheet=s.name) AS stored_rows FROM wh_ingest i JOIN wh_sheet s ON s.file_id=i.file_id;
'''
class Warehouse:
    def __init__(self,path=None):
        self.path=local_path(path or os.getenv('GSI_DWH_PATH') or Path(os.getenv('LOCALAPPDATA',str(Path.home()/'.gsi')))/'GSI'/'warehouse.sqlite')
        self.path.parent.mkdir(parents=True,exist_ok=True)
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
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA synchronous=FULL')
            with c: yield c
        finally: c.close()
    def audit(self,kind,payload,actor='operator'):
        with self.db() as c: c.execute('INSERT INTO wh_audit(at,run_id,kind,actor,payload) VALUES(?,?,?,?,?)',(now(),RUN.get(),kind,actor,dumps(payload)))
    def issue(self,code,detail,file_id=None,sheet=None,row=None):
        with self.db() as c: c.execute('INSERT INTO wh_issue(run_id,file_id,sheet,row_no,code,detail) VALUES(?,?,?,?,?,?)',(RUN.get(),file_id,sheet,row,code,dumps(detail)))
    @contextmanager
    def run(self,context):
        from .writer_lock import WriterLock
        with WriterLock(self.path.with_suffix('.writer.lock'),timeout=5):
            with self._run(context) as rid: yield rid

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
    def publish(self,rid):
        with self.db() as c:
            if c.execute('SELECT status FROM wh_run WHERE id=?',(rid,)).fetchone()!=('completed',): raise ValueError('Only completed runs may be published')
            c.execute("INSERT INTO wh_current VALUES('report',?) ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id",(rid,))
    def blob(self,content,name,source,path=''):
        fid=hashlib.sha256(content).hexdigest()
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO wh_file VALUES(?,?,?,?,?)',(fid,name,content,len(content),now()))
            c.execute('INSERT INTO wh_ingest(run_id,source,path,file_id,at) VALUES(?,?,?,?,?)',(RUN.get(),source,path,fid,now()))
        return fid
    def frame(self,df,layer,name):
        if not df.columns.is_unique: raise ValueError('Duplicate frame columns must be disambiguated before storage')
        fid=uuid.uuid4().hex
        meta={'columns':list(df.columns),'dtypes':[str(d) for d in df.dtypes],'index':list(df.index),'index_name':df.index.name,'index_dtype':str(df.index.dtype)}
        rows=[(fid,i,dumps(list(row))) for i,row in enumerate(df.itertuples(index=False,name=None))]
        with self.db() as c:
            c.execute('INSERT INTO wh_frame VALUES(?,?,?,?,?,?,?)',(fid,RUN.get(),layer,name,dumps(meta),len(df),now()))
            c.executemany('INSERT INTO wh_frame_row VALUES(?,?,?)',rows)
        return fid
    def read_frame(self,fid):
        import pandas as pd
        with self.db() as c:
            row=c.execute('SELECT metadata,row_count FROM wh_frame WHERE id=?',(fid,)).fetchone()
            if row is None: raise KeyError(fid)
            meta=loads(row[0]); data=[loads(r[0]) for r in c.execute('SELECT payload FROM wh_frame_row WHERE frame_id=? ORDER BY row_no',(fid,))]
        if len(data)!=row[1]: raise RuntimeError('Warehouse row count mismatch')
        df=pd.DataFrame(data,columns=meta['columns'],index=pd.Index(meta['index'],dtype=meta.get('index_dtype')));df.index.name=meta['index_name']
        for col,dtype in zip(meta['columns'],meta['dtypes']): df[col]=df[col].astype(dtype)
        return df
    def backup(self,path):
        dest=local_path(path)
        if dest==self.path or dest.exists(): raise ValueError('Backup destination must be a new local file')
        dest.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as c:
            target=sqlite3.connect(dest)
            try: c.backup(target)
            finally: target.close()
        return dest

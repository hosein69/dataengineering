# -*- coding: utf-8 -*-
"""سوابق ردیف‌های منبع و دفتر تغییرات؛ فقط افزودنی، هیچ ردیفی پاک یا بازنویسی نمی‌شود.

هر فریم استاندارد هر سورس (خروجی adapter) در هر اجرا با آخرین وضعیتش مقایسه می‌شود:

* ``src_record``: هر نسخه از هر ردیف یک ردیف با بازه ``[from_seq, to_seq)``. نسخه‌ای که عوض
  شود یا دیگر دیده نشود فقط «بسته» می‌شود و نسخه تازه کنارش می‌نشیند (``prev_id``).
* ``src_change``: دفتر تغییرات. برای هر ردیف یک رویداد (``field`` خالی) و برای ردیف
  تغییرکرده یک سطر به ازای هر فیلد با مقدار قبلی و جدید.
  kind: baseline، new، changed، gone، back، schema، rekey.
  cause: data (فایل عوض شد)، program (فقط برنامه یا تنظیمات)، data+program، unknown.
* ``src_frame_state``: آخرین وضعیت هر فریم تا فریم بی‌تغییر بدون باز شدن رد شود.

کلید ردیف‌ها از ``config/source_keys.yaml`` می‌آید. ردیف‌های هم‌کلید اول با محتوای یکسان و
بعد به ترتیب جفت می‌شوند؛ فریم بی‌کلید با خود محتوا شناخته می‌شود.

محتوای هر ردیف «متعارف» ذخیره می‌شود: خانه خالی، NaN و None یکی‌اند و 5.0 همان 5 است، تا
عوض شدن نوع ستون یا شکل خالی‌ها تغییر داده حساب نشود. فریم دقیق هر اجرا جدا و بی‌تغییر در
بایگانی Parquet می‌ماند؛ این سوابق برای «چه چیزی، کِی، از چه به چه» است.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

#: نسخه قواعد متعارف‌سازی و مقایسه. عوض شدنش همه ردیف‌ها را یک‌بار دوباره می‌سنجد، بدون
#: ثبت تغییر ساختگی.
CANON = 1
KEYS_YAML = Path(__file__).resolve().parents[1] / 'config' / 'source_keys.yaml'

_JSON = dict(ensure_ascii=False, separators=(',', ':'), allow_nan=False)
_BIG = 2 ** 53
_CHUNK = 400


# ─────────────────────────── کلیدها ───────────────────────────
@dataclass(frozen=True)
class FrameSpec:
    keys: Tuple[str, ...] = ()
    location: Tuple[str, ...] = ()
    role: str = 'rows'
    label: str = ''

    def key_spec(self, columns) -> dict:
        cols = set(columns)
        if self.keys and all(k in cols for k in self.keys):
            return {'canon': CANON, 'mode': 'keys', 'keys': list(self.keys)}
        return {'canon': CANON, 'mode': 'content'}


@dataclass(frozen=True)
class Specs:
    location: Tuple[str, ...] = ()
    frames: Dict[str, FrameSpec] = field(default_factory=dict)

    def get(self, name: str) -> FrameSpec:
        return self.frames.get(name) or FrameSpec((), self.location, 'rows', name)


def load_specs(path=None) -> Specs:
    import yaml
    p = Path(path) if path else KEYS_YAML
    raw = (yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else None) or {}
    base = tuple(str(c) for c in ((raw.get('defaults') or {}).get('location') or ()))
    frames = {}
    for name, item in (raw.get('frames') or {}).items():
        item = item or {}
        loc = tuple(dict.fromkeys(base + tuple(str(c) for c in (item.get('location') or ()))))
        frames[str(name)] = FrameSpec(tuple(str(k) for k in (item.get('keys') or ())), loc,
                                      str(item.get('role') or 'rows'), str(item.get('label') or name))
    return Specs(base, frames)


# ─────────────────────────── مقدار متعارف ───────────────────────────
def _canon_float(f: float):
    if f != f:
        return None
    if f == math.inf or f == -math.inf:
        return {'$f': 'inf' if f > 0 else '-inf'}
    if f.is_integer() and abs(f) < _BIG:
        return int(f)
    return f


def canon(v):
    """مقدار JSON-پذیر متعارف یک خانه؛ ``None`` یعنی خالی."""
    t = type(v)
    if t is str:
        return v if v.strip() else None
    if v is None:
        return None
    if t is int or t is bool:
        return v
    if t is float:
        return _canon_float(v)
    return _canon_other(v)


def _canon_other(v):
    if v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return _canon_float(float(v))
    if isinstance(v, str):
        s = str(v)
        return s if s.strip() else None
    if isinstance(v, np.datetime64):
        if np.isnat(v):
            return None
        v = pd.Timestamp(v)
    if isinstance(v, datetime):
        return {'$t': v.isoformat()}
    if isinstance(v, date):
        return {'$d': v.isoformat()}
    if isinstance(v, dtime):
        return {'$tm': v.isoformat()}
    if isinstance(v, np.timedelta64):
        if np.isnat(v):
            return None
        v = pd.Timedelta(v)
    if isinstance(v, timedelta):
        return {'$td': pd.Timedelta(v).isoformat()}
    if isinstance(v, Decimal):
        if v.is_nan():
            return None
        return {'$dec': str(v)}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {'$b': bytes(v).hex()}
    if isinstance(v, dict):
        return {str(k): canon(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [canon(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted((canon(x) for x in v), key=lambda x: json.dumps(x, **_JSON))
    return {'$x': type(v).__name__, 'v': str(v)}


def _canon_column(s: pd.Series) -> list:
    dt = s.dtype
    if isinstance(dt, np.dtype):
        kind = dt.kind
        if kind in 'biu':
            return s.to_numpy().tolist()
        if kind == 'f':
            arr = s.to_numpy(dtype=np.float64)
            out = arr.tolist()
            finite = np.isfinite(arr)
            integral = finite & (np.floor(arr) == arr) & (np.abs(arr) < _BIG)
            if integral.any():
                for i, v in zip(np.flatnonzero(integral).tolist(), arr[integral].astype(np.int64).tolist()):
                    out[i] = v
            odd = ~finite
            if odd.any():
                for i in np.flatnonzero(odd).tolist():
                    out[i] = _canon_float(out[i])
            return out
    return [canon(v) for v in s.tolist()]


def _dump(x) -> str:
    return json.dumps(x, **_JSON)


def _row_payloads(df: pd.DataFrame, cols: Sequence[str], rows=None) -> List[str]:
    """متن JSON متعارف ردیف‌ها (فقط خانه‌های پر، به ترتیب نام ستون)."""
    sub = df if rows is None else df.iloc[list(rows)]
    if not len(sub):
        return []
    if not cols:
        return ['{}'] * len(sub)
    lists = [_canon_column(sub[c]) for c in cols]
    names = list(cols)
    dumps = json.JSONEncoder(**_JSON).encode
    return [dumps({n: v for n, v in zip(names, values) if v is not None}) for values in zip(*lists)]


def _vhash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


_ZDICT_MAX = 32768
_ZDICT_ROWS = 256


def _pack(text: str, primed=None) -> bytes:
    """محتوای یک نسخه: فشرده با فرهنگ فریم (d)، فشرده ساده (z) یا خام (j)، هرکدام کوتاه‌تر."""
    raw = text.encode('utf-8')
    if primed is not None:
        co = primed.copy()
        z, tag = co.compress(raw) + co.flush(), b'd'
    else:
        z, tag = zlib.compress(raw, 6), b'z'
    return tag + z if len(z) + 1 < len(raw) else b'j' + raw


def unpack(blob, zdict: Optional[bytes] = None) -> dict:
    """محتوای یک نسخه از ``src_record.payload`` (با فرهنگ ``src_zdict`` همان ردیف، اگر دارد)."""
    blob = bytes(blob)
    tag, body = blob[:1], blob[1:]
    if tag == b'd':
        if zdict is None:
            raise ValueError('GSI history payload needs its compression dictionary')
        d = zlib.decompressobj(zdict=zdict)
        body = d.decompress(body) + d.flush()
    elif tag == b'z':
        body = zlib.decompress(body)
    elif tag != b'j':
        raise ValueError('Unknown GSI history payload encoding')
    return json.loads(body.decode('utf-8'))


def _build_zdict(texts: Sequence[str]) -> bytes:
    """نمونه‌ای یکنواخت از ردیف‌ها؛ zlib انتهای فرهنگ را ارزان‌تر ارجاع می‌دهد."""
    n = len(texts)
    if not n:
        return b''
    step = max(1, n // _ZDICT_ROWS)
    sample = '\n'.join(texts[i] for i in range(0, n, step)).encode('utf-8')
    return sample[-_ZDICT_MAX:]


def _primed(zdict: bytes):
    return zlib.compressobj(6, zlib.DEFLATED, 15, 9, zlib.Z_DEFAULT_STRATEGY, zdict)


class PayloadReader:
    """خواندن محتوای نسخه‌ها با نگه‌داشتن فرهنگ‌های فشرده‌سازی در حافظه."""

    def __init__(self, conn):
        self.conn = conn
        self.cache: Dict[int, bytes] = {}

    def zdict(self, zid):
        if zid is None:
            return None
        data = self.cache.get(zid)
        if data is None:
            row = self.conn.execute('SELECT data FROM src_zdict WHERE id=?', (zid,)).fetchone()
            if row is None:
                raise KeyError(f'src_zdict {zid}')
            data = self.cache[zid] = bytes(row[0])
        return data

    def unpack(self, blob, zid) -> dict:
        return unpack(blob, self.zdict(zid))


def _fast_hashes(df: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    """اثرانگشت سریع هر ردیف (فقط میان‌بر مقایسه؛ برابر بودنش یعنی محتوای برابر)."""
    n = len(df)
    if not cols or not n:
        return np.zeros(n, dtype=np.int64)
    parts = {}
    for i, c in enumerate(cols):
        s = df[c]
        if s.dtype == object:
            vals = s.to_numpy()
            mask = pd.isna(vals)
            types = set(map(type, vals[~mask])) if (~mask).any() else set()
            if types and not types <= {str}:
                # ستون چندنوعی: نوع هم در اثرانگشت می‌آید تا 1 و "1" یکی نشوند.
                vals = np.array([None if m else f'{type(v).__name__}\x1f{v!r}' for v, m in zip(vals, mask)],
                                dtype=object)
            parts[i] = vals
        else:
            parts[i] = s.to_numpy() if isinstance(s.dtype, np.dtype) else s.array
    frame = pd.DataFrame(parts, index=pd.RangeIndex(n), copy=False)
    return pd.util.hash_pandas_object(frame, index=False).to_numpy().view(np.int64)


def _base_keys(df: pd.DataFrame, keys: Sequence[str]) -> List[str]:
    lists = [_canon_column(df[k]) for k in keys]
    enc = json.JSONEncoder(**_JSON).encode
    return [enc(list(vals)) for vals in zip(*lists)]


def _content_base(vhash: str) -> str:
    return 'c:' + vhash[:24]


def _locations(df: pd.DataFrame, cols: Sequence[str], rows) -> List[str]:
    if not cols:
        return ['{}'] * len(rows)
    sub = df.iloc[list(rows)]
    lists = [_canon_column(sub[c]) for c in cols]
    enc = json.JSONEncoder(**_JSON).encode
    return [enc({n: v for n, v in zip(cols, values) if v is not None}) for values in zip(*lists)]


def _field_diff(old: dict, new: dict, fields=None):
    """[(فیلد، مقدار قبلی، مقدار جدید)] به متن JSON؛ خالی یعنی None."""
    out = []
    for f in sorted(old.keys() | new.keys()):
        if fields is not None and f not in fields:
            continue
        a, b = old.get(f), new.get(f)
        if type(a) is type(b) and (a is b or (type(a) is str and a == b)):
            continue
        ta = None if a is None else _dump(a)
        tb = None if b is None else _dump(b)
        if ta != tb:
            out.append((f, ta, tb))
    return out


# ─────────────────────────── جفت کردن ───────────────────────────
# ردیف باز: (id, rkey, occ, fhash, vhash)
_ID, _RKEY, _OCC, _FH, _VH = range(5)


def _pair_group(rows: List[int], recs: list, fh: np.ndarray, row_ck=None, rec_ck=None):
    """ردیف‌های یک کلید را با نسخه‌های باز همان کلید جفت می‌کند.

    به ترتیب: اثرانگشت سریع برابر، محتوای متعارف برابر (``row_ck``/``rec_ck``)، و در آخر به
    ترتیب (ردیف‌ها به ترتیب فایل، نسخه‌ها به ترتیب occ). خروجی: (جفت‌ها، ردیف‌های اضافه،
    نسخه‌های اضافه)؛ یکی از دو «اضافه» همیشه خالی است.
    """
    if len(rows) == 1 and len(recs) == 1:
        return [(rows[0], recs[0])], [], []
    if not recs:
        return [], list(rows), []
    if not rows:
        return [], [], list(recs)
    pairs, left, free = [], list(rows), list(recs)
    for row_key, rec_key in ((lambda i: int(fh[i]), lambda r: r[_FH]), (row_ck, rec_ck)):
        if row_key is None or not left or not free:
            continue
        bucket = defaultdict(list)
        for r in free:
            bucket[rec_key(r)].append(r)
        used, rest = set(), []
        for i in left:
            b = bucket.get(row_key(i))
            if b:
                r = b.pop(0)
                used.add(r[_ID])
                pairs.append((i, r))
            else:
                rest.append(i)
        left = rest
        free = [r for r in free if r[_ID] not in used]
    k = min(len(left), len(free))
    pairs.extend(zip(left[:k], free[:k]))
    return pairs, left[k:], free[k:]


def _free_occ(taken: set) -> int:
    n = 0
    while n in taken:
        n += 1
    return n


# ─────────────────────────── اجرای یک فریم ───────────────────────────
class _Batch:
    """نوشتنی‌های یک اجرا؛ همه در یک تراکنش، بعد از هر فریم روانه می‌شوند."""

    def __init__(self, conn, seq: int, run_id: str, next_id: int):
        self.conn, self.seq, self.run_id, self.next_id = conn, seq, run_id, next_id
        self.closes: list = []       # (to_seq, id)
        self.fh_updates: list = []   # (fhash, id)
        self.inserts: list = []      # ردیف‌های src_record
        self.changes: list = []      # ردیف‌های src_change
        self.totals = defaultdict(int)
        self.reader = PayloadReader(conn)

    def new_id(self) -> int:
        i = self.next_id
        self.next_id += 1
        return i

    def flush(self) -> None:
        c = self.conn
        if self.closes:
            c.executemany('UPDATE src_record SET to_seq=? WHERE id=?', self.closes)
        if self.fh_updates:
            c.executemany('UPDATE src_record SET fhash=? WHERE id=?', self.fh_updates)
        if self.inserts:
            c.executemany('INSERT INTO src_record(id,source,frame,rkey,occ,from_seq,to_seq,vhash,fhash,payload,zdict,'
                          'loc,prev_id) VALUES(?,?,?,?,?,?,NULL,?,?,?,?,?,?)', self.inserts)
        if self.changes:
            c.executemany('INSERT INTO src_change(seq,run_id,source,frame,rkey,occ,kind,field,old,new,cause,'
                          'record_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', self.changes)
        for name, items in (('closed', self.closes), ('fhash', self.fh_updates),
                            ('versions', self.inserts), ('log', self.changes)):
            self.totals[name] += len(items)
            items.clear()


def _cause(previous: Optional[dict], current: Optional[dict]) -> str:
    if not current or not previous:
        return 'data'
    files_changed = previous.get('files') != current.get('files')
    program_changed = previous.get('program') != current.get('program')
    if files_changed and program_changed:
        return 'data+program'
    if files_changed:
        return 'data'
    if program_changed:
        return 'program'
    return 'unknown'


def _project(d: dict, fields) -> dict:
    return d if fields is None else {k: v for k, v in d.items() if k in fields}


class _FrameRun:
    def __init__(self, batch: _Batch, wh, src: str, frame: str, spec: FrameSpec, sha: str,
                 meta_text: Optional[str], load_input: Optional[dict]):
        self.b, self.wh, self.src, self.frame, self.spec = batch, wh, src, frame, spec
        self.sha, self.meta_text = sha, meta_text
        self.load_input = dict(load_input or {})
        self.seq = batch.seq
        self.texts: Dict[int, str] = {}
        self.vhs: Dict[int, str] = {}
        self.pending: list = []
        self.cause = 'data'
        self.schema_changed = False
        self.common = None
        self.stats = {'rows': 0, 'new': 0, 'changed': 0, 'fields': 0, 'gone': 0, 'back': 0,
                      'unchanged': 0, 'restated': 0}

    # ── کمکی‌ها ──
    def ensure_texts(self, rows) -> None:
        need = [i for i in dict.fromkeys(rows) if i not in self.texts]
        if not need:
            return
        if len(need) == self.n:
            self.texts.update(enumerate(_row_payloads(self.df, self.vcols)))
            return
        need.sort()
        for i, t in zip(need, _row_payloads(self.df, self.vcols, need)):
            self.texts[i] = t

    def vhash(self, i: int) -> str:
        v = self.vhs.get(i)
        if v is None:
            v = self.vhs[i] = _vhash(self.texts[i])
        return v

    def change(self, rkey, occ, kind, fld=None, old=None, new=None, record_id=None) -> None:
        self.b.changes.append((self.seq, self.b.run_id, self.src, self.frame, rkey, occ, kind, fld, old, new,
                               self.cause, record_id))

    def add(self, rkey: str, occ: int, i: int, prev_id) -> int:
        rid = self.b.new_id()
        self.pending.append((rid, rkey, int(occ), i, prev_id))
        return rid

    def materialize(self, fresh_dict: bool) -> None:
        if not self.pending:
            return
        c = self.b.conn
        zid = None
        if not fresh_dict:
            row = c.execute('SELECT id,data FROM src_zdict WHERE source=? AND frame=? ORDER BY id DESC LIMIT 1',
                            (self.src, self.frame)).fetchone()
            if row is not None:
                zid, data = int(row[0]), bytes(row[1])
        if zid is None:
            data = _build_zdict([self.texts[i] for i in sorted(self.texts)])
            if data:
                zid = c.execute('INSERT INTO src_zdict(source,frame,seq,data) VALUES(?,?,?,?)',
                                (self.src, self.frame, self.seq, data)).lastrowid
        primed = _primed(data) if zid is not None else None
        locs = _locations(self.df, self.lcols, [p[3] for p in self.pending])
        for (rid, rkey, occ, i, prev_id), loc in zip(self.pending, locs):
            blob = _pack(self.texts[i], primed)
            self.b.inserts.append((rid, self.src, self.frame, rkey, occ, self.seq, self.vhash(i), int(self.fh[i]),
                                   blob, zid if blob[:1] == b'd' else None, loc, prev_id))
        self.pending.clear()

    def old_payloads(self, ids, cache: dict) -> dict:
        need = [i for i in dict.fromkeys(ids) if i not in cache]
        for k in range(0, len(need), _CHUNK):
            chunk = need[k:k + _CHUNK]
            q = 'SELECT id,payload,zdict FROM src_record WHERE id IN (%s)' % ','.join('?' * len(chunk))
            for rid, blob, zid in self.b.conn.execute(q, chunk):
                cache[rid] = self.b.reader.unpack(blob, zid)
        return cache

    def log_changed(self, rkey: str, occ: int, old: dict, i: int, rid: int, fields=None) -> None:
        diff = _field_diff(old, json.loads(self.texts[i]), fields)
        if not diff:
            self.stats['restated'] += 1      # فقط ستون افزوده/حذف‌شده یا قواعد متعارف تازه
            return
        self.stats['changed'] += 1
        self.stats['fields'] += len(diff)
        self.change(rkey, occ, 'changed', record_id=rid)
        for f, a, b in diff:
            self.change(rkey, occ, 'changed', f, a, b, rid)

    # ── اجرا ──
    def run(self) -> dict:
        from .framecodec import decode_frame
        c = self.b.conn
        t0 = time.perf_counter()
        state = c.execute('SELECT key_spec,columns_json,baseline_seq,last_seq,last_sha,last_input,rows '
                          'FROM src_frame_state WHERE source=? AND frame=?', (self.src, self.frame)).fetchone()
        input_text = _dump(self.load_input)
        try:
            meta = json.loads(self.meta_text) if self.meta_text else {}
            meta_cols = meta.get('columns')
            if meta_cols is not None:
                named = [n for n in (meta.get('index_names') or []) if n is not None]
                meta_cols = list(named) + list(meta_cols)
        except ValueError:
            meta_cols = None
        if state is not None and meta_cols is not None and state[4] == self.sha:
            names = [str(x) for x in meta_cols]
            loc = set(self.spec.location)
            if (state[0] == _dump(self.spec.key_spec(names))
                    and state[1] == _dump(sorted(x for x in names if x not in loc))):
                c.execute('UPDATE src_frame_state SET last_seq=?,last_input=? WHERE source=? AND frame=?',
                          (self.seq, input_text, self.src, self.frame))
                return {'mode': 'same', 'rows': int(state[6]), 'seconds': round(time.perf_counter() - t0, 3)}

        df = decode_frame(self.wh.objects.get(self.sha, 'parquet'))
        idx = df.index
        if any(name is not None for name in idx.names):
            try:
                df = df.reset_index()      # نمایه نام‌دار جزو محتواست
            except ValueError:
                df = df.reset_index(drop=True)
        elif not (isinstance(idx, pd.RangeIndex) and idx.start == 0 and idx.step == 1):
            df = df.reset_index(drop=True)
        if any(not isinstance(x, str) for x in df.columns):
            df = df.rename(columns=str)
        self.df = df
        self.n = n = len(self.df)
        cols = list(self.df.columns)
        loc = set(self.spec.location)
        self.vcols = sorted(x for x in cols if x not in loc)
        self.lcols = [x for x in self.spec.location if x in cols]
        kspec = self.spec.key_spec(cols)
        kspec_text, vcols_text = _dump(kspec), _dump(self.vcols)
        self.keymode = kspec['mode'] == 'keys'
        self.keys = list(kspec.get('keys') or [])
        self.fh = _fast_hashes(self.df, self.vcols)
        self.bases = _base_keys(self.df, self.keys) if self.keymode else None
        self.stats['rows'] = n

        if state is None:
            self.baseline()
            c.execute('INSERT INTO src_frame_state(source,frame,key_spec,columns_json,baseline_seq,last_seq,'
                      'last_sha,last_input,rows) VALUES(?,?,?,?,?,?,?,?,?)',
                      (self.src, self.frame, kspec_text, vcols_text, self.seq, self.seq, self.sha, input_text, n))
            mode = 'baseline'
        else:
            self.cause = _cause(json.loads(state[5] or '{}'), self.load_input)
            old_vcols = json.loads(state[1])
            self.schema_changed = old_vcols != self.vcols
            if self.schema_changed:
                self.common = set(old_vcols) & set(self.vcols)
                for f in sorted(set(self.vcols) - set(old_vcols)):
                    self.change(None, None, 'schema', f, None, '"added"')
                for f in sorted(set(old_vcols) - set(self.vcols)):
                    self.change(None, None, 'schema', f, '"removed"', None)
            rekey = state[0] != kspec_text
            if rekey:
                self.change(None, None, 'rekey', None, state[0], kspec_text)
            self.compare(rekey)
            c.execute('UPDATE src_frame_state SET key_spec=?,columns_json=?,last_seq=?,last_sha=?,last_input=?,'
                      'rows=? WHERE source=? AND frame=?',
                      (kspec_text, vcols_text, self.seq, self.sha, input_text, n, self.src, self.frame))
            mode = 'rekey' if rekey else ('schema' if self.schema_changed else 'diff')
        self.materialize(fresh_dict=mode in ('baseline', 'rekey', 'schema'))
        self.stats.update(mode=mode, cause=self.cause, seconds=round(time.perf_counter() - t0, 3))
        return self.stats

    def baseline(self) -> None:
        self.ensure_texts(range(self.n))
        counter: Dict[str, int] = defaultdict(int)
        for i in range(self.n):
            base = self.bases[i] if self.keymode else _content_base(self.vhash(i))
            occ = counter[base]
            counter[base] += 1
            self.add(base, occ, i, None)
        self.stats['new'] = self.n
        self.change(None, None, 'baseline', None, None, str(self.n))

    # ── جفت کردن ردیف‌های این اجرا با نسخه‌های باز ──
    def _pair_all(self, rows_by: dict, recs_by: dict, payloads: dict, projected: bool):
        # گروه‌های چندتایی (کلید تکراری) با محتوای متعارف هم جفت می‌شوند؛ متن‌ها یک‌جا ساخته می‌شوند.
        multi = [b for b in rows_by.keys() & recs_by.keys()
                 if not (len(rows_by[b]) == 1 and len(recs_by[b]) == 1)]
        if multi:
            self.ensure_texts([i for b in multi for i in rows_by[b]])
            if projected:
                self.old_payloads([r[_ID] for b in multi for r in recs_by[b]], payloads)

        def row_ck(i):
            if projected:
                return _vhash(_dump(_project(json.loads(self.texts[i]), self.common)))
            return self.vhash(i)

        def rec_ck(r):
            if projected:
                return _vhash(_dump(_project(payloads[r[_ID]], self.common)))
            return r[_VH]

        pairs, extra_rows, extra_recs = [], [], []
        for b in rows_by.keys() | recs_by.keys():
            rs = sorted(recs_by.get(b, ()), key=lambda r: (r[_OCC], r[_ID]))
            p, er, eo = _pair_group(rows_by.get(b, []), rs, self.fh, row_ck, rec_ck)
            pairs.extend(p)
            extra_rows.extend(er)
            extra_recs.extend(eo)
        return pairs, extra_rows, extra_recs

    def match(self, recs: list, payloads: dict, rekey: bool):
        if self.keymode:
            rows_by = defaultdict(list)
            for i, b in enumerate(self.bases):
                rows_by[b].append(i)
            recs_by = defaultdict(list)
            for r in recs:
                b = _dump([payloads[r[_ID]].get(k) for k in self.keys]) if rekey else r[_RKEY]
                recs_by[b].append(r)
            return self._pair_all(rows_by, recs_by, payloads, rekey or self.schema_changed)
        # بی‌کلید: اول اثرانگشت سریع (همان محتوا، همان نوع ستون‌ها)، بعد محتوای متعارف
        pairs = []
        if not (rekey or self.schema_changed):
            by_fh = defaultdict(list)
            for r in sorted(recs, key=lambda r: (r[_RKEY], r[_OCC], r[_ID])):
                by_fh[r[_FH]].append(r)
            left = []
            for i in range(self.n):
                bucket = by_fh.get(int(self.fh[i]))
                if bucket:
                    pairs.append((i, bucket.pop(0)))
                else:
                    left.append(i)
            pool = [r for bucket in by_fh.values() for r in bucket]
            projected = False
        else:
            left, pool, projected = list(range(self.n)), list(recs), True
        self.ensure_texts(left)
        rows_by = defaultdict(list)
        for i in left:
            if projected:
                b = _content_base(_vhash(_dump(_project(json.loads(self.texts[i]), self.common))))
            else:
                b = _content_base(self.vhash(i))
            rows_by[b].append(i)
        recs_by = defaultdict(list)
        for r in pool:
            b = _content_base(_vhash(_dump(_project(payloads[r[_ID]], self.common)))) if projected \
                else _content_base(r[_VH])
            recs_by[b].append(r)
        p, er, eo = self._pair_all(rows_by, recs_by, payloads, projected)
        return pairs + p, er, eo

    def compare(self, rekey: bool) -> None:
        c = self.b.conn
        recs = c.execute('SELECT id,rkey,occ,fhash,vhash FROM src_record '
                         'WHERE source=? AND frame=? AND to_seq IS NULL', (self.src, self.frame)).fetchall()
        payloads: dict = {}
        if rekey or (self.schema_changed and not self.keymode):
            self.old_payloads([r[_ID] for r in recs], payloads)
        pairs, extra_rows, extra_recs = self.match(recs, payloads, rekey)

        # جفت‌ها: بی‌تغییر می‌مانند یا بسته و با نسخه تازه ادامه داده می‌شوند
        if rekey or self.schema_changed:
            fast, slow = [], pairs
        else:
            fast, slow = [], []
            for i, r in pairs:
                (fast if int(self.fh[i]) == r[_FH] else slow).append((i, r))
        self.ensure_texts([i for i, _ in slow] + list(extra_rows))
        keep, redo = list(fast), []
        for i, r in slow:
            if not rekey and self.vhash(i) == r[_VH]:
                keep.append((i, r))
                if int(self.fh[i]) != r[_FH]:
                    self.b.fh_updates.append((int(self.fh[i]), r[_ID]))
            else:
                redo.append((i, r))
        self.stats['unchanged'] = len(keep)
        taken = defaultdict(set)
        for i, r in keep:
            taken[r[_RKEY]].add(r[_OCC])
        redo.sort(key=lambda x: x[0])
        self.old_payloads([r[_ID] for i, r in redo if self.vhash(i) != r[_VH]], payloads)
        for i, r in redo:
            vh = self.vhash(i)
            base = self.bases[i] if self.keymode else _content_base(vh)
            occ = r[_OCC] if (self.keymode and not rekey) else None
            if occ is None or occ in taken[base]:
                occ = _free_occ(taken[base])
            taken[base].add(occ)
            self.b.closes.append((self.seq, r[_ID]))
            rid = self.add(base, occ, i, r[_ID])
            if self.keymode and vh != r[_VH]:
                self.log_changed(base, occ, payloads[r[_ID]], i, rid, self.common)
            else:
                self.stats['restated'] += 1

        # ردیف‌های تازه، یا ردیفی که قبلاً رفته بود و برگشته
        any_closed = not rekey and c.execute(
            'SELECT 1 FROM src_record WHERE source=? AND frame=? AND to_seq IS NOT NULL LIMIT 1',
            (self.src, self.frame)).fetchone() is not None
        current = set(self.vcols)
        for i in sorted(extra_rows):
            vh = self.vhash(i)
            base = self.bases[i] if self.keymode else _content_base(vh)
            occ = _free_occ(taken[base])
            taken[base].add(occ)
            prev = c.execute('SELECT id,vhash,payload,zdict FROM src_record WHERE source=? AND frame=? AND rkey=? '
                             'AND occ=? AND to_seq IS NOT NULL ORDER BY to_seq DESC, id DESC LIMIT 1',
                             (self.src, self.frame, base, occ)).fetchone() if any_closed else None
            rid = self.add(base, occ, i, prev[0] if prev else None)
            if prev is None:
                self.stats['new'] += 1
                self.change(base, occ, 'new', record_id=rid)
                continue
            self.stats['back'] += 1
            self.change(base, occ, 'back', record_id=rid)
            if prev[1] != vh:
                for f, a, b in _field_diff(self.b.reader.unpack(prev[2], prev[3]), json.loads(self.texts[i]), current):
                    self.change(base, occ, 'back', f, a, b, rid)

        # نسخه‌هایی که این بار دیده نشدند
        for r in sorted(extra_recs, key=lambda r: r[_ID]):
            self.b.closes.append((self.seq, r[_ID]))
            self.stats['gone'] += 1
            self.change(r[_RKEY], r[_OCC], 'gone', record_id=r[_ID])


# ─────────────────────────── API ───────────────────────────
def _load_inputs(conn, rid: str) -> Dict[str, dict]:
    """فایل‌های هر سورس در این اجرا (اثرانگشت محتوا) و امضای برنامه، برای تعیین علت تغییر."""
    out: Dict[str, dict] = {}
    for src, fid in conn.execute('SELECT source,file_id FROM wh_ingest WHERE run_id=? ORDER BY id', (rid,)):
        out.setdefault(src, {'files': [], 'program': ''})['files'].append(fid)
    for src, program in conn.execute('SELECT source,program_sig FROM wh_source_load WHERE run_id=?', (rid,)):
        out.setdefault(src, {'files': [], 'program': ''})['program'] = program or ''
    for item in out.values():
        item['files'] = sorted(set(item['files']))
    return out


def record_history(wh, rid: str, sources, *, specs: Optional[Specs] = None, log=None) -> dict:
    """سوابق فریم‌های استاندارد سورس‌های تازه‌خوانده‌شده این اجرا را در یک تراکنش ثبت می‌کند.

    ``sources``: سورس‌هایی که در این اجرا واقعاً خوانده شدند (نه جایگزین از Snapshot قبلی و
    نه سورسی که فایلش نبود). فریمی که این بار ساخته نشده دست نمی‌خورد و «رفته» حساب نمی‌شود.
    """
    t0 = time.perf_counter()
    specs = specs or load_specs()
    sources = {str(s) for s in sources}
    stats: Dict[str, dict] = {}
    with wh.db() as c:
        row = c.execute('SELECT seq FROM wh_run WHERE id=?', (rid,)).fetchone()
        if row is None:
            raise KeyError(rid)
        seq = int(row[0])
        latest: Dict[Tuple[str, str], Tuple[str, str]] = {}
        for name, sha, meta in c.execute("SELECT name,object_sha,metadata FROM wh_frame "
                                         "WHERE run_id=? AND layer='standardized' ORDER BY rowid", (rid,)):
            src, sep, frame = str(name).partition('/')
            if sep and frame and src in sources:
                latest[(src, frame)] = (sha, meta)
        inputs = _load_inputs(c, rid)
        start = c.execute('SELECT COALESCE(MAX(id),0)+1 FROM src_record').fetchone()[0]
        batch = _Batch(c, seq, rid, int(start))
        for (src, frame), (sha, meta) in sorted(latest.items()):
            st = _FrameRun(batch, wh, src, frame, specs.get(f'{src}/{frame}'), sha, meta, inputs.get(src)).run()
            batch.flush()
            stats[f'{src}/{frame}'] = st
    # لاگ بعد از بستن تراکنش: گیرنده لاگ خودش در همین انبار می‌نویسد و تا تراکنش باز است منتظر می‌ماند.
    if log is not None:
        for name, st in stats.items():
            if st.get('mode') != 'same':
                log.info(f"🧾 [history] {name}: {_describe(st)}")
    summary = {'seq': seq, 'frames': len(stats), 'seconds': round(time.perf_counter() - t0, 3),
               'unchanged_frames': sum(1 for s in stats.values() if s.get('mode') == 'same'),
               **{k: sum(int(s.get(k, 0)) for s in stats.values() if s.get('mode') != 'same')
                  for k in ('new', 'changed', 'fields', 'gone', 'back', 'restated')},
               **{k: v for k, v in batch.totals.items()}}
    return {'summary': summary, 'frames': stats}


def _describe(st: dict) -> str:
    mode = st.get('mode')
    if mode == 'baseline':
        return f"خط مبنا {st['rows']} ردیف ({st['seconds']}s)"
    parts = [f"{st.get(k, 0)} {fa}" for k, fa in (('new', 'تازه'), ('changed', 'تغییر'), ('gone', 'رفته'),
                                                   ('back', 'برگشته')) if st.get(k)]
    if st.get('fields'):
        parts.append(f"{st['fields']} فیلد")
    if st.get('restated'):
        parts.append(f"{st['restated']} بازنویسی بی‌تغییر محتوا")
    tail = f" | {mode} | علت: {st.get('cause')}" if mode != 'diff' else f" | علت: {st.get('cause')}"
    return (', '.join(parts) or 'بدون تغییر ردیف') + tail + f" ({st.get('seconds')}s)"


# ─────────────────────────── خواندن ───────────────────────────
def decode_value(v):
    """مقدار متعارف را به مقدار پایتون برمی‌گرداند (برای نمایش)."""
    if isinstance(v, dict):
        if '$t' in v:
            return pd.Timestamp(v['$t'])
        if '$d' in v:
            return date.fromisoformat(v['$d'])
        if '$tm' in v:
            return dtime.fromisoformat(v['$tm'])
        if '$td' in v:
            return pd.Timedelta(v['$td'])
        if '$f' in v:
            return float(v['$f'])
        if '$dec' in v:
            return Decimal(v['$dec'])
        if '$b' in v:
            return bytes.fromhex(v['$b'])
        if '$x' in v:
            return v.get('v')
        return {k: decode_value(x) for k, x in v.items()}
    if isinstance(v, list):
        return [decode_value(x) for x in v]
    return v


def frame_as_of(conn, source: str, frame: str, seq: int, *, with_location: bool = False) -> pd.DataFrame:
    """محتوای یک فریم منبع «به تاریخ» یک اجرا، از روی سوابق."""
    rows = conn.execute('SELECT rkey,occ,payload,zdict,loc FROM src_record WHERE source=? AND frame=? AND from_seq<=? '
                        'AND (to_seq IS NULL OR to_seq>?) ORDER BY rkey,occ', (source, frame, seq, seq)).fetchall()
    reader = PayloadReader(conn)
    records = []
    for rkey, occ, blob, zid, loc in rows:
        item = {k: decode_value(v) for k, v in reader.unpack(blob, zid).items()}
        if with_location:
            item.update({k: decode_value(v) for k, v in json.loads(loc).items()})
        records.append(item)
    return pd.DataFrame.from_records(records)

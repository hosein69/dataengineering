# -*- coding: utf-8 -*-
"""حافظه خواندن سورس‌ها: فایلی که عوض نشده دوباره خوانده و پردازش نمی‌شود.

برای هر سورس در هر اجرا یک «امضای ورودی» ساخته می‌شود: نام و اثرانگشت محتوای فایل‌های
هدف به ترتیب، مشخصات سورس، کد و تنظیمات برنامه، نسخه کتابخانه‌ها و متغیرهای محیطی GSI.
اگر اجرای کامل‌شده‌ای با همان امضا هست:

* فریم‌های آن اجرا (که در بایگانی با اثرانگشت هستند) بدون نوشتن دوباره به این اجرا پیوند
  می‌خورند و فریم‌های استاندارد از Parquet باز می‌شوند؛
* ردیف دفتر فایل‌ها (``wh_ingest``)، ایرادهای ثبت‌شده همان فایل‌ها و سهم همان سورس از
  «سلامت سیستم» دوباره ثبت می‌شوند تا گزارش این اجرا با خواندن کامل یکی باشد.

هر بارگذاری، چه خوانده چه دوباره به‌کار رفته، یک ردیف در ``wh_source_load`` دارد.
``GSI_SOURCE_CACHE=0`` دوباره‌به‌کاربردن را خاموش می‌کند؛ دفتر همچنان ثبت می‌شود.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from .store import RUN, Warehouse, now

_CODE_SUFFIXES = ('.py', '.yaml', '.yml', '.json')
_SIG_VERSION = 1


def _dump(x) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def enabled() -> bool:
    return (os.getenv('GSI_SOURCE_CACHE') or '1').strip().lower() not in ('0', 'false', 'no', 'off')


def _package_hash() -> str:
    """اثرانگشت همه کد و تنظیمات بسته gsi (حدود ۱۰ میلی‌ثانیه)."""
    root = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__' and not d.startswith('.'))
        for name in sorted(files):
            if name.endswith(_CODE_SUFFIXES):
                path = Path(base) / name
                h.update(path.relative_to(root).as_posix().encode('utf-8'))
                h.update(b'\0')
                h.update(path.read_bytes())
                h.update(b'\0')
    return h.hexdigest()


def _library_versions() -> Dict[str, str]:
    out = {'python': platform.python_version()}
    for name in ('pandas', 'numpy', 'pyarrow', 'openpyxl', 'xlrd', 'yaml'):
        mod = sys.modules.get(name)
        if mod is None:
            try:
                mod = __import__(name)
            except Exception:                      # noqa: BLE001 — کتابخانه اختیاری
                continue
        out[name] = str(getattr(mod, '__version__', ''))
    return out


def program_signature() -> str:
    """امضای «برنامه»: کد، تنظیمات، رجیستری سورس‌ها، کتابخانه‌ها و متغیرهای محیطی GSI."""
    from ..config.sources import _yaml_path
    sources_yaml = Path(_yaml_path())
    env = {k: v for k, v in os.environ.items() if k.startswith(('GSI_', 'AIBL_'))
           and k not in ('GSI_SOURCE_CACHE',)}
    payload = {
        'v': _SIG_VERSION,
        'package': _package_hash(),
        'sources_yaml': hashlib.sha256(sources_yaml.read_bytes()).hexdigest() if sources_yaml.is_file() else '',
        'libraries': _library_versions(),
        'env': env,
    }
    return hashlib.sha256(_dump(payload).encode('utf-8')).hexdigest()


class SourceLoad:
    """بارگذاری یک سورس در یک اجرای انبار داده."""

    def __init__(self, wh: Warehouse, adapter, rid: str, program: str):
        from .. import health
        self.wh, self.adapter, self.rid, self.program = wh, adapter, rid, program
        self.key = adapter.key
        self.t0 = time.perf_counter()
        self.targets: List[dict] = []
        self.input_sig: Optional[str] = None
        hp = health.current()
        self._mark = (len(hp.stages), len(hp.joins), len(hp.findings))

    # ── امضای ورودی ──
    def prepare(self) -> None:
        from ..dataio.reader import source_targets
        from .excel import remember_bytes
        from ..dataio.logging_setup import log
        spec, targets = source_targets(self.key, quiet=True)
        for path in targets:
            p = Path(path)
            read_start = time.perf_counter()
            before = p.stat()
            content = p.read_bytes()
            after = p.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError('فایل هنگام خواندن تغییر کرد؛ دوباره اجرا کنید.')
            remember_bytes(p, after, content)
            read_seconds = time.perf_counter() - read_start
            hash_start = time.perf_counter()
            digest = hashlib.sha256(content).hexdigest()
            log.info('[source-timing] %s %s network_read=%.3fs sha256=%.3fs bytes=%d',
                     self.key, p.name, read_seconds, time.perf_counter() - hash_start, len(content))
            self.targets.append({'name': p.name, 'path': str(p), 'sha': digest,
                                 'size': len(content)})
        cls = type(self.adapter)
        spec_value = dataclasses.asdict(spec) if dataclasses.is_dataclass(spec) else repr(spec)
        sig = {'v': _SIG_VERSION, 'source': self.key, 'adapter': f'{cls.__module__}.{cls.__qualname__}',
               'spec': spec_value, 'files': [[t['name'], t['sha']] for t in self.targets],
               'program': self.program}
        self.input_sig = hashlib.sha256(_dump(sig).encode('utf-8')).hexdigest()

    def close(self) -> None:
        from .excel import forget_bytes
        for t in self.targets:
            forget_bytes(t['path'])

    # ── دوباره‌به‌کاربردن ──
    def reuse(self, rec):
        """فریم‌های استاندارد اجرای قبلیِ هم‌امضا، یا ``None`` اگر باید خوانده شود."""
        if not enabled() or not self.targets or not self.input_sig:
            return None
        with self.wh.read_db(bind=False) as c:
            row = c.execute(
                "SELECT l.run_id,l.reused_run,l.frames,l.health FROM wh_source_load l JOIN wh_run r ON r.id=l.run_id "
                "WHERE l.source=? AND l.input_sig=? AND r.status='completed' AND l.run_id<>? AND l.frames<>'[]' "
                "ORDER BY r.seq DESC LIMIT 1", (self.key, self.input_sig, self.rid)).fetchone()
        if row is None:
            return None
        origin_run, origin, frames_text, health_text = row[0], row[1] or row[0], row[2], row[3]
        frames = json.loads(frames_text)
        store = self.wh.objects
        if not all(store.exists(f['sha'], 'parquet') for f in frames):
            return None
        from .framecodec import decode_frame
        out = {}
        prefix = self.key + '/'
        for f in frames:
            if f['layer'] != 'standardized':
                continue
            df = decode_frame(store.get(f['sha'], 'parquet'))
            if len(df) != int(f['rows']):
                return None
            out[f['name'][len(prefix):]] = df
        for t in self.targets:
            from .excel import _read_stable
            self.wh.blob(_read_stable(Path(t['path'])), t['name'], self.key, t['path'])
        with self.wh.db() as c:
            ids = [t['sha'] for t in self.targets]
            marks = ','.join('?' * len(ids))
            c.execute(f'INSERT INTO wh_issue(run_id,file_id,sheet,row_no,code,detail) '
                      f'SELECT ?,file_id,sheet,row_no,code,detail FROM wh_issue WHERE run_id=? AND file_id IN ({marks}) '
                      f'ORDER BY id', [self.rid, origin_run, *ids])
            for f in frames:
                self.wh.link_frame(c, f['sha'], f['layer'], f['name'], f['rows'], f['meta'])
            self._ledger(c, 'reused', origin, frames, health_text)
        self._replay_health(json.loads(health_text or '{}'), rec)
        return out

    def _replay_health(self, delta: dict, rec) -> None:
        from .. import health
        hp = health.current()
        for k, v in (delta.get('source') or {}).items():
            if k not in ('key', 'elapsed_s') and hasattr(rec, k):
                setattr(rec, k, list(v) if isinstance(v, list) else v)
        rec.elapsed_s = round(time.perf_counter() - self.t0, 3)
        for item in delta.get('stages') or ():
            hp.stages.append(health.StageHealth(**item))
        for item in delta.get('joins') or ():
            hp.joins.append(health.JoinHealth(**item))
        for item in delta.get('findings') or ():
            hp.findings.append(health.Finding(**item))

    # ── ثبت بارگذاری تازه ──
    def commit(self, rec) -> None:
        from .. import health
        hp = health.current()
        s, j, f = self._mark
        delta = {'source': dataclasses.asdict(rec),
                 'stages': [dataclasses.asdict(x) for x in hp.stages[s:]],
                 'joins': [dataclasses.asdict(x) for x in hp.joins[j:]],
                 'findings': [dataclasses.asdict(x) for x in hp.findings[f:]]}
        with self.wh.db() as c:
            frames = [{'layer': layer, 'name': name, 'sha': sha, 'rows': int(rows), 'meta': meta}
                      for layer, name, sha, rows, meta in c.execute(
                          "SELECT layer,name,object_sha,row_count,metadata FROM wh_frame WHERE run_id=? "
                          "AND layer IN ('standardized','staging') AND substr(name,1,?)=? ORDER BY rowid",
                          (self.rid, len(self.key) + 1, self.key + '/'))]
            # سورسی که فایلی برایش پیدا نشد «خوانده» نشده است؛ در دفتر جدا دیده می‌شود
            mode = 'missing' if (self.input_sig and not self.targets) else 'parsed'
            self._ledger(c, mode, None, frames, _dump(delta))

    def _ledger(self, c, mode: str, reused_run, frames, health_text) -> None:
        c.execute('INSERT OR REPLACE INTO wh_source_load(run_id,source,input_sig,program_sig,mode,reused_run,files,'
                  'frames,health,seconds) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (self.rid, self.key, self.input_sig or '', self.program, mode, reused_run,
                   _dump(self.targets), _dump(frames), health_text or '{}',
                   round(time.perf_counter() - self.t0, 3)))


_PROGRAM: Dict[str, str] = {}


def program_signature_for(rid: str) -> str:
    """امضای برنامه، یک‌بار برای هر اجرا (همه بخش‌های یک اجرا یک امضا می‌بینند)."""
    program = _PROGRAM.get(rid)
    if program is None:
        _PROGRAM.clear()
        program = _PROGRAM[rid] = program_signature()
    return program


def begin(adapter) -> Optional[SourceLoad]:
    """شروع بارگذاری یک سورس؛ بیرون از اجرای انبار داده ``None``."""
    rid = RUN.get()
    if rid is None:
        return None
    program = program_signature_for(rid)
    session = SourceLoad(Warehouse(), adapter, rid, program)
    try:
        session.prepare()
    except Exception:
        # خواندن فایل‌ها برای امضا ممکن نشد؛ مسیر عادی خطا را خودش گزارش می‌کند.
        session.close()
        session.targets = []
        session.input_sig = None
    return session

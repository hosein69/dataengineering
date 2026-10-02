"""Single-writer guard with forensic metadata.

The OS lock is the source of truth.  The adjacent JSON metadata is diagnostic
only and never used to decide whether a writer is alive.  This distinction is
important on Windows/networked environments: a stale file must never be
mistaken for an active process.
"""
from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_write(path: Path, payload: dict) -> None:
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        # Diagnostics must never break the lock itself.
        pass


class WarehouseBusyError(TimeoutError):
    """A second writer was refused; this is concurrency control, not ETL failure."""

    code = "WAREHOUSE_WRITER_BUSY"
    category = "CONCURRENCY"
    severity = "INFO"

    def __init__(self, path: Path, details: dict | None = None):
        self.path = Path(path)
        self.details = dict(details or {})
        same_host = self.details.get("host") == socket.gethostname()
        same_pid = self.details.get("pid") == os.getpid()
        self.reason = "SELF_REENTRY" if same_host and same_pid else "CONCURRENT_WRITER"
        super().__init__(self._message())

    def _message(self) -> str:
        owner = []
        if self.details.get("host"):
            owner.append(f"host={self.details['host']}")
        if self.details.get("pid"):
            owner.append(f"pid={self.details['pid']}")
        if self.details.get("run_id"):
            owner.append(f"run={self.details['run_id']}")
        suffix = (" [" + ", ".join(owner) + "]") if owner else ""
        if self.reason == "SELF_REENTRY":
            return "اجرای تودرتوی خط لوله در همین پردازش شناسایی شد؛ اجرای دوم شروع نشد." + suffix
        return "یک نویسنده دیگر روی انبار داده فعال است؛ اجرای دوم برای جلوگیری از تداخل شروع نشد." + suffix

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "reason": self.reason,
            "lock_path": str(self.path),
            **self.details,
        }


class WriterLock:
    def __init__(self, path, timeout=5, metadata=None):
        self.path = Path(path)
        self.timeout = float(timeout)
        self.file = None
        self.meta_path = self.path.with_suffix(self.path.suffix + ".meta.json")
        self.meta = {
            "state": "waiting",
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "requested_at": _utcnow(),
            **dict(metadata or {}),
        }

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.path, "a+b")
        if self.file.seek(0, 2) == 0:
            self.file.write(b"0")
            self.file.flush()
        start = time.monotonic()
        while True:
            try:
                self.file.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.meta.update({"state": "active", "acquired_at": _utcnow()})
                _safe_write(self.meta_path, self.meta)
                return self
            except OSError:
                if time.monotonic() - start >= self.timeout:
                    self.file.close()
                    raise WarehouseBusyError(self.path, _safe_read(self.meta_path))
                time.sleep(0.05)

    def update(self, **fields):
        self.meta.update(fields)
        if self.meta.get("state") == "active":
            _safe_write(self.meta_path, self.meta)

    def __exit__(self, *args):
        try:
            self.meta.update({"state": "released", "released_at": _utcnow()})
            _safe_write(self.meta_path, self.meta)
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()

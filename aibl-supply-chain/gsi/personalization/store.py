# -*- coding: utf-8 -*-
"""Encrypted file-share persistence for GSI personal state and live snapshots.

Design goals
------------
* Shared-folder only: no HTTP/API/IP transport.
* AES-256-GCM encryption at rest.
* Master key never stored under ``GSI_PROFILE_ROOT``.
* One isolated folder per employee code.
* In-memory SQLite payload: no plaintext SQLite database is written to disk.
* Atomic replace + coarse lock for SMB/network-share safety.
* Explicit separation between personal profile state and fresh operational snapshot.
"""
from __future__ import annotations

import base64
import contextlib
import json
import math
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..core.text import clean_employee_code

ROOT_ENV = "GSI_PROFILE_ROOT"
KEY_ENV = "GSI_PROFILE_MASTER_KEY"
KEY_FILE_ENV = "GSI_PROFILE_KEY_FILE"
USER_KEY_ENV = "GSI_PROFILE_USER_KEY"
USER_KEY_FILE_ENV = "GSI_PROFILE_USER_KEY_FILE"
LOCK_TIMEOUT_ENV = "GSI_PROFILE_LOCK_TIMEOUT"

_MAGIC = b"GSI-PROFILE\x01"
_NONCE_BYTES = 12
_SCHEMA_VERSION = 1


class ProfileStoreError(RuntimeError):
    pass


class ProfileConfigurationError(ProfileStoreError):
    pass


class ProfileIntegrityError(ProfileStoreError):
    pass


def generate_master_key() -> str:
    """Return a URL-safe base64 encoded 256-bit master key."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def _decode_master_key(raw: str, *, source: str = KEY_ENV) -> bytes:
    value = (raw or "").strip()
    if not value:
        raise ProfileConfigurationError("کلید رمزگذاری GSI تنظیم نشده است.")
    try:
        padded = value + "=" * (-len(value) % 4)
        key = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except Exception as ex:
        raise ProfileConfigurationError(f"{source} باید Base64 معتبر باشد.") from ex
    if len(key) != 32:
        raise ProfileConfigurationError("کلید اصلی GSI باید دقیقاً ۳۲ بایت (AES-256) باشد.")
    return key


def _path_is_under(path: Path, root: Path) -> bool:
    try:
        p = os.path.normcase(str(path.resolve()))
        r = os.path.normcase(str(root.resolve()))
        return os.path.commonpath([p, r]) == r
    except Exception:
        return False


def _read_key_text(path: Path) -> str:
    raw = path.read_bytes()
    return raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig").strip()


def _read_master_key(root: Path) -> bytes:
    raw = os.environ.get(KEY_ENV, "").strip()
    if raw:
        return _decode_master_key(raw)
    key_file = os.environ.get(KEY_FILE_ENV, "").strip()
    if not key_file:
        raise ProfileConfigurationError(
            f"یکی از {KEY_ENV} یا {KEY_FILE_ENV} باید تنظیم شود؛ کلید داخل پوشه مشترک ذخیره نمی‌شود."
        )
    p = Path(key_file).expanduser()
    if _path_is_under(p, root):
        raise ProfileConfigurationError("فایل کلید نباید داخل GSI_PROFILE_ROOT یا زیرشاخه‌های آن باشد.")
    if not p.is_file():
        raise ProfileConfigurationError(f"فایل کلید پیدا نشد: {p}")
    return _decode_master_key(_read_key_text(p), source=f"فایل کلید اصلی «{p}»")


def derive_user_key(master_key: bytes, employee_code: str) -> bytes:
    """Derive a cryptographically isolated per-user root key from the central master key."""
    emp = _emp(employee_code)
    if len(master_key) != 32:
        raise ProfileConfigurationError("master_key باید ۳۲ بایت باشد.")
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"GSI-PERSONAL-USER-v1",
        info=("employee:" + emp).encode("ascii"),
    ).derive(master_key)


def derive_user_key_text(master_key_text: str, employee_code: str) -> str:
    key = derive_user_key(_decode_master_key(master_key_text), employee_code)
    return base64.urlsafe_b64encode(key).decode("ascii")


def _read_user_key(root: Path) -> Optional[bytes]:
    raw = os.environ.get(USER_KEY_ENV, "").strip()
    if raw:
        return _decode_master_key(raw, source=USER_KEY_ENV)
    key_file = os.environ.get(USER_KEY_FILE_ENV, "").strip()
    if not key_file:
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            candidate = Path(base) / "GSI" / "profile.key"
        else:
            candidate = Path(os.environ.get("GSI_HOME", os.path.join(os.path.expanduser("~"), ".gsi"))) / "profile.key"
        key_file = str(candidate) if candidate.is_file() else ""
    if not key_file:
        return None
    p = Path(key_file).expanduser()
    if _path_is_under(p, root):
        raise ProfileConfigurationError("فایل User Key نباید داخل GSI_PROFILE_ROOT باشد.")
    if not p.is_file():
        raise ProfileConfigurationError(f"فایل User Key پیدا نشد: {p}")
    return _decode_master_key(_read_key_text(p), source=f"فایل User Key «{p}»")


def _emp(value: str) -> str:
    emp = clean_employee_code(value)
    if not emp or not emp.isdigit():
        raise ProfileConfigurationError("کد پرسنلی برای Store باید عددی و غیرخالی باشد.")
    if len(emp) > 32:
        raise ProfileConfigurationError("کد پرسنلی نامعتبر است.")
    return emp


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _local_personal_config() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "GSI" / "personal_config.json"
    return Path(os.environ.get("GSI_HOME", os.path.join(os.path.expanduser("~"), ".gsi"))) / "personal_config.json"


def _configured_root() -> str:
    raw = os.environ.get(ROOT_ENV, "").strip()
    if raw:
        return raw
    cfg = _local_personal_config()
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            return str(data.get("profile_root", "")).strip()
        except Exception as ex:
            raise ProfileConfigurationError("تنظیمات محلی قابل خواندن نیست.") from ex
    return ""


@dataclass(frozen=True)
class UserPaths:
    root: Path
    employee_code: str

    @property
    def folder(self) -> Path:
        return self.root / self.employee_code

    @property
    def state_dir(self) -> Path:
        return self.folder / "state"

    @property
    def snapshot_dir(self) -> Path:
        return self.folder / "snapshot"

    @property
    def profile(self) -> Path:
        return self.state_dir / "profile.gsi"

    @property
    def snapshot(self) -> Path:
        return self.snapshot_dir / "current.gsi"

    def lock_for(self, target: Path) -> Path:
        return target.with_suffix(target.suffix + ".lock")


class _FileLock:
    """Never steal an old lock: timestamps cannot prove a network writer is dead."""
    def __init__(self, path: Path, timeout: float = 10.0, stale_after: float = 120.0):
        self.path = path
        if not math.isfinite(timeout) or timeout <= 0:
            raise ProfileConfigurationError("مهلت قفل باید عدد مثبت و محدود باشد.")
        self.timeout = timeout
        self.token = secrets.token_hex(24).encode("ascii")
        self.fd = None

    def __enter__(self):
        start = time.monotonic()
        while True:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if time.monotonic() - start >= self.timeout:
                    raise ProfileStoreError(f"قفل فایل آزاد نشد: {self.path.name}؛ پس از اطمینان از توقف نویسنده، مدیر قفل را بررسی کند.")
                time.sleep(min(0.08, self.timeout))
                continue
            except OSError as ex:
                raise ProfileStoreError(
                    f"پوشه مشترک GSI در دسترس نیست: {self.path.parent} — "
                    "اتصال درایو شبکه و دسترسی Modify روی state/ را بررسی کنید."
                ) from ex
            try:
                os.write(self.fd, self.token)
                os.fsync(self.fd)
            except OSError:
                os.close(self.fd)
                self.fd = None
                with contextlib.suppress(OSError):
                    self.path.unlink()
                raise
            return self

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        with contextlib.suppress(OSError):
            if self.path.read_bytes() == self.token:
                self.path.unlink()


class EncryptedUserStore:
    """Encrypted per-user store backed by an in-memory SQLite database."""

    def __init__(self, root: str | Path, master_key: bytes, employee_code: str, *, key_is_user: bool = False):
        self.paths = UserPaths(Path(root).expanduser(), _emp(employee_code))
        raw_key = bytes(master_key)
        if len(raw_key) != 32:
            raise ProfileConfigurationError("کلید GSI باید ۳۲ بایت باشد.")
        self.key_is_user = key_is_user
        if not hasattr(sqlite3.Connection, "serialize"):
            raise ProfileConfigurationError("Python 3.11+ با پشتیبانی SQLite serialize لازم است.")
        self._user_key = raw_key if key_is_user else derive_user_key(raw_key, self.paths.employee_code)
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        if not key_is_user:
            self.paths.snapshot_dir.mkdir(parents=True, exist_ok=True)
        raw_timeout = os.environ.get(LOCK_TIMEOUT_ENV, "10").strip()
        try:
            self.lock_timeout = float(raw_timeout)
        except ValueError:
            raise ProfileConfigurationError("مهلت قفل نامعتبر است.")
        if not math.isfinite(self.lock_timeout) or self.lock_timeout <= 0:
            raise ProfileConfigurationError("مهلت قفل باید مثبت و محدود باشد.")

    @classmethod
    def from_env(cls, employee_code: str) -> "EncryptedUserStore":
        raw_root = _configured_root()
        if not raw_root:
            raise ProfileConfigurationError(
                f"{ROOT_ENV} تنظیم نشده و personal_config.json هم مسیر Share ندارد."
            )
        root = Path(raw_root).expanduser()
        if not root.is_dir():
            raise ProfileConfigurationError("پوشه شبکه در دسترس نیست؛ مسیر و اتصال را بررسی کنید.")
        user_key = _read_user_key(root)
        if user_key is not None:
            return cls(root, user_key, employee_code, key_is_user=True)
        return cls(root, _read_master_key(root), employee_code)

    @classmethod
    def from_master_env(cls, employee_code: str) -> "EncryptedUserStore":
        """Central-writer constructor. Never accepts a per-user key."""
        raw_root = os.environ.get(ROOT_ENV, "").strip()
        if not raw_root:
            raise ProfileConfigurationError(f"{ROOT_ENV} تنظیم نشده است.")
        root = Path(raw_root).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return cls(root, _read_master_key(root), employee_code)

    @property
    def employee_code(self) -> str:
        return self.paths.employee_code

    def _derive_key(self, kind: str) -> bytes:
        info = f"gsi-personal-v1:{kind}:{self.employee_code}".encode("utf-8")
        return HKDF(
            algorithm=hashes.SHA256(), length=32,
            salt=b"GSI-PERSONAL-STORE-v1", info=info,
        ).derive(self._user_key)

    def _aad(self, kind: str) -> bytes:
        return _MAGIC + b"|" + kind.encode("ascii") + b"|" + self.employee_code.encode("ascii")

    def _decrypt(self, path: Path, kind: str) -> Optional[bytes]:
        try:
            blob = path.read_bytes()
        except FileNotFoundError:
            if not self.paths.root.is_dir() or not self.paths.folder.is_dir():
                raise ProfileStoreError("پوشه شبکه در دسترس نیست؛ داده خالی تلقی نشد.")
            return None
        if len(blob) < len(_MAGIC) + _NONCE_BYTES + 16 or not blob.startswith(_MAGIC):
            raise ProfileIntegrityError(f"فرمت فایل رمزگذاری‌شده معتبر نیست: {path.name}")
        nonce = blob[len(_MAGIC):len(_MAGIC) + _NONCE_BYTES]
        ciphertext = blob[len(_MAGIC) + _NONCE_BYTES:]
        try:
            return AESGCM(self._derive_key(kind)).decrypt(nonce, ciphertext, self._aad(kind))
        except InvalidTag as ex:
            raise ProfileIntegrityError(
                f"رمزگشایی {path.name} ناموفق بود؛ فایل دستکاری شده یا کلید اشتباه است."
            ) from ex

    def _encrypt(self, plaintext: bytes, kind: str) -> bytes:
        nonce = secrets.token_bytes(_NONCE_BYTES)
        ciphertext = AESGCM(self._derive_key(kind)).encrypt(nonce, plaintext, self._aad(kind))
        return _MAGIC + nonce + ciphertext

    def _atomic_write(self, path: Path, blob: bytes) -> None:
        tmp = path.with_name(path.name + f".{os.getpid()}.{secrets.token_hex(4)}.tmp")
        try:
            with open(tmp, "wb") as fh:
                fh.write(blob)
                fh.flush()
                os.fsync(fh.fileno())
            for attempt in range(4):
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()

    @staticmethod
    def _new_db(employee_code: str, kind: str) -> sqlite3.Connection:
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS meta(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kv(
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(namespace,key)
            );
            CREATE TABLE IF NOT EXISTS audit(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                event TEXT NOT NULL,
                detail_json TEXT NOT NULL
            );
        """)
        con.executemany(
            "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
            [("schema_version", str(_SCHEMA_VERSION)), ("employee_code", employee_code),
             ("kind", kind), ("created_at", _utc()), ("updated_at", _utc())],
        )
        con.commit()
        return con

    def _load_db(self, path: Path, kind: str) -> sqlite3.Connection:
        plain = self._decrypt(path, kind)
        if plain is None:
            return self._new_db(self.employee_code, kind)
        con = sqlite3.connect(":memory:")
        try:
            con.deserialize(plain)
            con.execute("PRAGMA trusted_schema=OFF")
            con.execute("PRAGMA temp_store=MEMORY")
            meta = dict(con.execute("SELECT key,value FROM meta"))
            if meta.get("employee_code") != self.employee_code or meta.get("kind") != kind or meta.get("schema_version") != str(_SCHEMA_VERSION):
                raise ValueError("Store metadata mismatch")
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Store integrity check failed")
        except Exception as ex:
            con.close()
            raise ProfileIntegrityError(f"ساختار فایل معتبر نیست: {path.name}") from ex
        return con

    def _save_db(self, con: sqlite3.Connection, path: Path, kind: str) -> None:
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('updated_at',?)", (_utc(),))
        con.commit()
        plain = con.serialize()
        self._atomic_write(path, self._encrypt(plain, kind))

    @contextlib.contextmanager
    def _db(self, kind: str, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        if kind not in {"profile", "snapshot"}:
            raise ValueError("Unknown store kind")
        if write and kind == "snapshot" and self.key_is_user:
            raise ProfileStoreError("انتشار داده فقط با اجرای مرکزی مجاز است.")
        path = self.paths.profile if kind == "profile" else self.paths.snapshot
        lock_path = self.paths.lock_for(path)
        lock_ctx = _FileLock(lock_path, self.lock_timeout) if write else contextlib.nullcontext()
        with lock_ctx:
            con = self._load_db(path, kind)
            try:
                yield con
                if write:
                    self._save_db(con, path, kind)
            finally:
                con.close()

    def get(self, namespace: str, key: str, default: Any = None, *, kind: str = "profile") -> Any:
        with self._db(kind) as con:
            row = con.execute(
                "SELECT value_json FROM kv WHERE namespace=? AND key=?", (namespace, key)
            ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except json.JSONDecodeError as ex:
            raise ProfileIntegrityError("JSON داخل Store معتبر نیست.") from ex

    def namespace(self, namespace: str, *, kind: str = "profile") -> Dict[str, Any]:
        with self._db(kind) as con:
            rows = con.execute(
                "SELECT key,value_json FROM kv WHERE namespace=? ORDER BY key", (namespace,)
            ).fetchall()
        try:
            return {k: json.loads(v) for k, v in rows}
        except json.JSONDecodeError as ex:
            raise ProfileIntegrityError("JSON داخل Store معتبر نیست.") from ex

    def set(self, namespace: str, key: str, value: Any, *, kind: str = "profile",
            audit_event: Optional[str] = None) -> None:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)
        with self._db(kind, write=True) as con:
            con.execute(
                "INSERT OR REPLACE INTO kv(namespace,key,value_json,updated_at) VALUES(?,?,?,?)",
                (namespace, key, encoded, _utc()),
            )
        if audit_event:
            from gsi.warehouse.store import Warehouse
            Warehouse().audit(audit_event, {'namespace':namespace,'key':key,'employee':str(self.paths.folder),'operation':'profile_set'})

    def merge(self, namespace: str, values: Mapping[str, Any], *, kind: str = "profile",
              audit_event: str = "merge") -> None:
        with self._db(kind, write=True) as con:
            now = _utc()
            for key, value in values.items():
                con.execute(
                    "INSERT OR REPLACE INTO kv(namespace,key,value_json,updated_at) VALUES(?,?,?,?)",
                    (namespace, str(key), json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False), now),
                )
        from gsi.warehouse.store import Warehouse
        Warehouse().audit(audit_event, {'namespace':namespace,'keys':sorted(map(str,values)),'employee':str(self.paths.folder),'operation':'profile_merge'})

    def replace_snapshot(self, payload: Mapping[str, Any], *, source_run_id: str = "") -> None:
        """Replace the user's current operational snapshot atomically.

        Snapshot is fresh data, not preference state. The previous snapshot is not
        merged silently, preventing stale fields from surviving a new pipeline run.
        """
        if self.key_is_user:
            raise ProfileStoreError("انتشار داده فقط با اجرای مرکزی مجاز است.")
        path = self.paths.snapshot
        with _FileLock(self.paths.lock_for(path), self.lock_timeout):
            con = self._new_db(self.employee_code, "snapshot")
            try:
                now = _utc()
                for key, value in payload.items():
                    con.execute(
                        "INSERT OR REPLACE INTO kv(namespace,key,value_json,updated_at) VALUES('current',?,?,?)",
                        (str(key), json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False), now),
                    )
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('source_run_id',?)", (source_run_id,))
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('refreshed_at',?)", (now,))
                self._save_db(con, path, "snapshot")
            finally:
                con.close()

    def snapshot_context(self):
        with self._db("snapshot") as con:
            data = {k: json.loads(v) for k, v in con.execute("SELECT key,value_json FROM kv WHERE namespace='current'")}
            meta = dict(con.execute("SELECT key,value FROM meta"))
        return data, meta

    def current_snapshot(self) -> Dict[str, Any]:
        return self.namespace("current", kind="snapshot")

    def metadata(self, *, kind: str = "profile") -> Dict[str, str]:
        with self._db(kind) as con:
            return dict(con.execute("SELECT key,value FROM meta ORDER BY key").fetchall())

    def audit(self, limit: int = 50) -> list[Dict[str, Any]]:
        with self._db("profile") as con:
            rows = con.execute(
                "SELECT ts,event,detail_json FROM audit ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 500)),)
            ).fetchall()
        legacy=[{"ts": ts, "event": event, "detail": json.loads(detail)} for ts, event, detail in rows]
        from gsi.warehouse.store import Warehouse
        with Warehouse().db() as c:
            recent=c.execute("SELECT at,kind,payload FROM wh_audit WHERE json_extract(payload,'$.employee')=? ORDER BY id DESC LIMIT ?",(str(self.paths.folder),max(1,min(int(limit),500)))).fetchall()
        return ([{'ts':ts,'event':event,'detail':json.loads(detail)} for ts,event,detail in recent]+legacy)[:limit]

    def integrity_check(self, *, kind: str = "profile") -> str:
        with self._db(kind) as con:
            row = con.execute("PRAGMA integrity_check").fetchone()
            return row[0] if row else "unknown"

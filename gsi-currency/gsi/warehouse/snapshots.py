"""نماهای «به تاریخ اجرا» روی جدول‌های نسخه‌دار کسب‌وکار؛ نبودن یک ردیف یعنی حذف کسب‌وکاری نیست.

نسخه ۱ پس از هر اجرا کپی کامل همه جدول‌های ``dwh_*`` را در ``snap_*`` می‌نوشت. در نسخه ۲ هر
ردیف بازه اعتبار ``[from_seq, to_seq)`` دارد، پس وضعیت هر اجرا بدون کپی قابل خواندن است:
ردیف‌هایی که ``from_seq <= P`` و ``to_seq`` خالی یا بزرگ‌تر از ``P`` باشد.

``bind_published`` روی یک اتصال خواندنی، برای هر جدول ``dwh_*`` یک نمای موقت هم‌نام می‌سازد
با همان ستون‌ها و همان ترتیب نسخه ۱ و به تاریخ اجرای منتشرشده؛ خواننده‌ها بی‌تغییر می‌مانند.
"""
from __future__ import annotations
import re

#: «CREATE VIEW نام [(ستون‌ها)] AS تعریف» — تعریف view برای بستن دوباره به نماهای موقت
_VIEW_SQL = re.compile(r'^\s*CREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:"[^"]+"|\S+?)\s*(?:\([^)]*\)\s*)?AS\b(.*)$',
                       re.I | re.S)


def tables(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'dwh_*' ORDER BY name")]


def _views(conn):
    return conn.execute("SELECT name,sql FROM sqlite_master WHERE type='view' AND name GLOB 'dwh_*' ORDER BY name").fetchall()


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _literal(text) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def published(conn):
    """``(run_id, seq)`` اجرای منتشرشده کسب‌وکار، یا ``(None, None)`` اگر هنوز چیزی منتشر نشده."""
    row = conn.execute(
        "SELECT c.run_id,r.seq FROM wh_current c JOIN wh_run r ON r.id=c.run_id "
        "WHERE c.slot IN ('dwh','report') ORDER BY CASE c.slot WHEN 'dwh' THEN 0 ELSE 1 END LIMIT 1").fetchone()
    return (row[0], int(row[1])) if row else (None, None)


def as_of_sql(name: str, seq, run_id, conn=None) -> str:
    """پرس‌وجوی ستون‌های نسخه ۱ یک جدول به تاریخ اجرای ``seq``؛ ``seq=None`` یعنی بدون ردیف.

    با ``conn``، ستونی که هنوز در فایل نیست (برنامه تازه‌تر از آخرین ساخت) ``NULL`` خوانده می‌شود.
    """
    from .business_dwh import TABLES, logical_projection, physical_columns
    t = TABLES[name]
    physical = physical_columns(conn, name) if conn is not None else None
    projection = logical_projection(t, _literal(run_id or ''), physical)
    if seq is None:
        return f'SELECT {projection} FROM main.{_q(name)} WHERE 0'
    p = int(seq)
    return (f'SELECT {projection} FROM main.{_q(name)} '
            f'WHERE from_seq<={p} AND (to_seq IS NULL OR to_seq>{p})')


def _mask(conn, name: str) -> None:
    """نمای خالی با همان ستون‌ها: داده‌ای که نسخه منتشرشده ندارد خوانده نمی‌شود."""
    conn.execute(f'CREATE TEMP VIEW {_q(name)} AS SELECT * FROM main.{_q(name)} WHERE 0')


def bind_published(conn) -> None:
    """Connection-local views pin all business reads to one published run."""
    from .business_dwh import TABLES
    rid, seq = published(conn)
    for name in tables(conn):
        if name in TABLES:
            conn.execute(f'CREATE TEMP VIEW {_q(name)} AS ' + as_of_sql(name, seq, rid, conn))
        else:
            # جدولی که قالب نسخه‌دارش شناخته نیست نمی‌تواند وضعیت منتشرشده‌اش را ثابت کند
            _mask(conn, name)
    # Rebind dependent views so they resolve the connection-local base tables.
    for name, sql in _views(conn):
        m = _VIEW_SQL.match(sql or "")
        if m:
            conn.execute(f'CREATE TEMP VIEW {_q(name)} AS ' + m.group(1))
        else:
            _mask(conn, name)

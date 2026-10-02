from __future__ import annotations

"""Business-aware SQLite Core for GSI.

This module deliberately consumes adapter outputs at their native grains. It does
not reconstruct business relationships from the flattened dashboard mart.
Only co-observed keys in the same evidence row create a direct relationship.

نسخه ۲ انبار داده
-----------------
* هر جدول ``dwh_*`` نسخه‌دار است: هر ردیف بازه ``[from_seq, to_seq)`` دارد. ردیفی که عوض
  شود یا دیگر دیده نشود فقط «بسته» می‌شود و نسخه تازه کنارش می‌نشیند؛ هیچ ردیفی پاک
  نمی‌شود و ساختن دوباره از صفر در کار نیست.
* خواننده‌ها با ``snapshots.bind_published`` همان ستون‌های قبلی را «به تاریخ اجرای
  منتشرشده» می‌بینند؛ کپی Snapshot برای هر اجرا دیگر ساخته نمی‌شود.
* ``dwh_fact_source_row`` کنار گذاشته شد: هر ردیف منبع با همه نسخه‌هایش در ``src_record``
  است و فریم دقیق هر اجرا در بایگانی Parquet.
* جدول واقعیتی که فریم ورودی‌اش از آخرین ساخت عوض نشده دوباره ساخته نمی‌شود.
"""

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple
import hashlib
import json

import pandas as pd
from gsi.core.text import clean_order_ref, clean_part_no, clean_key, is_empty_val

from gsi.adapters.base import (
    KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER, KEY_PR, KEY_PO, KEY_REG, KEY_REG_FILE,
)
from .store import Warehouse, RUN, dumps, now


ENTITY_COLS = {
    "ORDER": KEY_ORDER,
    "MATERIAL": KEY_MATERIAL,
    "BL": KEY_BL,
    "REG": KEY_REG,
    "REG_FILE": KEY_REG_FILE,
    "PR": KEY_PR,
    "PO": KEY_PO,
    "EMP": KEY_EMP,
}

# Only direct co-observation creates a bridge. Derived/transitive paths remain
# query-time paths so evidence is never confused with inference.
DIRECT_PAIRS = (
    ("ORDER", "MATERIAL"),
    ("ORDER", "PR"),
    ("PR", "MATERIAL"),
    ("PR", "PO"),
    ("PO", "MATERIAL"),
    ("PO", "BL"),  # roadmap profile 3: inbound reference document + BL
    ("PO", "REG_FILE"),  # roadmap profile 2: native PO registration-file evidence
    ("ORDER", "BL"),
    ("BL", "REG"),
    ("ORDER", "REG"),
    ("REG_FILE", "REG"),
    ("REG_FILE", "ORDER"),
    ("ORDER", "EMP"),
)

#: R8: ستون کمکی adapter SAP برای گروه‌بندی قلم خالی (ROW<SAP_SOURCE_ROW>)
SAP_PR_ITEM_GROUP = "SAP_PR_ITEM_GROUP"
SAP_PO_ITEM_GROUP = "SAP_PO_ITEM_GROUP"

_SOURCE_ALIASES = {
    "ntsw": {"REG": "NTSW_KEY_REG"},
    "sata": {"REG": "SATA_KEY_REG"},
    "fx_transaction": {"REG": "FX_KEY_REG"},
    "credit": {"REG": "CRD_KEY_REG"},
    "ilappend": {"REG": "IL_KEY_REG"},
    # R8: کد پرسنلی کارشناس در فایل کارشناسان پیشوندی است؛ بی این، رابطه ORDER+EMP ساخته نمی‌شد.
    "moghavemat": {"EMP": "MOGH_KEY_EMP"},
}


# ─────────────────────────── جدول‌ها ───────────────────────────
# نقش ستون‌ها: key = کلید طبیعی، value = مقدار نسخه‌دار، first = اولین اجرایی که کلید دیده شد
# (از نسخه‌ای به نسخه بعد منتقل می‌شود)، last/run = شناسه اجرای منتشرشده در نما، id = vid.
@dataclass(frozen=True)
class Col:
    name: str
    role: str
    decl: str = "TEXT NOT NULL"


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: Tuple[Col, ...]

    @property
    def keys(self) -> Tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.role == "key")

    @property
    def values(self) -> Tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.role == "value")

    @property
    def has_first(self) -> bool:
        return any(c.role == "first" for c in self.columns)

    @property
    def stored(self) -> Tuple[Col, ...]:
        return tuple(c for c in self.columns if c.role in ("key", "value", "first"))


def _dim(name: str, key: str) -> TableSpec:
    return TableSpec(name, (Col(key, "key"), Col("first_seen_run", "first"), Col("last_seen_run", "last")))


_PAYLOAD = Col("payload", "value")
_LAST = Col("last_seen_run", "last")

TABLES: Dict[str, TableSpec] = {t.name: t for t in (
    TableSpec("dwh_entity", (Col("entity_type", "key"), Col("business_key", "key"),
                             Col("first_seen_run", "first"), _LAST)),
    _dim("dwh_dim_order", "order_key"),
    _dim("dwh_dim_material", "material_key"),
    _dim("dwh_dim_bl", "bl_key"),
    _dim("dwh_dim_registration", "reg_key"),
    _dim("dwh_dim_registration_file", "reg_file_key"),
    _dim("dwh_dim_pr", "pr_key"),
    _dim("dwh_dim_po", "po_key"),
    _dim("dwh_dim_employee", "emp_key"),
    TableSpec("dwh_relation", (Col("left_type", "key"), Col("left_key", "key"), Col("right_type", "key"),
                               Col("right_key", "key"), Col("source", "key"), Col("frame", "key"),
                               Col("rule", "key"), Col("first_seen_run", "first"), _LAST,
                               Col("evidence_count", "value", "INTEGER NOT NULL DEFAULT 1"))),
    TableSpec("dwh_fact_supply_position", (Col("order_key", "key"), Col("material_key", "key"), _PAYLOAD, _LAST)),
    TableSpec("dwh_bridge_order_material_pr_item", (
        Col("order_key", "key"), Col("material_key", "key"), Col("pr_key", "key"),
        Col("pr_item", "key", "TEXT NOT NULL DEFAULT ''"),
        Col("evidence_count", "value", "INTEGER NOT NULL DEFAULT 1"),
        Col("source_rows", "value", "TEXT NOT NULL DEFAULT ''"), _PAYLOAD, _LAST)),
    TableSpec("dwh_fact_oracle_material", (Col("material_key", "key"), _PAYLOAD, _LAST)),
    TableSpec("dwh_fact_sap_pr_item", (Col("pr_key", "key"), Col("pr_item", "key", "TEXT NOT NULL DEFAULT ''"),
                                       Col("material_key", "value", "TEXT"), _PAYLOAD, _LAST)),
    TableSpec("dwh_fact_sap_po_item", (Col("po_key", "key"), Col("po_item", "key", "TEXT NOT NULL DEFAULT ''"),
                                       Col("pr_key", "value", "TEXT"),
                                       Col("pr_item", "value", "TEXT NOT NULL DEFAULT ''"),
                                       Col("material_key", "value", "TEXT"), _PAYLOAD, _LAST)),
    TableSpec("dwh_fact_sap_workflow", (Col("workflow_key", "key"), Col("pr_key", "value"),
                                        Col("pr_item", "value", "TEXT NOT NULL DEFAULT ''"),
                                        Col("event_date", "value", "TEXT"), _PAYLOAD, _LAST)),
    TableSpec("dwh_fact_ntsw_allocation_request", (Col("request_key", "key"), Col("reg_key", "value"),
                                                   _PAYLOAD, _LAST)),
    TableSpec("dwh_fact_ntsw_commitment", (Col("reg_key", "key"), _PAYLOAD, _LAST)),
    TableSpec("dwh_unresolved_relation", (Col("id", "id"), Col("run_id", "run"), Col("source", "key"),
                                          Col("frame", "key"), Col("row_hash", "key"),
                                          Col("reason_code", "key"), _PAYLOAD)),
)}

#: شاخص‌های جست‌وجوی خواننده‌ها (همان شاخص‌های نسخه ۱)
_LOOKUP_INDEXES = (
    ("dwh_relation_left", "dwh_relation", ("left_type", "left_key")),
    ("dwh_relation_right", "dwh_relation", ("right_type", "right_key")),
    ("dwh_ompi_order_material", "dwh_bridge_order_material_pr_item", ("order_key", "material_key")),
    ("dwh_ompi_pr", "dwh_bridge_order_material_pr_item", ("pr_key",)),
    ("dwh_sap_pr_material", "dwh_fact_sap_pr_item", ("material_key",)),
    ("dwh_sap_po_pr", "dwh_fact_sap_po_item", ("pr_key", "pr_item")),
    ("dwh_sap_workflow_pr", "dwh_fact_sap_workflow", ("pr_key", "event_date")),
    ("dwh_entity_key", "dwh_entity", ("business_key",)),
    ("dwh_unresolved_frame", "dwh_unresolved_relation", ("source", "frame")),
)

#: فریم ورودی هر جدول واقعیت؛ اگر از آخرین ساخت عوض نشده باشد جدول دست نمی‌خورد
FACT_INPUTS = {
    "dwh_fact_supply_position": ("moghavemat", "inventory"),
    "dwh_bridge_order_material_pr_item": ("moghavemat", "order_material_pr_item"),
    "dwh_fact_sap_pr_item": ("sap", "pr_items"),
    "dwh_fact_sap_po_item": ("sap", "po_items"),
    "dwh_fact_sap_workflow": ("sap", "workflow_rows"),
    "dwh_fact_oracle_material": ("oracle", "main"),
    "dwh_fact_ntsw_allocation_request": ("ntsw", "allocation_rows"),
    "dwh_fact_ntsw_commitment": ("ntsw", "commitment"),
}


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _trigger_ddl(t: TableSpec) -> str:
    guard = " OR ".join([f"NEW.{_q(c.name)} IS NOT OLD.{_q(c.name)}" for c in t.stored]
                        + ["NEW.vid IS NOT OLD.vid", "NEW.from_seq IS NOT OLD.from_seq",
                           "NEW.vhash IS NOT OLD.vhash"])
    return f"""
CREATE TRIGGER IF NOT EXISTS {t.name}_keep BEFORE DELETE ON {t.name}
BEGIN SELECT RAISE(ABORT,'GSI business history is append-only: {t.name}'); END;
CREATE TRIGGER IF NOT EXISTS {t.name}_close_once BEFORE UPDATE ON {t.name}
WHEN OLD.to_seq IS NOT NULL OR NEW.to_seq IS NULL OR NEW.to_seq<=OLD.from_seq OR {guard}
BEGIN SELECT RAISE(ABORT,'GSI business rows are closed once and never edited: {t.name}'); END;
"""


def _table_ddl(t: TableSpec) -> str:
    cols = ",\n ".join(f"{_q(c.name)} {c.decl}" for c in t.stored)
    keys = ",".join(_q(k) for k in t.keys)
    return f"""
CREATE TABLE IF NOT EXISTS {t.name}(
 vid INTEGER PRIMARY KEY,
 {cols},
 from_seq INTEGER NOT NULL,
 to_seq INTEGER,
 vhash TEXT NOT NULL,
 UNIQUE({keys},from_seq));
CREATE UNIQUE INDEX IF NOT EXISTS {t.name}_open ON {t.name}({keys}) WHERE to_seq IS NULL;
""" + _trigger_ddl(t)


BUSINESS_SCHEMA = "".join(_table_ddl(t) for t in TABLES.values()) + "".join(
    f"CREATE INDEX IF NOT EXISTS {name} ON {table}({','.join(_q(c) for c in cols)});\n"
    for name, table, cols in _LOOKUP_INDEXES) + r'''
CREATE TABLE IF NOT EXISTS wh_dwh_build_state(
 name TEXT PRIMARY KEY,
 input_sig TEXT NOT NULL,
 seq INTEGER NOT NULL);

DROP VIEW IF EXISTS dwh_registration_hub;
CREATE VIEW dwh_registration_hub AS
WITH regs AS (SELECT DISTINCT left_key f,right_key r FROM dwh_relation WHERE left_type='REG_FILE' AND right_type='REG'),
ords AS (SELECT DISTINCT left_key f,right_key o FROM dwh_relation WHERE left_type='REG_FILE' AND right_type='ORDER'),
card AS (SELECT business_key f,(SELECT count(*) FROM regs WHERE f=business_key) nr,
(SELECT count(*) FROM ords WHERE f=business_key) no FROM dwh_entity WHERE entity_type='REG_FILE')
SELECT card.f reg_file_key,regs.r reg_key,ords.o order_key FROM card
LEFT JOIN regs ON regs.f=card.f LEFT JOIN ords ON ords.f=card.f WHERE nr<=1 AND no<=1
UNION ALL SELECT card.f,regs.r,NULL FROM card JOIN regs ON regs.f=card.f WHERE nr>1 OR no>1
UNION ALL SELECT card.f,NULL,ords.o FROM card JOIN ords ON ords.f=card.f WHERE nr>1 OR no>1;
'''


def logical_projection(t: TableSpec, run_literal: str, physical=None) -> str:
    """ستون‌های نسخه ۱ جدول به همان ترتیب، برای نمای «به تاریخ» اجرای منتشرشده.

    ``physical``: ستون‌های واقعی جدول در فایل؛ ستونی که هنوز در فایل نیست ``NULL`` خوانده می‌شود.
    """
    out = []
    for c in t.columns:
        if c.role in ("key", "value", "first"):
            out.append(_q(c.name) if physical is None or c.name in physical else f"NULL AS {_q(c.name)}")
        elif c.role in ("last", "run"):
            out.append(f"{run_literal} AS {_q(c.name)}")
        elif c.role == "id":
            out.append(f"vid AS {_q(c.name)}")
    return ",".join(out)


# ─────────────────────────── مقدارها ───────────────────────────
def _clean(v) -> str:
    if v is None or v is pd.NA:
        return ""
    t = str(v).strip()
    if t.lower() in {"nan", "none", "<na>"}:
        return ""
    return t


def _clean_col(df: pd.DataFrame, col: str) -> pd.Series:
    """``_clean`` خانه‌به‌خانه؛ ستون نبود یعنی رشته خالی (همان ``row.get(col, "")``)."""
    if col not in df.columns:
        return pd.Series("", index=df.index, dtype=object)
    return df[col].map(_clean).astype(object)


# ─────────────────────────── کلید متعارف (R8) ───────────────────────────
def _reg8(v) -> str:
    # R8: همان قاعده registration_bridge._clean_reg (فقط ۸ رقم)
    from gsi.resolve.registration_bridge import _clean_reg
    return _clean_reg(v)


def _reg_file(v) -> str:
    from gsi.resolve.registration_bridge import _clean_reg_file
    return _clean_reg_file(v)


def _item(v) -> str:
    # R8: همان قاعده a60_finance ``_clean_item`` (صفرهای ابتدای شماره قلم حذف)
    from gsi.core.text import clean_key
    s = clean_key(v)
    return s.lstrip("0") or ("0" if s else "")


def _canon_rules() -> List[Tuple[str, Tuple[str, ...], object]]:
    """(موجودیت، ستون‌ها، تابع متعارف‌سازی) برای همه ستون‌های کلیدی که انبار داده می‌خواند."""
    from gsi.core.text import clean_bl, clean_employee_code, clean_key, clean_order_ref, clean_part_no
    reg_cols = (KEY_REG,) + tuple(dict.fromkeys(
        c for aliases in _SOURCE_ALIASES.values() for t, c in aliases.items() if t == "REG"))
    emp_cols = (KEY_EMP,) + tuple(dict.fromkeys(
        c for aliases in _SOURCE_ALIASES.values() for t, c in aliases.items() if t == "EMP"))
    return [
        ("ORDER", (KEY_ORDER,), clean_order_ref),
        ("MATERIAL", (KEY_MATERIAL, "SAP_PO_MATERIAL"), clean_part_no),
        ("BL", (KEY_BL,), clean_bl),
        ("REG", reg_cols, _reg8),
        ("REG_FILE", (KEY_REG_FILE,), _reg_file),
        ("PR", (KEY_PR, "SAP_PO_PR"), clean_key),
        ("PO", (KEY_PO,), clean_key),
        ("EMP", emp_cols, clean_employee_code),
        ("ITEM", ("SAP_PO_PR_ITEM", "SAP_PR_ITEM"), _item),
    ]


def canonical_sources(sources: Mapping[str, Mapping[str, pd.DataFrame]]):
    """R8: کلیدهای کسب‌وکار همه فریم‌ها با همان قواعد adapterها و گزارش یکسان می‌شوند.

    ``_clean`` فقط فاصله را می‌گرفت؛ «603128A-Item 1» و «603128A»، یا «00010» و «10»، دو
    کلید جدا می‌شدند. فقط فریمی که ستون کلیدش واقعاً عوض می‌شود کپی سطحی می‌شود و بقیه همان
    شیء ورودی‌اند؛ فریم ورودی (و بایگانی dwh_input) دست نمی‌خورد. کلید نامعتبر (مثلاً ثبت
    سفارش غیر ۸ رقمی یا شماره پرونده «0») خالی می‌شود.
    """
    from gsi.dataio.logging_setup import log
    rules = _canon_rules()
    stats: Dict[str, List[int]] = {}
    out: Dict[str, Dict[str, pd.DataFrame]] = {}
    for source, frames in sources.items():
        if not isinstance(frames, Mapping):
            out[source] = frames
            continue
        new_frames = {}
        for frame, df in frames.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                new_frames[frame] = df
                continue
            changes = {}
            for typ, cols, fn in rules:
                for col in cols:
                    if col not in df.columns:
                        continue
                    before = _clean_col(df, col)
                    uniq = pd.unique(before.to_numpy())
                    mapping = {v: (fn(v) if v else "") for v in uniq}
                    after = before.map(mapping).astype(object)
                    diff = after != before
                    if not diff.any():
                        continue
                    st = stats.setdefault(typ, [0, 0])
                    invalid = diff & (after == "")
                    st[0] += int((diff & ~invalid).sum())
                    st[1] += int(invalid.sum())
                    changes[col] = after
            if changes:
                df = df.copy(deep=False)
                for col, values in changes.items():
                    df[col] = values
            new_frames[frame] = df
        out[source] = new_frames
    if stats:
        log.info("   🔑 [dwh] کلیدهای متعارف (R8) — " + " | ".join(
            f"{typ}: {c} عوض شد، {i} نامعتبر" for typ, (c, i) in sorted(stats.items())))
    return out


def _entity_key(kind: str, value) -> str:
    """Normalize only documented identifiers; never create a placeholder hub."""
    raw = _clean(value)
    if not raw or is_empty_val(raw) or raw == "*":
        return ""
    if kind == "ORDER":
        if raw in {"0", "1", "2"}:
            return ""
        key = clean_order_ref(raw)
        if key.replace(" ", "") in {"بدونسفارش", "فاقدسفارش", "ورودموقت", "برگشتازصادرات"}:
            return ""
        return key
    if kind == "MATERIAL":
        return clean_part_no(raw)
    if kind == "BL":
        # Leading zeroes are significant in shipping identifiers.
        return raw.upper()
    if kind == "REG_FILE" and raw in {"0", "1", "2"}:
        return ""
    return clean_key(raw)


def _source_business_keys(source: str, row: pd.Series, columns) -> dict[str, str]:
    """Extract native business keys, including source-prefixed copies.

    The flat mart may need SATA to seed KEY_REG, but the business DWH must retain
    source-native REG evidence independently.  This keeps NTSW/source relations
    usable even when the dashboard merge path is incomplete.
    """
    keys = {typ: _clean(row.get(col, "")) for typ, col in ENTITY_COLS.items() if col in columns}
    for typ, col in _SOURCE_ALIASES.get(source, {}).items():
        if not keys.get(typ) and col in columns:
            keys[typ] = _clean(row.get(col, ""))
    return keys


def _frame_keys(source: str, df: pd.DataFrame) -> Dict[str, pd.Series]:
    """همان ``_source_business_keys``، ستونی."""
    keys = {typ: _clean_col(df, col) for typ, col in ENTITY_COLS.items() if col in df.columns}
    for typ, col in _SOURCE_ALIASES.get(source, {}).items():
        if col in df.columns:
            alias = _clean_col(df, col)
            keys[typ] = alias if typ not in keys else keys[typ].where(keys[typ] != "", alias)
    keys = {typ: series.map(lambda v: _entity_key(typ, v)) for typ, series in keys.items()}
    return keys


def _row_payload(row) -> str:
    return dumps({str(k): (None if pd.isna(v) else v) for k, v in row.items()})


def _with_content(df: pd.DataFrame, location: frozenset):
    """ردیف‌ها (dict) همراه «محتوای» متعارف هر ردیف، بدون ستون‌های جای ردیف.

    نسخه‌سازی با محتوا است، با همان قواعد سوابق منبع (خانه خالی = رشته خالی، ۱٫۰ = ۱): ردیفی که
    فقط جایش در فایل عوض شده یا فایلش دوباره ذخیره شده نسخه تازه نمی‌سازد. payload هر نسخه جایی را
    نشان می‌دهد که آن محتوا اولین بار دیده شد؛ فایل‌ها با اثرانگشت بایگانی‌اند و آن جا همیشه باز می‌شود.
    """
    from .history import _row_payloads
    columns = sorted((c for c in df.columns if str(c) not in location), key=str)
    return zip(_records(df), _row_payloads(df, columns))


def _records(df: pd.DataFrame):
    columns = list(df.columns)
    for values in df.itertuples(index=False, name=None):
        yield dict(zip(columns, values))


def _row_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _location(specs, source: str, frame: str) -> frozenset:
    """ستون‌های جای ردیف یک فریم از ``source_keys.yaml`` (همان تعریف سوابق منبع)."""
    return frozenset(specs.get(f"{source}/{frame}").location) if specs is not None else frozenset()


def _vhash(values: tuple) -> str:
    return hashlib.sha256(json.dumps(list(values), ensure_ascii=False, separators=(",", ":"),
                                     default=str).encode("utf-8")).hexdigest()


def _dim_table(entity_type: str) -> tuple[str, str]:
    return {
        "ORDER": ("dwh_dim_order", "order_key"),
        "MATERIAL": ("dwh_dim_material", "material_key"),
        "BL": ("dwh_dim_bl", "bl_key"),
        "REG": ("dwh_dim_registration", "reg_key"),
        "REG_FILE": ("dwh_dim_registration_file", "reg_file_key"),
        "PR": ("dwh_dim_pr", "pr_key"),
        "PO": ("dwh_dim_po", "po_key"),
        "EMP": ("dwh_dim_employee", "emp_key"),
    }[entity_type]


def _relation_allowed(source: str, left_type: str, right_type: str) -> bool:
    # Commercial Expert's BL field is explicitly quarantined as non-shipping BL.
    if source == "moghavemat" and "BL" in (left_type, right_type):
        return False
    return True


def physical_columns(conn, name: str) -> set:
    """ستون‌های جدول اصلی (نه نمای موقت هم‌نامی که ``bind_published`` می‌سازد)."""
    return {r[1] for r in conn.execute(f"PRAGMA main.table_info({_q(name)})")}


def evolve_schema(conn) -> List[str]:
    """ستون تازه‌ای که به قالب یک جدول اضافه شده، به جدول موجود هم اضافه می‌شود.

    نسخه‌های قبلی برای آن ستون خالی می‌مانند و دست نمی‌خورند؛ ساخت بعدی (با امضای برنامه تازه)
    نسخه‌های باز را با مقدار کامل جایگزین می‌کند. عوض شدن کلید یک جدول مهاجرت دستی می‌خواهد.
    """
    changed = []
    for t in TABLES.values():
        have = physical_columns(conn, t.name)
        if not have:
            continue
        missing = [c for c in t.stored if c.name not in have]
        if not missing:
            continue
        if any(c.role == "key" for c in missing):
            raise RuntimeError(f"کلید جدول {t.name} در این نسخه برنامه عوض شده است؛ سوابق قبلی دست نمی‌خورد "
                               f"و این جدول به مهاجرت صریح نیاز دارد.")
        for c in missing:
            decl = c.decl if ("DEFAULT" in c.decl or "NOT NULL" not in c.decl) else c.decl + " DEFAULT ''"
            conn.execute(f"ALTER TABLE {t.name} ADD COLUMN {_q(c.name)} {decl}")
        conn.execute(f"DROP TRIGGER IF EXISTS {t.name}_close_once")
        changed.append(t.name)
    return changed


def _unique_open_indexes(conn) -> List[str]:
    """R8: شاخص نسخه باز هر جدول باید بر کلید طبیعی یکتا باشد (یک نسخه باز برای هر کلید).

    انبارهای قبلی همین شاخص را با همین نام غیریکتا دارند و ``IF NOT EXISTS`` آن را عوض
    نمی‌کند. اگر کلید تکراری باز ندارد، شاخص دوباره یکتا ساخته می‌شود؛ اگر دارد شاخص قبلی
    می‌ماند، خطا ثبت می‌شود و هیچ ردیفی پاک یا بسته نمی‌شود. خروجی: جدول‌های دارای تکرار.
    """
    from gsi.dataio.logging_setup import log
    blocked = []
    for t in TABLES.values():
        if not physical_columns(conn, t.name):
            continue
        name = f"{t.name}_open"
        info = {r[1]: r[2] for r in conn.execute(f"PRAGMA main.index_list({_q(t.name)})")}
        if name in info and info[name]:
            continue
        keys = ",".join(_q(k) for k in t.keys)
        dup = conn.execute(f"SELECT count(*) FROM (SELECT 1 FROM {t.name} WHERE to_seq IS NULL "
                           f"GROUP BY {keys} HAVING count(*)>1)").fetchone()[0]
        if dup:
            log.error(f"   ❌ [dwh] جدول {t.name}: {dup} کلید طبیعی بیش از یک نسخه باز دارد؛ شاخص یکتای "
                      f"{name} ساخته نشد و شاخص قبلی ماند (هیچ ردیفی پاک نشد). بازبینی دستی لازم است.")
            blocked.append(t.name)
            continue
        conn.execute(f"DROP INDEX IF EXISTS {name}")
        conn.execute(f"CREATE UNIQUE INDEX {name} ON {t.name}({keys}) WHERE to_seq IS NULL")
    return blocked


def ensure_schema(wh: Warehouse) -> None:
    with wh.db() as conn:
        conn.executescript(BUSINESS_SCHEMA)
        if evolve_schema(conn):
            conn.executescript(BUSINESS_SCHEMA)
        _unique_open_indexes(conn)


# ─────────────────────────── استخراج از ردیف‌های منبع ───────────────────────────
def _nonempty(s: pd.Series) -> set:
    return set(s[s != ""].unique().tolist())


def _source_evidence(sources: Mapping[str, Mapping[str, pd.DataFrame]], specs=None):
    """موجودیت‌ها، رابطه‌های هم‌دیده و ردیف‌های حل‌نشده؛ ستونی و با همان قواعد ردیف‌به‌ردیف قبلی.

    ``row_hash`` ردیف حل‌نشده از محتوای بدون جای ردیف و شماره تکرار همان محتوا در فریم ساخته
    می‌شود، تا جابه‌جایی ردیف در فایل آن را «رفته + تازه» نکند.
    """
    entity_keys: set = set()
    relation_counts: Dict[tuple, int] = {}
    unresolved: List[tuple] = []          # (source, frame, row_hash, reason, payload) به ترتیب ردیف
    unresolved_vh: Dict[tuple, str] = {}
    source_rows = 0
    for source, frames in sources.items():
        sap_has_raw = (source == "sap" and isinstance((frames or {}).get("raw_rows"), pd.DataFrame)
                       and not frames["raw_rows"].empty)
        for frame, df in (frames or {}).items():
            if source == 'clearance' and frame == 'export':
                # Reverse trade flow is archived as evidence, never linked into
                # import-side ORDER/BL/REG financial relationships.
                continue
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            # raw_rows is the physical archive for native multi-sheet SAP.
            if sap_has_raw and frame != "raw_rows":
                continue
            source_rows += len(df)
            keys = _frame_keys(source, df)
            for typ, s in keys.items():
                entity_keys.update((typ, k) for k in _nonempty(s))
            empty = pd.Series("", index=df.index, dtype=object)
            for lt, rt in DIRECT_PAIRS:
                lk, rk = keys.get(lt, empty), keys.get(rt, empty)
                if source == "sap" and (lt, rt) == ("PR", "PO"):
                    alt = _clean_col(df, "SAP_PO_PR")
                    lk = alt.where(alt != "", lk)
                if source == "sap" and (lt, rt) == ("PO", "MATERIAL"):
                    alt = _clean_col(df, "SAP_PO_MATERIAL")
                    rk = alt.where(alt != "", rk)
                entity_keys.update((lt, k) for k in _nonempty(lk))
                entity_keys.update((rt, k) for k in _nonempty(rk))
                if not _relation_allowed(source, lt, rt):
                    continue
                both = (lk != "") & (rk != "")
                if not both.any():
                    continue
                rule = f"DIRECT_COOBSERVED:{source}/{frame}:{lt}+{rt}"
                pairs = pd.DataFrame({"l": lk[both].to_numpy(), "r": rk[both].to_numpy()}).value_counts(sort=False)
                for (l, r), n in pairs.items():
                    k = (lt, l, rt, r, source, frame, rule)
                    relation_counts[k] = relation_counts.get(k, 0) + int(n)

            reasons = pd.Series(None, index=df.index, dtype=object)
            if source == "sap" and frame == "raw_rows":
                po_pr, pr = _clean_col(df, "SAP_PO_PR"), keys.get("PR", empty)
                reasons[(po_pr != "") & (pr != "") & (po_pr != pr)] = "SAP_HEADER_PO_PR_CONFLICT"
            if source == "ntsw" and frame == "import_license":
                reg_file, reg = keys.get("REG_FILE", empty), keys.get("REG", empty)
                reasons[(reg_file != "") & (reg == "")] = "REG_FILE_WITHOUT_REG_IN_IMPORT_LICENCE"
                reasons[(reg != "") & (reg_file == "")] = "REG_WITHOUT_REG_FILE_IN_IMPORT_LICENCE"
                reasons[(reg_file == "") & (reg == "")] = "IMPORT_LICENCE_ROW_WITHOUT_REG_KEYS"
            if source == "ilappend":
                rf, reg, order = keys.get("REG_FILE", empty), keys.get("REG", empty), keys.get("ORDER", empty)
                reasons[(rf != "") & (reg == "") & (order == "")] = "IL_REG_FILE_WITHOUT_REG_OR_ORDER"
            hit = reasons.notna().to_numpy()
            if hit.any():
                positions = [int(i) for i in hit.nonzero()[0]]
                sub = df.iloc[positions]
                occurrences: Dict[str, int] = {}
                for (row, content), reason in zip(_with_content(sub, _location(specs, source, frame)),
                                                  reasons.iloc[positions].tolist()):
                    payload = _row_payload(row)
                    occ = occurrences[content] = occurrences.get(content, -1) + 1
                    key = (source, frame, _row_hash(content + ":" + str(occ)), reason)
                    unresolved.append(key + (payload,))
                    unresolved_vh[key] = _vhash((content,))
    return entity_keys, relation_counts, unresolved, source_rows, unresolved_vh


# ─────────────────────────── واقعیت‌های جاری ───────────────────────────
def _frame(sources, source, name):
    df = (sources.get(source) or {}).get(name)
    return df if isinstance(df, pd.DataFrame) and not df.empty else None


def _fact_entities(sources) -> set:
    """موجودیت‌هایی که ساختن جدول‌های واقعیت ثبت می‌کند (همان ``_upsert_entity`` هر ردیف)."""
    out: set = set()

    def add(typ, s):
        out.update((typ, k) for k in s.map(lambda v: _entity_key(typ, v)) if k)

    inv = _frame(sources, "moghavemat", "inventory")
    if inv is not None:
        o, m = _clean_col(inv, KEY_ORDER), _clean_col(inv, KEY_MATERIAL)
        # R8: متریال بی‌سفارش هم ردیف واقعیت دارد؛ فقط MATERIAL از آن ثبت می‌شود.
        ok = m != ""
        add("ORDER", o[ok]); add("MATERIAL", m[ok])
    ompi = _frame(sources, "moghavemat", "order_material_pr_item")
    if ompi is not None:
        o, m, pr = _clean_col(ompi, KEY_ORDER), _clean_col(ompi, KEY_MATERIAL), _clean_col(ompi, KEY_PR)
        ok = (o != "") & (m != "") & (pr != "")
        add("ORDER", o[ok]); add("MATERIAL", m[ok]); add("PR", pr[ok])
    sap_pr = _frame(sources, "sap", "pr_items")
    if sap_pr is not None:
        pr, mat = _clean_col(sap_pr, KEY_PR), _clean_col(sap_pr, KEY_MATERIAL)
        ok = pr != ""
        add("PR", pr[ok]); add("MATERIAL", mat[ok])
    sap_po = _frame(sources, "sap", "po_items")
    if sap_po is not None:
        po = _clean_col(sap_po, KEY_PO)
        explicit = _clean_col(sap_po, "SAP_PO_PR")
        pr = explicit.where(explicit != "", _clean_col(sap_po, KEY_PR))
        pmat = _clean_col(sap_po, "SAP_PO_MATERIAL")
        mat = pmat.where(pmat != "", _clean_col(sap_po, KEY_MATERIAL))
        ok = po != ""
        add("PO", po[ok]); add("PR", pr[ok]); add("MATERIAL", mat[ok])
    wf = _frame(sources, "sap", "workflow_rows")
    if wf is not None:
        add("PR", _clean_col(wf, KEY_PR))
    oracle = _frame(sources, "oracle", "main")
    if oracle is not None:
        add("MATERIAL", _clean_col(oracle, KEY_MATERIAL))
    alloc = _frame(sources, "ntsw", "allocation_rows")
    if alloc is not None and "NTSW_REQUEST_KEY" in alloc.columns:
        r, q = _clean_col(alloc, KEY_REG), _clean_col(alloc, "NTSW_REQUEST_KEY")
        add("REG", r[(r != "") & (q != "")])
    com = _frame(sources, "ntsw", "commitment")
    if com is not None:
        add("REG", _clean_col(com, KEY_REG))
    return out


class FactGrainConflict(ValueError):
    """کلید طبیعی یک جدول واقعیت دو ردیف با محتوای متفاوت دارد؛ جدول ساخته نمی‌شود."""

    def __init__(self, name: str, conflicts: Dict[tuple, int]):
        self.name = name
        self.count = len(conflicts)
        self.rows = int(sum(conflicts.values()))
        self.sample = [list(k) for k in list(conflicts)[:10]]
        super().__init__(f"DWH_FACT_GRAIN_CONFLICT: {name} keys={self.count} rows={self.rows} "
                         f"sample={self.sample!r}; conflicting rows must be resolved at source grain")


def _fact_rows(name: str, df: pd.DataFrame, location: frozenset = frozenset()) -> Tuple[List[tuple], Dict[tuple, str]]:
    """ردیف‌های یک جدول واقعیت (کلید + مقدار) و اثرانگشت محتوای هر کلید.

    کلید تکراری با محتوای یکسان یک ردیف می‌شود. کلید تکراری با محتوای متفاوت دیگر بی‌صدا
    «آخری می‌ماند» نمی‌شود: ``FactGrainConflict`` با همه کلیدهای متعارض بالا می‌رود و ساخت
    همان جدول انجام نمی‌شود (قاعده مالک). درخواست تخصیص NTSW و متریال بدون سفارش استثنا
    هستند و هر ردیف با پسوند «#n» از ترتیب اثرانگشت محتوا نگه داشته می‌شود (R8).
    اثرانگشت از مقدارها بدون ستون‌های جای ردیف ساخته می‌شود.
    """
    rows: Dict[tuple, tuple] = {}
    content: Dict[tuple, tuple] = {}
    conflicts: Dict[tuple, int] = {}

    def put(key, values, same):
        if key in content and content[key] != same:
            conflicts[key] = conflicts.get(key, 1) + 1
            return
        rows[key] = values
        content[key] = same

    if name == "dwh_fact_supply_position":
        orderless: Dict[str, List[tuple]] = {}
        for row, body in _with_content(df, location):
            o, m = _entity_key("ORDER", row.get(KEY_ORDER, "")), _entity_key("MATERIAL", row.get(KEY_MATERIAL, ""))
            if not m:
                continue
            if not o:
                # R8: متریال بی‌سفارش حذف نمی‌شود؛ order_key خالی می‌ماند.
                orderless.setdefault(m, []).append((row, body))
                continue
            payload = _row_payload(row)
            put((o, m), (payload,), (body,))
        for m, items in orderless.items():
            distinct = {}
            for row, body in items:
                distinct.setdefault(_row_hash(body), (row, body))
            if len(distinct) == 1:
                row, body = next(iter(distinct.values()))
                put(("", m), (_row_payload(row),), (body,))
                continue
            # چند ردیف بی‌سفارش متفاوت برای یک متریال: هیچ‌کدام جای دیگری را نمی‌گیرد.
            for n, h in enumerate(sorted(distinct), 1):
                row, body = distinct[h]
                marked = dict(row, _DWH_ORDERLESS_OCCURRENCE=n, _DWH_ORDERLESS_OCCURRENCES=len(distinct))
                put((f"#{n}", m), (_row_payload(marked),), (body,))
    elif name == "dwh_bridge_order_material_pr_item":
        for row, body in _with_content(df, location):
            o, m = _entity_key("ORDER", row.get(KEY_ORDER, "")), _entity_key("MATERIAL", row.get(KEY_MATERIAL, ""))
            pr, item = _entity_key("PR", row.get(KEY_PR, "")), _clean(row.get("MOGH_PR_ITEM", ""))
            if not (o and m and pr):
                continue
            try:
                evidence_count = max(1, int(float(row.get("MOGH_EVIDENCE_COUNT", 1) or 1)))
            except Exception:
                evidence_count = 1
            payload = _row_payload(row)
            put((o, m, pr, item), (evidence_count, _clean(row.get("MOGH_SOURCE_ROWS", "")), payload),
                (evidence_count, body))
    elif name == "dwh_fact_sap_pr_item":
        for row, body in _with_content(df, location):
            pr, item = _entity_key("PR", row.get(KEY_PR, "")), _clean(row.get("SAP_PR_ITEM", ""))
            # R8: قلم خالی با کلید گروه‌بندی همان ردیف (ROW<n>) از بقیه جدا می‌ماند.
            item = item or _clean(row.get(SAP_PR_ITEM_GROUP, ""))
            mat = _entity_key("MATERIAL", row.get(KEY_MATERIAL, ""))
            if pr:
                payload = _row_payload(row)
                put((pr, item), (mat or None, payload), (mat or None, body))
    elif name == "dwh_fact_sap_po_item":
        for row, body in _with_content(df, location):
            po, item = _entity_key("PO", row.get(KEY_PO, "")), _clean(row.get("SAP_PO_ITEM", ""))
            item = item or _clean(row.get(SAP_PO_ITEM_GROUP, ""))  # R8
            explicit_pr = _clean(row.get("SAP_PO_PR", ""))
            pr = _entity_key("PR", explicit_pr or row.get(KEY_PR, ""))
            pri = _clean(row.get("SAP_PO_PR_ITEM", "")) if explicit_pr else _clean(row.get("SAP_PR_ITEM", ""))
            mat = _entity_key("MATERIAL", row.get("SAP_PO_MATERIAL", "")) or _entity_key("MATERIAL", row.get(KEY_MATERIAL, ""))
            if po:
                payload = _row_payload(row)
                put((po, item), (pr or None, pri, mat or None, payload), (pr or None, pri, mat or None, body))
    elif name == "dwh_fact_sap_workflow":
        # کلید رویداد از محتوا ساخته می‌شود نه از شماره ردیف: ردیف‌های هم‌محتوا در جاهای مختلف
        # (مثل قبل) جدا می‌مانند و با شماره تکرار از هم جدا می‌شوند؛ جابه‌جایی ردیف کلید را عوض نمی‌کند.
        places: Dict[str, Dict[str, int]] = {}
        for row, body in _with_content(df, location):
            pr, item = _entity_key("PR", row.get(KEY_PR, "")), _clean(row.get("SAP_PR_ITEM", ""))
            if not pr:
                continue
            payload = _row_payload(row)
            wf = _clean(row.get("SAP_WORKFLOW_ID", "")) or _clean(row.get("SAP_COMPARISON_ID", ""))
            seed = f"{pr}|{item}|{wf}|{body}"
            place = json.dumps([str(row.get(c)) for c in sorted(location) if c in row], ensure_ascii=False)
            seen = places.setdefault(seed, {})
            occ = seen.setdefault(place, len(seen))
            wkey = hashlib.sha256(f"{seed}|{occ}".encode("utf-8")).hexdigest()
            event_date = (_clean(row.get("SAP_CHANGED_ON_ISO", "")) or _clean(row.get("SAP_RELEASE_DATE_ISO", "")) or
                          _clean(row.get("SAP_COMMISSION_DATE_ISO", "")) or _clean(row.get("SAP_REQUISITION_DATE_ISO", "")))
            put((wkey,), (pr, item, event_date or None, payload), (pr, item, event_date or None, body))
    elif name == "dwh_fact_oracle_material":
        for row, body in _with_content(df, location):
            m = _entity_key("MATERIAL", row.get(KEY_MATERIAL, ""))
            if m:
                payload = _row_payload(row)
                put((m,), (payload,), (body,))
    elif name == "dwh_fact_ntsw_allocation_request":
        if "NTSW_REQUEST_KEY" in df.columns:
            # R8: درخواست مبهم/هم‌زمان متناقض چند ردیف با یک NTSW_REQUEST_KEY دارد و قبلاً فقط
            # آخری می‌ماند. حالا همه می‌مانند: کلید تکراری پسوند «#n» می‌گیرد که از ترتیب
            # اثرانگشت محتوا می‌آید، تا جابه‌جایی ردیف در فایل کلید را عوض نکند.
            groups: Dict[str, List[tuple]] = {}
            for row, body in _with_content(df, location):
                r, q = _entity_key("REG", row.get(KEY_REG, "")), _clean(row.get("NTSW_REQUEST_KEY", ""))
                if r and q:
                    groups.setdefault(q, []).append((r, row, body))
            for q, items in groups.items():
                if len(items) == 1:
                    r, row, body = items[0]
                    put((q,), (r, _row_payload(row)), (r, body))
                    continue
                items = sorted(items, key=lambda x: (_row_hash(x[2]), x[0]))
                for n, (r, row, body) in enumerate(items, 1):
                    marked = dict(row, _DWH_REQUEST_KEY=q, _DWH_REQUEST_OCCURRENCE=n,
                                  _DWH_REQUEST_OCCURRENCES=len(items))
                    put((f"{q}#{n}",), (r, _row_payload(marked)), (r, body))
    elif name == "dwh_fact_ntsw_commitment":
        for row, body in _with_content(df, location):
            r = _entity_key("REG", row.get(KEY_REG, ""))
            if r:
                payload = _row_payload(row)
                put((r,), (payload,), (body,))
    if conflicts:
        raise FactGrainConflict(name, conflicts)
    return [k + v for k, v in rows.items()], {k: _vhash(v) for k, v in content.items()}


# ─────────────────────────── ادغام نسخه‌دار ───────────────────────────
_MISSING = object()


def merge_versions(conn, name: str, rows, seq: int, run_id: str, vhashes=None) -> Dict[str, int]:
    """وضعیت این اجرای یک جدول را با نسخه‌های باز ادغام می‌کند؛ هیچ ردیفی پاک نمی‌شود.

    ``rows``: تاپل‌های «کلید + مقدار» به ترتیب ستون‌های key و value جدول، یکتا بر کلید.
    ``vhashes``: اثرانگشت محتوای هر کلید، اگر بخشی از مقدار (جای ردیف) نباید نسخه تازه بسازد؛
    نبودنش یعنی همه مقدارها.
    """
    t = TABLES[name]
    keys, kn = t.keys, len(t.keys)
    current = {}
    for r in rows:
        key, value = tuple(r[:kn]), tuple(r[kn:])
        if key in current and current[key] != value:
            raise ValueError(f"DWH_VERSION_GRAIN_CONFLICT: {name} key={key!r}")
        current[key] = value
    select = (f"SELECT vid,{','.join(_q(k) for k in keys)},vhash"
              + (",first_seen_run" if t.has_first else "") + f" FROM {name} WHERE to_seq IS NULL")
    closes, inserts = [], []
    stats = {"unchanged": 0, "changed": 0, "new": 0, "gone": 0}
    seen = set()
    for row in conn.execute(select):
        vid, k, old_vh = row[0], tuple(row[1:1 + kn]), row[1 + kn]
        seen.add(k)
        v = current.get(k, _MISSING)
        if v is _MISSING:
            closes.append((seq, vid))
            stats["gone"] += 1
            continue
        vh = vhashes[k] if vhashes is not None else _vhash(v)
        if vh == old_vh:
            stats["unchanged"] += 1
            continue
        closes.append((seq, vid))
        inserts.append(k + v + ((row[2 + kn],) if t.has_first else ()) + (seq, vh))
        stats["changed"] += 1
    fresh = [k for k in current if k not in seen]
    if fresh:
        # کلیدی که قبلاً بوده و رفته بود: «اولین بار دیده‌شده» از سابقه‌اش می‌آید
        history = t.has_first and conn.execute(
            f"SELECT 1 FROM {name} WHERE to_seq IS NOT NULL LIMIT 1").fetchone() is not None
        where = " AND ".join(f"{_q(c)}=?" for c in keys)
        for k in fresh:
            first = run_id
            if history:
                prev = conn.execute(f"SELECT first_seen_run FROM {name} WHERE {where} "
                                    f"ORDER BY from_seq DESC LIMIT 1", k).fetchone()
                if prev:
                    first = prev[0]
            v = current[k]
            inserts.append(k + v + ((first,) if t.has_first else ()) + (seq, vhashes[k] if vhashes is not None else _vhash(v)))
            stats["new"] += 1
    if closes:
        conn.executemany(f"UPDATE {name} SET to_seq=? WHERE vid=?", closes)
    if inserts:
        cols = list(keys) + list(t.values) + (["first_seen_run"] if t.has_first else []) + ["from_seq", "vhash"]
        conn.executemany(f"INSERT INTO {name}({','.join(_q(c) for c in cols)}) VALUES({','.join('?' * len(cols))})",
                         inserts)
    return stats


def _open_count(conn, name: str) -> int:
    return int(conn.execute(f"SELECT count(*) FROM {name} WHERE to_seq IS NULL").fetchone()[0])


def _input_frames(sources) -> List[Tuple[str, pd.DataFrame]]:
    """همه فریم‌های غیرخالی ورودی، به ترتیب دریافت؛ ورودی دقیق هر ساخت در بایگانی می‌ماند."""
    out = []
    for source, frames in sources.items():
        for frame, df in (frames or {}).items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                out.append((f"{source}/{frame}", df))
    return out


def _source_row_count(sources) -> int:
    """تعداد ردیف‌های منبعی که نسخه ۱ در ``dwh_fact_source_row`` بایگانی می‌کرد."""
    n = 0
    for source, frames in sources.items():
        frames = frames or {}
        sap_has_raw = (source == "sap" and isinstance(frames.get("raw_rows"), pd.DataFrame)
                       and not frames["raw_rows"].empty)
        for frame, df in frames.items():
            if isinstance(df, pd.DataFrame) and not df.empty and not (sap_has_raw and frame != "raw_rows"):
                n += len(df)
    return n


def _sig(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def build(wh: Warehouse, sources: Mapping[str, Mapping[str, pd.DataFrame]], run_id: str | None = None) -> dict[str, int]:
    run_id = run_id or RUN.get()
    if not run_id:
        raise RuntimeError("Business DWH build requires an active warehouse run")
    seq = wh.run_seq(run_id)
    if seq is None:
        raise RuntimeError("Business DWH build requires a recorded warehouse run")
    from .source_cache import program_signature_for
    program = program_signature_for(run_id)

    # ورودی دقیق این ساخت، از همان داده‌ای که در حافظه است، به‌عنوان فریم‌های «dwh_input» این اجرا
    # بایگانی می‌شود (محتوای تکراری دوباره نوشته نمی‌شود). جریان وجوه از همین‌ها می‌خواند.
    inputs = wh.keep_frames("dwh_input", _input_frames(sources))
    # R8: بایگانی بالا فریم‌های اصلی را نگه می‌دارد؛ از اینجا همه استخراج‌ها
    # (_source_evidence، _fact_entities و _fact_rows) کلید متعارف می‌بینند.
    sources = canonical_sources(sources)
    evidence_sig = _sig("evidence", program, sorted(inputs.items()))
    ensure_schema(wh)
    with wh.db() as conn:
        state = dict(conn.execute("SELECT name,input_sig FROM wh_dwh_build_state"))
    from .history import load_specs
    specs = load_specs()
    fresh_evidence = state.get("evidence") != evidence_sig
    if fresh_evidence:
        # ── استخراج (بیرون از تراکنش نوشتن) ──
        entity_keys, relation_counts, unresolved, source_rows, unresolved_vh = _source_evidence(sources, specs)
        entity_keys |= _fact_entities(sources)
    else:
        source_rows = _source_row_count(sources)
    fact_plan: Dict[str, Tuple[str, object]] = {}
    grain_conflicts: Dict[str, Dict[str, object]] = {}
    for name, (source, frame) in FACT_INPUTS.items():
        df = _frame(sources, source, frame)
        sig = _sig("fact", name, program, inputs.get(f"{source}/{frame}") if df is not None else None)
        if state.get(name) == sig:
            fact_plan[name] = (sig, None)          # همان ورودی و همان برنامه: نسخه‌های باز معتبر می‌مانند
        elif df is None:
            fact_plan[name] = (sig, ([], {}))
        else:
            try:
                fact_plan[name] = (sig, _fact_rows(name, df, _location(specs, source, frame)))
            except FactGrainConflict as ex:
                # جدول متعارض ساخته نمی‌شود و امضایش ثبت نمی‌شود؛ نسخه‌های باز قبلی دست‌نخورده
                # می‌مانند و دروازه کیفیت با DWH_FACT_GRAIN_CONFLICT انتشار را متوقف می‌کند.
                from gsi.dataio.logging_setup import log
                log.error(str(ex))
                grain_conflicts[name] = {"keys": ex.count, "rows": ex.rows, "sample": ex.sample,
                                         "source": f"{source}/{frame}"}

    counts: Dict[str, object] = {"source_rows": source_rows}
    versions: Dict[str, Dict[str, int]] = {}
    skipped = []

    def mark(conn, name, sig):
        conn.execute("INSERT INTO wh_dwh_build_state(name,input_sig,seq) VALUES(?,?,?) "
                     "ON CONFLICT(name) DO UPDATE SET input_sig=excluded.input_sig,seq=excluded.seq",
                     (name, sig, seq))

    with wh.db() as conn:
        if fresh_evidence:
            by_type: Dict[str, List[str]] = {}
            for typ, key in entity_keys:
                by_type.setdefault(typ, []).append(key)
            versions["dwh_entity"] = merge_versions(conn, "dwh_entity", sorted(entity_keys), seq, run_id)
            for typ in ENTITY_COLS:
                table, _col = _dim_table(typ)
                versions[table] = merge_versions(conn, table, [(k,) for k in sorted(by_type.get(typ, ()))],
                                                 seq, run_id)
            versions["dwh_relation"] = merge_versions(
                conn, "dwh_relation", [k + (n,) for k, n in relation_counts.items()], seq, run_id)
            versions["dwh_unresolved_relation"] = merge_versions(conn, "dwh_unresolved_relation", unresolved,
                                                                 seq, run_id, unresolved_vh)
            mark(conn, "evidence", evidence_sig)
        else:
            skipped.append("evidence")
        for name, (sig, plan) in fact_plan.items():
            if plan is None:
                skipped.append(name)
                continue
            rows, hashes = plan
            versions[name] = merge_versions(conn, name, rows, seq, run_id, hashes)
            mark(conn, name, sig)
        counts["unresolved"] = _open_count(conn, "dwh_unresolved_relation")
        counts["entities"] = _open_count(conn, "dwh_entity")
        counts["relations"] = _open_count(conn, "dwh_relation")
        counts["order_material_pr_item"] = _open_count(conn, "dwh_bridge_order_material_pr_item")
        counts["sap_pr_items"] = _open_count(conn, "dwh_fact_sap_pr_item")
        counts["sap_po_items"] = _open_count(conn, "dwh_fact_sap_po_item")
        counts["sap_workflow"] = _open_count(conn, "dwh_fact_sap_workflow")
        # هر رابطه باز باید دو سر باز داشته باشد (جایگزین کلید خارجی جدول‌های نسخه ۱)
        counts["orphan_relations"] = int(conn.execute(
            "SELECT count(*) FROM dwh_relation r WHERE r.to_seq IS NULL AND ("
            "NOT EXISTS(SELECT 1 FROM dwh_entity e WHERE e.to_seq IS NULL AND e.entity_type=r.left_type "
            "AND e.business_key=r.left_key) OR "
            "NOT EXISTS(SELECT 1 FROM dwh_entity e WHERE e.to_seq IS NULL AND e.entity_type=r.right_type "
            "AND e.business_key=r.right_key))").fetchone()[0])
    counts["versions"] = {k: v for k, v in versions.items() if v.get("new") or v.get("changed") or v.get("gone")}
    counts["unchanged"] = skipped
    counts["grain_conflicts"] = grain_conflicts
    return counts

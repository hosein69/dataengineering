# -*- coding: utf-8 -*-
"""زنجیره تعهد ارزی: از درخواست تخصیص تا رفع تعهد.

گزارش روی ``wh_business_record`` و ``wh_measure`` ساخته می‌شود، نه روی اکسل خام،
تا مبالغ با دقت Decimal بمانند و هر عدد به سطر فیزیکی منبعش قابل ردیابی باشد.

قواعدی که این ماژول نمی‌شکند
----------------------------
* **نامعلوم ≠ صفر.** نبودِ شاهد یک گام، با ``None`` نمایش داده می‌شود نه صفر.
  «تعهد صفر» فقط وقتی نوشته می‌شود که منبع عدد صفر داده باشد.
* **جمع بین‌ارزی ممنوع.** مبالغ همیشه به تفکیک ارز نگه داشته می‌شوند؛ هیچ نرخ
  تبدیلی اینجا اعمال نمی‌شود.
* **همبستگی، علیت نیست.** ستون ``GAP`` می‌گوید کدام گام شاهد ندارد؛ نمی‌گوید
  چرا. علت نیازمند شاهد بیرون از این داده است.
* **کلید، مجوز نیست.** تطبیق روی «ثبت سفارش» شاهد پیوند است، نه اثبات یکتایی؛
  نرخ تطبیق صریح گزارش می‌شود تا خواننده بداند چقدر از زنجیره واقعاً بسته شده.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .store import Warehouse, loads

# هر گام: (کلید, عنوان فارسی, شیت منبع, ستون تاریخِ شاهد)
STAGES = [
    ("license",    "مجوز / پیش‌فاکتور", "Import License",     "تاریخ صدور ثبت سفارش"),
    ("request",    "درخواست تخصیص",     "Allocation",         "تاریخ ایجاد درخواست"),
    ("allocation", "تخصیص ارز",          "Allocation",         "تاریخ تخصیص"),
    ("purchase",   "خرید ارز / سوئیفت",  "خريد جاري1405",      "تاريخ سوئيفت"),
    ("declaration","اظهارنامه گمرکی",    "Custom Declaration", "تاریخ اظهارنامه"),
    ("commitment", "ایجاد تعهد",         "Release Commitment", "تاریخ ایجاد تعهد"),
    ("release",    "رفع تعهد",           "Release Commitment", None),
]

RELEASED_MARKERS = ("رفع تعهد شده", "رفع شده", "تسویه")


_NOT_A_KEY = {"", "nan", "none", "null", "-", "—"}


def _text(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _key(v: Any) -> str:
    """کلید ثبت سفارش. سطر خالیِ منبع رشته «nan» می‌دهد؛ آن یک پرونده نیست."""
    t = _text(v)
    return "" if t.lower() in _NOT_A_KEY else t


def _records(wh: Warehouse) -> List[Dict[str, Any]]:
    with wh.db() as c:
        rows = c.execute(
            "SELECT sheet,row_no,file_id,registration_id,payload "
            "FROM wh_business_record WHERE registration_id<>'' ").fetchall()
    out = []
    for sheet, row_no, fid, reg, payload in rows:
        if not _key(reg):
            continue
        out.append({"sheet": sheet, "row_no": row_no, "file_id": fid,
                    "registration": _key(reg), "payload": loads(payload)})
    return out


def _measures(wh: Warehouse) -> Dict[tuple, List[Dict[str, Any]]]:
    with wh.db() as c:
        rows = c.execute(
            "SELECT file_id,sheet,row_no,measure,amount_decimal,currency,status "
            "FROM wh_measure").fetchall()
    by = defaultdict(list)
    for fid, sheet, row_no, measure, amount, currency, status in rows:
        by[(fid, sheet, row_no)].append(
            {"measure": measure, "amount": amount, "currency": currency, "status": status})
    return by


def coverage(wh: Optional[Warehouse] = None) -> Dict[str, Any]:
    """نرخ تطبیق بین گام‌ها — صادقانه، چه بسته باشد چه نباشد."""
    wh = wh or Warehouse()
    recs = _records(wh)
    by_sheet: Dict[str, set] = defaultdict(set)
    for r in recs:
        by_sheet[r["sheet"]].add(r["registration"])
    sheets = {s: by_sheet.get(s, set()) for _, _, s, _ in STAGES}
    alloc = sheets.get("Allocation", set())
    commit = sheets.get("Release Commitment", set())
    linked = alloc & commit
    universe = set().union(*sheets.values()) if sheets else set()
    multi = sum(1 for k in universe if sum(k in v for v in sheets.values()) > 1)
    return {
        "registrations_total": len(universe),
        "in_more_than_one_stage": multi,
        "allocation_rows": len(alloc),
        "commitment_rows": len(commit),
        "allocation_to_commitment_matched": len(linked),
        "match_rate": (len(linked) / len(alloc)) if alloc else None,
        "per_stage": {key: len(sheets.get(sheet, set())) for key, _, sheet, _ in STAGES},
    }


def chain(wh: Optional[Warehouse] = None) -> List[Dict[str, Any]]:
    """یک سطر برای هر «ثبت سفارش»، با شاهد هر گام و مانده تعهد به تفکیک ارز."""
    wh = wh or Warehouse()
    recs = _records(wh)
    meas = _measures(wh)
    stage_by_sheet: Dict[str, List[tuple]] = defaultdict(list)
    for key, label, sheet, date_col in STAGES:
        stage_by_sheet[sheet].append((key, label, date_col))

    rows: Dict[str, Dict[str, Any]] = {}
    for r in recs:
        reg = r["registration"]
        if r["sheet"] not in stage_by_sheet:
            continue
        row = rows.setdefault(reg, {
            "ثبت سفارش": reg, "_stages": {}, "_amounts": defaultdict(dict),
            "_evidence": [], "مانده تعهد": None, "ارز تعهد": "",
            "مهلت رفع تعهد": "", "وضعیت رفع تعهد": "",
        })
        payload = r["payload"]
        row["_evidence"].append(f"{r['sheet']}#{r['row_no']}")
        for key, label, date_col in stage_by_sheet[r["sheet"]]:
            if key == "release":
                status = _text(payload.get("وضعیت رفع تعهد"))
                row["وضعیت رفع تعهد"] = status
                row["مهلت رفع تعهد"] = _text(payload.get("مهلت رفع تعهد"))
                row["_stages"][key] = bool(status) and status.startswith(RELEASED_MARKERS)
                continue
            seen = bool(_text(payload.get(date_col))) if date_col else True
            # گام فقط وقتی «دیده شده» است که شاهد تاریخی داشته باشد؛ نبودِ تاریخ
            # یعنی نامعلوم، نه «انجام نشده».
            row["_stages"][key] = seen if seen else row["_stages"].get(key, None)
        for m in meas.get((r["file_id"], r["sheet"], r["row_no"]), []):
            if m["status"] != "valid" or m["amount"] is None:
                continue
            row["_amounts"][m["measure"]][m["currency"]] = Decimal(m["amount"])
            if m["measure"] == "مانده تعهد":
                row["مانده تعهد"] = m["amount"]
                row["ارز تعهد"] = m["currency"]

    out = []
    for reg, row in sorted(rows.items()):
        stages = row["_stages"]
        gaps = [label for key, label, _, _ in STAGES if not stages.get(key)]
        rec = {
            "ثبت سفارش": reg,
            **{label: ("✔" if stages.get(key) else ("—" if key in stages else "نامعلوم"))
               for key, label, _, _ in STAGES},
            "مانده تعهد": row["مانده تعهد"] if row["مانده تعهد"] is not None else "نامعلوم",
            "ارز تعهد": row["ارز تعهد"] or "نامعلوم",
            "مهلت رفع تعهد": row["مهلت رفع تعهد"] or "نامعلوم",
            "وضعیت رفع تعهد": row["وضعیت رفع تعهد"] or "نامعلوم",
            "گام بدون شاهد": " · ".join(gaps) if gaps else "",
            "شاهد": " · ".join(sorted(set(row["_evidence"]))),
        }
        amounts = {f"{m} ({c})": format(v, "f")
                   for m, cur in row["_amounts"].items() for c, v in cur.items()}
        rec.update(amounts)
        out.append(rec)
    return out


def _scoped_file_ids(conn, run_id: Optional[str]) -> tuple[list[str], str]:
    """The file versions a total may legitimately cover.

    The append-only archive is not a current snapshot. An explicit/selected
    run with no source files stays empty; never fall back to another run.
    Without publication, the default report stays empty.
    """
    if run_id is None:
        row = (conn.execute("SELECT run_id FROM wh_current WHERE slot='dwh'").fetchone()
               or conn.execute("SELECT run_id FROM wh_current WHERE slot='report'").fetchone())
        run_id = row[0] if row else None
    if run_id:
        ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT file_id FROM wh_ingest WHERE run_id=? AND source='ntsw'", (run_id,)).fetchall()]
        return ids, f"run:{run_id}"
    return [], "NO_PUBLISHED_RUN"


def totals_by_currency(wh: Optional[Warehouse] = None, run_id: Optional[str] = None,
                       all_versions: bool = False) -> List[Dict[str, Any]]:
    """جمع تعهد و مانده، فقط درون هر ارز و فقط روی نسخه جاری فایل‌ها.

    ``wh_measure`` آرشیو است و همه نسخه‌های ingest‌شده در آن می‌مانند؛ جمع بدون
    دامنه یعنی جمع‌زدن مانده دیروز روی مانده امروز. پیش‌فرض، فایل‌های اجرای
    منتشرشده است. ``all_versions=True`` عمداً کل آرشیو را جمع می‌زند و نتیجه با
    همان برچسب دامنه برمی‌گردد تا با «مانده جاری» اشتباه نشود.
    """
    wh = wh or Warehouse()
    with wh.db() as c:
        if all_versions:
            scope, ids = "all_archived_versions", None
            rows = c.execute(
                "SELECT measure,currency,amount_decimal,status FROM wh_measure "
                "WHERE measure IN ('تعهد اولیه','مانده تعهد')").fetchall()
        else:
            ids, scope = _scoped_file_ids(c, run_id)
            if not ids:
                return []
            marks = ",".join("?" * len(ids))
            rows = c.execute(
                "SELECT measure,currency,amount_decimal,status FROM wh_measure "
                f"WHERE measure IN ('تعهد اولیه','مانده تعهد') AND file_id IN ({marks})",
                ids).fetchall()
    known = defaultdict(Decimal)
    unknown = defaultdict(int)
    for measure, currency, amount, status in rows:
        key = (measure, currency or "نامشخص")
        if status == "valid" and amount is not None:
            known[key] += Decimal(amount)
        else:
            unknown[key] += 1
    return [{"سنجه": k[0], "ارز": k[1], "جمع معلوم": format(known[k], "f"),
             "سطر نامعلوم": unknown[k], "دامنه": scope,
             "نسخه‌های شمرده‌شده": len(ids) if ids is not None else "کل آرشیو"}
            for k in sorted(set(known) | set(unknown))]

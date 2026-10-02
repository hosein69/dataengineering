"""برگ تصمیم — صفحه اول HTML به ترتیب «سند ← وضعیت ← توضیح» (29.15.13).

صفحه اول گزارش HTML تا 29.15.12 با برند، زنجیره فرایند و راهنما شروع می‌شد و مدیر
باید برای پیدا کردن «الان چه باید بشود و با کیست» تب‌ها و فیلترها را می‌گشت، با این‌که
اقدام بعدی، مالک و موعد هر پرونده (s58) روی همان ردیف‌ها بود. این ماژول همان داده‌ها را
در قالب گزارش مدیر می‌گذارد: DONE / OWNER / DATE / RISK / NEXT / ASK، و زیر آن صف اقدام
با دروازه‌های اجرا.

قواعد (از مدل تصمیم مالک):

* **فقط از همین خروجی.** ورودی همان ``df`` است که ``build_dynamic_html`` می‌گیرد و
  دامنه مخاطب (ردیف و ستون) قبل از آن اعمال شده؛ این برگ چیزی بیرون از آن نمی‌خواند.
* **نامعلوم صفر نیست.** اگر ستونی در این خروجی نباشد، کارت «نامشخص» می‌شود و نام ستون
  غایب را می‌گوید؛ هیچ‌وقت «۰» نمی‌نویسد.
* **ASK فقط با شاهد.** اگر داده دلیلی برای درخواست از مدیر ندارد، ASK خالی است.
* **دروازه‌ها:** اقدام بدون مالک «آماده اجرا نیست»؛ اقدام بدون موعد «هنوز Task نشده»؛
  اقدام با شاهد ناقص علامت می‌خورد.
* هر کارت ستون‌های منبعش را اعلام می‌کند.

این ماژول هیچ عددی را محاسبه یا ذخیره نمی‌کند که در مارت نباشد؛ فقط می‌شمارد و مرتب می‌کند.
"""
from __future__ import annotations

import html
from typing import Dict, List, Optional

import pandas as pd

PRIORITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
PRIORITY_FA = {"CRITICAL": "بحرانی", "HIGH": "بالا", "MEDIUM": "متوسط", "LOW": "پایین"}
# طبقه‌هایی که «ریسک توقف» هستند (s40: کد طبقه بحرانی)
RISK_BANDS = ("STOCKOUT", "CRITICAL")
BAND_FA = {"STOCKOUT": "توقف خط", "CRITICAL": "بحرانی"}

GATE_OWNERLESS = "OWNERLESS"
GATE_NO_DATE = "NO_DATE"
GATE_EVIDENCE = "EVIDENCE_GAP"
GATE_READY = "READY"
GATE_FA = {
    GATE_OWNERLESS: "بدون مالک — آماده اجرا نیست",
    GATE_NO_DATE: "بدون موعد — هنوز Task نشده",
    GATE_EVIDENCE: "آماده اجرا — شاهد ناقص",
    GATE_READY: "آماده اجرا",
}
GATE_TONE = {GATE_OWNERLESS: "critical", GATE_NO_DATE: "serious",
             GATE_EVIDENCE: "warning", GATE_READY: "good"}

USED_COLS = ("KEY_REG", "CASE_KEY", "CANONICAL_ORDER", "KEY_MATERIAL", "NEXT_ACTION_ID",
             "NEXT_ACTION_TITLE", "NEXT_ACTION_OWNER", "NEXT_ACTION_DUE_DATE", "NEXT_ACTION_DAYS",
             "NEXT_ACTION_PRIORITY", "NEXT_ACTION_EVIDENCE_GAPS", "NEXT_ACTION_RULE_BASIS",
             "کد طبقه بحرانی", "مقاومت (روز)", "اقدام پیشنهادی مقاومت")
ACTION_COLS = ("NEXT_ACTION_ID", "NEXT_ACTION_TITLE", "NEXT_ACTION_OWNER",
               "NEXT_ACTION_DUE_DATE", "NEXT_ACTION_PRIORITY")
MAX_ACTIONS = 7


def _s(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _date(v) -> Optional[pd.Timestamp]:
    s = _s(v)
    if not s:
        return None
    t = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(t) else pd.Timestamp(t).normalize()


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _distinct(df: pd.DataFrame, col: str) -> Optional[int]:
    if col not in df.columns:
        return None
    return int(df[col].map(_s).replace("", pd.NA).dropna().nunique())


def _actions(recs: List[Dict], has: set, ref: Optional[pd.Timestamp]) -> List[Dict]:
    """یک اقدام به ازای هر شناسه اقدام؛ متریال‌های هم‌پرونده کنار آن جمع می‌شوند."""
    out: Dict[str, Dict] = {}
    for r in recs:
        title = _s(r.get("NEXT_ACTION_TITLE"))
        aid = _s(r.get("NEXT_ACTION_ID"))
        if not title and not aid:
            continue
        case = _s(r.get("KEY_REG")) or _s(r.get("CASE_KEY")) or _s(r.get("CANONICAL_ORDER"))
        key = aid or f"{case}|{title}"
        a = out.get(key)
        if a is None:
            due = _date(r.get("NEXT_ACTION_DUE_DATE"))
            if due is not None and ref is not None:
                days = float((due - ref).days)
            else:
                days = _num(r.get("NEXT_ACTION_DAYS"))
            owner = _s(r.get("NEXT_ACTION_OWNER"))
            gaps = _s(r.get("NEXT_ACTION_EVIDENCE_GAPS"))
            prio = _s(r.get("NEXT_ACTION_PRIORITY")).upper()
            if "NEXT_ACTION_OWNER" in has and not owner:
                gate = GATE_OWNERLESS
            elif "NEXT_ACTION_DUE_DATE" in has and due is None:
                gate = GATE_NO_DATE
            elif gaps:
                gate = GATE_EVIDENCE
            else:
                gate = GATE_READY
            a = {"id": aid, "case": case, "title": title, "owner": owner,
                 "due": due.strftime("%Y-%m-%d") if due is not None else "",
                 "days": days, "priority": prio, "gaps": gaps,
                 "basis": _s(r.get("NEXT_ACTION_RULE_BASIS")), "gate": gate,
                 "materials": []}
            out[key] = a
        mat = _s(r.get("KEY_MATERIAL"))
        if mat and mat not in a["materials"]:
            a["materials"].append(mat)

    def order(a):
        overdue = a["days"] is not None and a["days"] < 0
        return (0 if overdue else 1, -PRIORITY_RANK.get(a["priority"], 0),
                a["days"] if a["days"] is not None else 10 ** 9, a["case"])
    return sorted(out.values(), key=order)


def compute_decision_brief(df: pd.DataFrame, ref_date: str) -> Dict:
    """داده برگ تصمیم؛ بدون HTML تا قابل آزمون باشد."""
    df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    ref = _date(ref_date)
    cols = set(df.columns)
    missing_action = [c for c in ACTION_COLS if c not in cols]
    recs = df[[c for c in USED_COLS if c in cols]].to_dict("records")
    acts = _actions(recs, cols, ref) if "NEXT_ACTION_TITLE" in cols else []
    known_actions = "NEXT_ACTION_TITLE" in cols

    b: Dict = {"ref_date": ref.strftime("%Y-%m-%d") if ref is not None else _s(ref_date),
               "rows": int(len(df)),
               "orders": _distinct(df, "CANONICAL_ORDER"),
               "materials": _distinct(df, "KEY_MATERIAL"),
               "regs": _distinct(df, "KEY_REG"),
               "actions": acts, "actions_known": known_actions,
               "missing_action_cols": missing_action}

    # OWNER
    if known_actions and "NEXT_ACTION_OWNER" in cols:
        by_owner: Dict[str, int] = {}
        for a in acts:
            if a["owner"]:
                by_owner[a["owner"]] = by_owner.get(a["owner"], 0) + 1
        b["owners"] = sorted(by_owner.items(), key=lambda kv: (-kv[1], kv[0]))
        b["ownerless"] = sum(1 for a in acts if a["gate"] == GATE_OWNERLESS)
    else:
        b["owners"] = None
        b["ownerless"] = None

    # DATE
    if known_actions and ("NEXT_ACTION_DUE_DATE" in cols or "NEXT_ACTION_DAYS" in cols):
        dated = [a for a in acts if a["days"] is not None]
        b["overdue"] = sum(1 for a in dated if a["days"] < 0)
        b["overdue_critical"] = sum(1 for a in dated if a["days"] < 0 and a["priority"] == "CRITICAL")
        upcoming = sorted((a for a in dated if a["days"] >= 0), key=lambda a: a["days"])
        b["next_due"] = upcoming[0] if upcoming else None
        b["undated"] = sum(1 for a in acts if a["days"] is None)
    else:
        b["overdue"] = b["overdue_critical"] = b["undated"] = None
        b["next_due"] = None

    # RISK — متریال‌های «توقف خط / بحرانی» و این‌که اقدامی دارند یا نه
    if "کد طبقه بحرانی" in cols and "KEY_MATERIAL" in cols:
        risk: Dict[str, Dict] = {}
        for r in recs:
            code = _s(r.get("کد طبقه بحرانی")).upper()
            mat = _s(r.get("KEY_MATERIAL"))
            if code not in RISK_BANDS or not mat:
                continue
            res = _num(r.get("مقاومت (روز)"))
            case = _s(r.get("KEY_REG")) or _s(r.get("CASE_KEY")) or _s(r.get("CANONICAL_ORDER"))
            # «در صف» = اقدام s58 با مالک و موعد برای همین پرونده. پیشنهاد مقاومت (s40)
            # متن توصیه است و مالک/موعد ندارد؛ جدا نشان داده می‌شود.
            has_action = bool(_s(r.get("NEXT_ACTION_TITLE"))) if known_actions else None
            cur = risk.get(mat)
            if cur is None:
                risk[mat] = {"material": mat, "band": code, "resistance": res,
                             "cases": [case] if case else [], "has_action": has_action,
                             "advice": _s(r.get("اقدام پیشنهادی مقاومت"))}
            else:
                if case and case not in cur["cases"]:
                    cur["cases"].append(case)
                if res is not None and (cur["resistance"] is None or res < cur["resistance"]):
                    cur["resistance"] = res
                if code == "STOCKOUT":
                    cur["band"] = code
                if has_action:
                    cur["has_action"] = True
        b["risk"] = sorted(risk.values(), key=lambda m: (
            0 if m["band"] == "STOCKOUT" else 1,
            m["resistance"] if m["resistance"] is not None else 10 ** 9, m["material"]))
        b["risk_without_action"] = (sum(1 for m in b["risk"] if m["has_action"] is False)
                                    if known_actions else None)
    else:
        b["risk"] = None
        b["risk_without_action"] = None

    # NEXT
    b["next"] = acts[0] if acts else None

    # ASK — فقط وقتی شاهد دارد
    asks: List[str] = []
    if b["ownerless"]:
        asks.append(f"تعیین مالک برای {b['ownerless']:,} اقدام بدون مالک")
    if b["risk_without_action"]:
        asks.append(f"تعیین مالک و موعد برای {b['risk_without_action']:,} متریال توقف خط/بحرانی "
                    "که پرونده‌اش در صف اقدام نیست")
    if b["overdue_critical"]:
        asks.append(f"تصمیم برای {b['overdue_critical']:,} اقدام بحرانی که موعدش گذشته "
                    "(ادامه با همان مالک یا ارجاع)")
    b["asks"] = asks
    return b


# ─────────────────────────── HTML ───────────────────────────

CSS = """
.dbrief{background:var(--raised,#fff);border:1px solid var(--border,#d5e8e8);border-radius:16px;padding:18px 20px;box-shadow:0 6px 18px rgba(15,53,56,.05)}
.dbrief-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.dbrief-head h2{margin:0;font-size:1.15rem;color:var(--text,#0f3538)}
.dbrief-head small{color:var(--text-3,#6b7c8a)}
.dbrief-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
@media (max-width:960px){.dbrief-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.dbrief-grid{grid-template-columns:1fr}}
.dcard{border:1px solid var(--border,#d5e8e8);border-top:3px solid var(--st-tone-ink,var(--teal,#007b7f));border-radius:12px;padding:10px 12px;background:var(--st-tone-wash,transparent);min-width:0}
.dcard[data-tone="critical"]{--st-tone-ink:var(--st-critical-ink);--st-tone-wash:var(--st-critical-wash)}
.dcard[data-tone="serious"]{--st-tone-ink:var(--st-serious-ink);--st-tone-wash:var(--st-serious-wash)}
.dcard[data-tone="warning"]{--st-tone-ink:var(--st-warning-ink);--st-tone-wash:var(--st-warning-wash)}
.dcard[data-tone="good"]{--st-tone-ink:var(--st-good-ink);--st-tone-wash:var(--st-good-wash)}
.dcard[data-tone="unknown"]{--st-tone-ink:var(--border-strong,#9fb0bc);border-style:dashed}
.dcard .k{font-size:11px;font-weight:800;letter-spacing:.06em;color:var(--text-3,#6b7c8a)}
.dcard .k span{font-weight:600;letter-spacing:0;margin-inline-start:6px}
.dcard .v{font-size:1.05rem;font-weight:800;color:var(--text,#0f3538);margin:4px 0 2px;overflow-wrap:anywhere}
.dcard .d{font-size:.86rem;color:var(--text-2,#355a5d);line-height:1.8;overflow-wrap:anywhere}
.dcard .d ul{margin:0;padding-inline-start:18px}
.dcard .src{font-size:10.5px;color:var(--text-3,#6b7c8a);margin-top:6px;direction:ltr;text-align:right;overflow-wrap:anywhere}
.dqueue{margin-top:14px}
.dqueue h3{font-size:.98rem;margin:0 0 8px;color:var(--text,#0f3538)}
.dqueue-wrap{overflow-x:auto}
.dqueue table{width:100%;border-collapse:collapse;font-size:.86rem;min-width:640px}
.dqueue th,.dqueue td{border-bottom:1px solid var(--border,#d5e8e8);padding:7px 8px;text-align:right;vertical-align:top}
.dqueue th{color:var(--text-3,#6b7c8a);font-weight:700;font-size:.78rem}
.dqueue td.num{white-space:nowrap;font-variant-numeric:tabular-nums}
.dgate{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.76rem;font-weight:700;border:1px solid var(--st-tone-ink,var(--border-strong));color:var(--st-tone-ink,inherit);background:var(--st-tone-wash,transparent);white-space:nowrap}
.dgate[data-tone="critical"]{--st-tone-ink:var(--st-critical-ink);--st-tone-wash:var(--st-critical-wash)}
.dgate[data-tone="serious"]{--st-tone-ink:var(--st-serious-ink);--st-tone-wash:var(--st-serious-wash)}
.dgate[data-tone="warning"]{--st-tone-ink:var(--st-warning-ink);--st-tone-wash:var(--st-warning-wash)}
.dgate[data-tone="good"]{--st-tone-ink:var(--st-good-ink);--st-tone-wash:var(--st-good-wash)}
.dqueue .more{font-size:.8rem;color:var(--text-3,#6b7c8a);margin-top:6px}
@media print{.dbrief{box-shadow:none;break-inside:avoid}}
"""


def _e(v) -> str:
    return html.escape(str(v))


def _b(v) -> str:
    """کد/شناسه لاتین داخل متن فارسی: ایزوله تا ترتیبش در RTL به‌هم نریزد."""
    return f"<bdi>{html.escape(str(v))}</bdi>"


def _dl(iso: str) -> str:
    """تاریخ: شمسی و میلادی، هر دو ایزوله (همان قالب سربرگ)."""
    if not iso:
        return ""
    from ..core.jalali import date_label
    return html.escape(date_label(iso))


def _card(key: str, label: str, value: str, detail: str, sources: List[str], tone: str) -> str:
    src = " · ".join(sources)
    return (f'<section class="dcard" data-tone="{tone}" data-brief="{key}" aria-label="{_e(label)}">'
            f'<div class="k">{key}<span>{_e(label)}</span></div>'
            f'<div class="v">{value}</div><div class="d">{detail}</div>'
            f'<div class="src" title="ستون‌های منبع">{_e(src)}</div></section>')


def _unknown(cols: List[str]) -> str:
    return ("نامشخص — در این خروجی نیست: " + ", ".join(_e(c) for c in cols))


def _days_fa(days: Optional[float]) -> str:
    if days is None:
        return "بدون موعد"
    d = int(days)
    if d < 0:
        return f"{-d:,} روز گذشته"
    if d == 0:
        return "امروز"
    return f"{d:,} روز مانده"


def render_decision_brief_html(b: Dict) -> str:
    cards: List[str] = []

    # DONE
    parts = [f"{b['rows']:,} ردیف تأمین"]
    for key, fa in (("orders", "سفارش"), ("materials", "متریال"), ("regs", "ثبت سفارش")):
        if b.get(key) is not None:
            parts.append(f"{b[key]:,} {fa}")
    cards.append(_card("DONE", "این خروجی", "وضعیت " + _dl(b["ref_date"]),
                       _e(" · ".join(parts)),
                       ["CANONICAL_ORDER", "KEY_MATERIAL", "KEY_REG"], "neutral"))

    # OWNER
    if b["owners"] is None:
        cards.append(_card("OWNER", "مالک اقدام‌های باز", "نامشخص",
                           _unknown(["NEXT_ACTION_OWNER"] if b["actions_known"] else ["NEXT_ACTION_TITLE", "NEXT_ACTION_OWNER"]),
                           ["NEXT_ACTION_OWNER"], "unknown"))
    else:
        items = "".join(f"<li>{_e(o)}: {n:,}</li>" for o, n in b["owners"][:4])
        if len(b["owners"]) > 4:
            items += f"<li>و {len(b['owners']) - 4:,} مالک دیگر</li>"
        if b["ownerless"]:
            items += f"<li><b>بدون مالک: {b['ownerless']:,}</b></li>"
        total = len(b["actions"])
        cards.append(_card("OWNER", "مالک اقدام‌های باز", _e(f"{total:,} اقدام باز"),
                           f"<ul>{items}</ul>" if items else "اقدام بازی در این خروجی نیست.",
                           ["NEXT_ACTION_ID", "NEXT_ACTION_OWNER"],
                           "critical" if b["ownerless"] else ("good" if total else "neutral")))

    # DATE
    if b["overdue"] is None:
        cards.append(_card("DATE", "موعدها", "نامشخص", _unknown(["NEXT_ACTION_DUE_DATE"]),
                           ["NEXT_ACTION_DUE_DATE"], "unknown"))
    else:
        nd = b["next_due"]
        detail = (f"نزدیک‌ترین موعد باز: {_dl(nd['due']) or '—'} ({_e(_days_fa(nd['days']))}) — "
                  f"ثبت سفارش {_b(nd['case'] or '—')}" if nd else "موعد آینده‌ای ثبت نشده.")
        if b["undated"]:
            detail += f"<br>بدون موعد: {b['undated']:,}"
        val = f"{b['overdue']:,} اقدام معوق" if b["overdue"] else "بدون اقدام معوق"
        if b["overdue_critical"]:
            val += f" ({b['overdue_critical']:,} بحرانی)"
        cards.append(_card("DATE", "موعدها نسبت به تاریخ مرجع", _e(val), detail,
                           ["NEXT_ACTION_DUE_DATE", "NEXT_ACTION_PRIORITY"],
                           "critical" if b["overdue_critical"] else ("serious" if b["overdue"] else "good")))

    # RISK
    if b["risk"] is None:
        cards.append(_card("RISK", "متریال در خطر توقف", "نامشخص",
                           _unknown(["کد طبقه بحرانی", "KEY_MATERIAL"]),
                           ["کد طبقه بحرانی", "KEY_MATERIAL"], "unknown"))
    else:
        risk = b["risk"]
        stock = sum(1 for m in risk if m["band"] == "STOCKOUT")
        items = []
        for m in risk[:4]:
            res = "مقاومت نامشخص" if m["resistance"] is None else f"مقاومت {m['resistance']:,.0f} روز"
            flag = " — <b>بیرون از صف اقدام (بدون مالک و موعد)</b>" if m["has_action"] is False else ""
            if m["has_action"] is False and m.get("advice"):
                flag += f"<br>پیشنهاد مقاومت: {_e(m['advice'])}"
            case = f" · پرونده {_b(m['cases'][0])}" if m["cases"] else ""
            items.append(f"<li>{_b(m['material'])} — {_e(BAND_FA.get(m['band'], m['band']))} · {_e(res)}{case}{flag}</li>")
        if len(risk) > 4:
            items.append(f"<li>و {len(risk) - 4:,} متریال دیگر</li>")
        val = (f"{len(risk):,} متریال" + (f" · {stock:,} توقف خط" if stock else "")) if risk else "متریال توقف خط/بحرانی نیست"
        cards.append(_card("RISK", "متریال توقف خط / بحرانی", _e(val),
                           f"<ul>{''.join(items)}</ul>" if items else "",
                           ["کد طبقه بحرانی", "مقاومت (روز)", "KEY_MATERIAL", "NEXT_ACTION_TITLE",
                            "اقدام پیشنهادی مقاومت"],
                           "critical" if stock or b["risk_without_action"] else ("serious" if risk else "good")))

    # NEXT
    n = b["next"]
    if not b["actions_known"]:
        cards.append(_card("NEXT", "اقدام بعدی", "نامشخص", _unknown(["NEXT_ACTION_TITLE"]),
                           ["NEXT_ACTION_TITLE"], "unknown"))
    elif n is None:
        cards.append(_card("NEXT", "اقدام بعدی", "اقدام بازی نیست", "", ["NEXT_ACTION_TITLE"], "good"))
    else:
        detail = (f"ثبت سفارش {_b(n['case'] or '—')} · {_e(n['owner'] or 'بدون مالک')} · "
                  f"{_dl(n['due']) or 'بدون موعد'} ({_e(_days_fa(n['days']))})")
        cards.append(_card("NEXT", "اقدام بعدی", _e(n["title"]), detail,
                           ["NEXT_ACTION_TITLE", "NEXT_ACTION_OWNER", "NEXT_ACTION_DUE_DATE"],
                           GATE_TONE.get(n["gate"], "neutral") if n["gate"] != GATE_READY else "neutral"))

    # ASK
    if b["asks"]:
        cards.append(_card("ASK", "درخواست از مدیر", _e(f"{len(b['asks']):,} تصمیم"),
                           "<ul>" + "".join(f"<li>{_e(a)}</li>" for a in b["asks"]) + "</ul>",
                           ["NEXT_ACTION_OWNER", "NEXT_ACTION_DUE_DATE", "کد طبقه بحرانی"], "serious"))
    else:
        cards.append(_card("ASK", "درخواست از مدیر", "درخواستی از مدیر نیست",
                           "داده این خروجی دلیلی برای تصمیم مدیر نشان نمی‌دهد.", [], "good"))

    # صف اقدام
    queue = ""
    acts = b["actions"]
    if acts:
        rows = []
        for a in acts[:MAX_ACTIONS]:
            mats = ", ".join(a["materials"][:3]) + (" …" if len(a["materials"]) > 3 else "")
            gap = f'<div class="d">شاهد ناقص: {_e(a["gaps"])}</div>' if a["gaps"] else ""
            rows.append(
                "<tr>"
                f'<td><span class="dgate" data-tone="{GATE_TONE[a["gate"]]}">{_e(GATE_FA[a["gate"]])}</span></td>'
                f'<td>{_e(PRIORITY_FA.get(a["priority"], a["priority"] or "—"))}</td>'
                f'<td>{_e(a["title"])}{gap}</td>'
                f'<td>{_b(a["case"] or "—")}<div class="d">{_b(mats)}</div></td>'
                f'<td>{_e(a["owner"] or "—")}</td>'
                f'<td class="num">{_dl(a["due"]) or "—"}<div class="d">{_e(_days_fa(a["days"]))}</div></td>'
                "</tr>")
        more = (f'<div class="more">{len(acts) - MAX_ACTIONS:,} اقدام دیگر در تب‌ها و Excel '
                "(ستون‌های «پیشنهاد GSI»، «مالک پیشنهادی»، «موعد داخلی اقدام»).</div>"
                if len(acts) > MAX_ACTIONS else "")
        queue = ('<div class="dqueue"><h3>صف اقدام — ترتیب: معوق، اولویت، موعد</h3>'
                 '<div class="dqueue-wrap"><table><thead><tr><th>دروازه اجرا</th><th>اولویت</th>'
                 '<th>اقدام</th><th>پرونده / متریال</th><th>مالک</th><th>موعد</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>{more}</div>')

    return (f'<section class="dbrief" id="decision_brief" aria-labelledby="dbrief_h">'
            f'<div class="dbrief-head"><h2 id="dbrief_h">برگ تصمیم</h2>'
            f'<small>فقط از داده همین خروجی · نامعلوم = «نامشخص»، نه صفر</small></div>'
            f'<div class="dbrief-grid">{"".join(cards)}</div>{queue}</section>')


def build_decision_brief_html(df: pd.DataFrame, ref_date: str) -> str:
    return render_decision_brief_html(compute_decision_brief(df, ref_date))

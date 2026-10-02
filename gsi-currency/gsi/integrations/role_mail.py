# -*- coding: utf-8 -*-
"""One reviewed, HR-routed message per expert role and person.

No file/source reads occur during planning. The only input is the same published
report and HR frame. Ambiguous identity or requested CC is a hard skip.
"""
from __future__ import annotations

import argparse
import html

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from ..core.text import normalize_persian_text, clean_employee_code
from ..design import brand as _BRAND
from ..personalization.hr_scope import _active, _name, _level
from ..resolve.expert_roles import ROLES

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
CC_LEVELS = ("head", "manager", "vice")


def _s(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _norm(v) -> str:
    return normalize_persian_text(_s(v)).strip()


@dataclass(frozen=True)
class MailPlan:
    employee_code: str
    name: str
    role_key: str
    role_label: str
    to: str
    cc: tuple[str, ...]
    cases: tuple[dict, ...]
    run_id: str


def _directory(hr: pd.DataFrame):
    active = []
    for raw in hr.to_dict("records"):
        if not _active(raw.get("HR_STATUS")):
            continue
        name = _name(raw)
        code = clean_employee_code(raw.get("KEY_EMP", ""))
        email = _s(raw.get("HR_EMAIL")).lower()
        if name and code:
            active.append({**raw, "_name": name, "_code": code, "_email": email})
    names = Counter(x["_name"] for x in active)
    codes = Counter(x["_code"] for x in active)
    emails = Counter(x["_email"] for x in active if _EMAIL.fullmatch(x["_email"]))
    return {x["_name"]: x for x in active if names[x["_name"]] == 1
            and codes[x["_code"]] == 1 and _EMAIL.fullmatch(x["_email"])
            and emails[x["_email"]] == 1}


def _cc(person, directory, levels):
    found = []
    for level in levels:
        if level in {"head", "manager"}:
            name = _norm(person.get("HR_HEAD" if level == "head" else "HR_MANAGER"))
            leader = directory.get(name)
            if not name or leader is None or _level(leader.get("HR_POST")) != level:
                return None, f"CC_{level.upper()}_UNRESOLVED"
        else:
            unit = _norm(person.get("HR_VICE"))
            candidates = [x for x in directory.values()
                          if _level(x.get("HR_POST")) == "vice" and _norm(x.get("HR_VICE")) == unit]
            if not unit or len(candidates) != 1:
                return None, "CC_VICE_UNRESOLVED"
            leader = candidates[0]
        if leader["_email"] != person["_email"] and leader["_email"] not in found:
            found.append(leader["_email"])
    return tuple(found), ""


def plan_messages(main: pd.DataFrame, hr: pd.DataFrame, *, run_id: str,
                  cc_levels: Iterable[str] = ("head", "manager"),
                  role_keys: Iterable[str] | None = None):
    levels = tuple(dict.fromkeys(cc_levels))
    if any(x not in CC_LEVELS for x in levels):
        raise ValueError("سطح CC نامعتبر است.")
    roles = {r.key: r for r in ROLES}
    selected = tuple(role_keys) if role_keys is not None else tuple(roles)
    if any(k not in roles for k in selected):
        raise ValueError("نقش کارشناس بدون ستون مالکیت معتبر است؛ ارسال متوقف شد.")
    if not run_id or main is None or hr is None or hr.empty:
        raise ValueError("Snapshot و HR منتشرشده هر دو لازم‌اند.")
    directory = _directory(hr)
    if not directory:
        raise ValueError("هیچ هویت فعال، یکتا و دارای ایمیل معتبر در HR پیدا نشد.")
    grouped = defaultdict(dict)
    skipped = Counter()
    for row in main.to_dict("records"):
        current_role = _norm(row.get("EXPERT_ROLE"))
        action = _s(row.get("NEXT_ACTION_TITLE"))
        owner_role = _norm(row.get("NEXT_ACTION_OWNER"))
        reg = _s(row.get("CANONICAL_REG")) or _s(row.get("KEY_REG"))
        if not reg or not action:
            continue
        for key in selected:
            role = roles[key]
            if current_role != _norm(role.fa) or owner_role not in {_norm(role.short), _norm(role.fa)}:
                continue
            name = _norm(row.get(key))
            person = directory.get(name)
            if person is None:
                skipped["OWNER_HR_UNRESOLVED"] += 1
                continue
            # The case's current owner must agree with the role-specific source.
            if _norm(row.get("CANONICAL_EXPERT")) != name:
                skipped["CURRENT_OWNER_CONFLICT"] += 1
                continue
            case = {"reg": reg, "action": action,
                    "priority": _s(row.get("NEXT_ACTION_PRIORITY")),
                    "due": _s(row.get("NEXT_ACTION_DUE_DATE")),
                    "gap": _s(row.get("NEXT_ACTION_EVIDENCE_GAPS"))}
            case_id = (reg, action, case["due"])
            grouped[(person["_code"], key)][case_id] = case
    plans = []
    for (code, key), cases in sorted(grouped.items()):
        person = next(x for x in directory.values() if x["_code"] == code)
        cc, reason = _cc(person, directory, levels)
        if reason:
            skipped[reason] += 1
            continue
        ordered = tuple(sorted(cases.values(), key=lambda c: (c["due"] or "9999", c["reg"])))
        plans.append(MailPlan(code, person["_name"], key, roles[key].fa,
                              person["_email"], cc, ordered, run_id))
    return plans, dict(skipped)


def render_html(plan: MailPlan, *, ref_date: str = "") -> str:
    esc = lambda v: html.escape(str(v), quote=True)
    rows = "".join("<tr>" + "".join(f"<td>{esc(c[k] or '—')}</td>"
                  for k in ("reg", "action", "priority", "due", "gap")) + "</tr>" for c in plan.cases)
    return (f'<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>body{font:14px/1.9 IRANSansWeb,Tahoma,Arial,sans-serif;color:#0f3538;background:#f3f8f8}'
            '.wrap{max-width:900px;margin:auto;background:white;padding:24px;border-radius:16px;overflow:hidden}'
            'h1{font-size:23px}table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #d5e8e8;text-align:right}'
            'th{background:#0f3538;color:white}.note{background:#faf3e4;border-right:4px solid #c79a4a;padding:12px}'
            '@media(max-width:600px){.scroll{overflow:auto}table{min-width:650px}}</style></head><body><div class="wrap">'
            '<table width="100%" cellpadding="0" cellspacing="0" style="margin:-24px -24px 18px;width:calc(100% + 48px);'
            'border-collapse:collapse">'
            + _BRAND.email_header_html(f"اقدام‌های {plan.name}",
                                       f"{plan.role_label} · تاریخ مرجع {ref_date or 'نامعلوم'} · "
                                       f"{len(plan.cases)} پرونده از گزارش منتشرشده") + '</table>'

            '<div class="scroll"><table><thead><tr><th>ثبت سفارش</th><th>اقدام پیشنهادی</th><th>اولویت</th>'
            '<th>موعد</th><th>شکاف شاهد</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
            '<p class="note">اقدام‌ها پیشنهاد GSI هستند؛ پیش از انجام، شاهد و مالک پرونده بررسی شود. '
            'نامعلوم به معنی صفر یا انجام‌شده نیست.</p></div></body></html>')


def outlook_message(plan: MailPlan, *, ref_date: str = "", send: bool = False,
                    display: bool = False):
    """Draft by default; send only when the caller explicitly passes send=True."""
    from .daily_email import _outlook_session, NoRecipients
    with _outlook_session() as win32:
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.BodyFormat = 2
        mail.Subject = f"GSi | اقدام‌های {plan.role_label} | {ref_date or plan.run_id}"
        mail.To = plan.to
        mail.CC = "; ".join(plan.cc)
        sender = os.environ.get("GSI_EMAIL_SENDER", "").strip().lower()
        if sender:
            account = next((a for a in outlook.Session.Accounts
                            if str(getattr(a, "SmtpAddress", "")).strip().lower() == sender), None)
            if account is None:
                raise RuntimeError("حساب فرستنده Outlook پیدا نشد.")
            mail.SendUsingAccount = account
        _BRAND.attach_email_header(mail)
        mail.HTMLBody = render_html(plan, ref_date=ref_date)
        if not mail.Recipients.ResolveAll():
            raise NoRecipients("Outlook گیرنده یا رونوشت را تأیید نکرد؛ پیام ذخیره/ارسال نشد.")
        mail.Save()
        if send:
            mail.Send()
        elif display:
            mail.Display()
    return {"sent": bool(send), "drafted": not send, "cases": len(plan.cases)}


def dispatch(plans: Iterable[MailPlan], *, ref_date: str = "", send: bool = False):
    """Reserve each send once per published run/person/role before Outlook.

    A crashed/uncertain send remains RESERVED, requiring manual reconciliation
    rather than risking a duplicate external message on the next schedule.
    """
    from ..warehouse.store import Warehouse
    plans = tuple(plans)
    results = []
    wh = Warehouse(initialize=False) if send else None
    if send:
        # Preflight the entire batch atomically: an already-sent later item
        # must not allow earlier messages to go out before the conflict appears.
        with wh.db() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS wh_role_mail_dispatch ("
                         "run_id TEXT NOT NULL, employee_code TEXT NOT NULL, role_key TEXT NOT NULL, "
                         "state TEXT NOT NULL, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                         "PRIMARY KEY(run_id,employee_code,role_key))")
            conn.execute("BEGIN IMMEDIATE")
            for plan in plans:
                conn.execute("INSERT INTO wh_role_mail_dispatch(run_id,employee_code,role_key,state) "
                             "VALUES(?,?,?,'RESERVED')", (plan.run_id, plan.employee_code, plan.role_key))
    for plan in plans:
        result = outlook_message(plan, ref_date=ref_date, send=send)
        if send:
            with wh.db() as conn:
                conn.execute("UPDATE wh_role_mail_dispatch SET state='SENT' "
                             "WHERE run_id=? AND employee_code=? AND role_key=?",
                             (plan.run_id, plan.employee_code, plan.role_key))
        results.append(result)
    return results


def from_published(*, cc_levels=("head", "manager"), role_keys=None):
    from ..warehouse.service import last_report
    from ..warehouse.store import Warehouse
    report = last_report()
    if report is None:
        raise ValueError("گزارش منتشرشده موجود نیست.")
    _, main, extras, _ = report
    if (extras.get("source_fallbacks") or {}).get("hr") or (extras.get("source_failures") or {}).get("hr"):
        raise ValueError("HR این انتشار تازه و معتبر نیست؛ مسیریابی ایمیل متوقف شد.")
    wh = Warehouse(initialize=False)
    frames, meta = wh.published_frames("hr")
    hr = frames.get("main")
    if hr is None or hr.empty or (meta or {}).get("run_id") != extras.get("warehouse_run_id"):
        raise ValueError("HR و گزارش به یک اجرای منتشرشده تعلق ندارند.")
    plans, skipped = plan_messages(main, hr, run_id=extras["warehouse_run_id"],
                                   cc_levels=cc_levels, role_keys=role_keys)
    return plans, skipped, str(extras.get("published_reference_date") or "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Create role-scoped Outlook drafts from published GSI data")
    ap.add_argument("--roles", help="Comma-separated EXPERT_* keys; default all supported roles")
    ap.add_argument("--cc", default="head,manager", help="head,manager,vice or empty")
    ap.add_argument("--preview", action="store_true", help="Counts only; do not open Outlook")
    ap.add_argument("--send", action="store_true", help="Explicitly send instead of saving drafts")
    ns = ap.parse_args(argv)
    roles = ns.roles.split(",") if ns.roles else None
    plans, skipped, ref = from_published(cc_levels=tuple(x for x in ns.cc.split(",") if x), role_keys=roles)
    if ns.send and skipped:
        raise SystemExit("مسیریابی ناقص است؛ ارسال دسته‌ای متوقف شد: " + json.dumps(skipped, ensure_ascii=False))
    print(f"Published run: {plans[0].run_id if plans else '—'} | messages: {len(plans)} | skipped: {skipped}")
    if ns.preview:
        return 0
    dispatch(plans, ref_date=ref, send=ns.send)
    print("Sent" if ns.send else "Drafts saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

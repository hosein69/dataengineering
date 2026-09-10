# -*- coding: utf-8 -*-
"""بسته ایمیل مدیریتی.

فهرست گیرندگان **پیکربندی محرمانه** است و هرگز داخل سورس نگه‌داری
نمی‌شود — همان قاعده‌ای که در پلتفرم AIBL هم اعمال شد. ترتیب حل:

    ۱) HRP_EMAIL_TO="a@x.invalid;b@x.invalid"
    ۲) HRP_RECIPIENTS_FILE=/secure/recipients.yaml
    ۳) $HRP_HOME/recipients.yaml
    ۴) **جدول پرسنلی خودِ اجرا** — ستون email (HRP_EMAIL_FROM_HR=1)

گزینه ۴ ترجیح دارد: فهرست هیچ‌جا کپی نمی‌شود، همیشه با آخرین وضعیت
پرسنلی هم‌گام است، و پرسنل غیرفعال خودکار حذف می‌شود.

بدون پیکربندی، ساخت بسته کار می‌کند ولی **ارسال با خطای صریح متوقف
می‌شود** تا هرگز به فهرستی قدیمی ارسال نشود.
"""
from __future__ import annotations

__contract__ = 1

import os
import re
from pathlib import Path
from typing import List, Optional

from . import aqua

RECIPIENTS_ENV = "HRP_EMAIL_TO"
RECIPIENTS_FILE_ENV = "HRP_RECIPIENTS_FILE"
RECIPIENTS_BASENAME = "recipients.yaml"


class NoRecipients(RuntimeError):
    """هیچ گیرنده‌ای پیکربندی نشده است."""


def _split(raw: str) -> List[str]:
    return [x.strip() for x in re.split(r"[,;\s]+", raw or "")
            if x.strip() and "@" in x]


def _from_file(path: Path) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        import yaml
        data = yaml.safe_load(text)
        if isinstance(data, dict) and data.get("recipients"):
            return [str(x).strip() for x in data["recipients"] if "@" in str(x)]
        if isinstance(data, list):
            return [str(x).strip() for x in data if "@" in str(x)]
    except Exception:
        pass
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip().lstrip("- ").strip()
        if "@" in line:
            out.append(line)
    return out


# ── انتخاب گیرنده از جدول پرسنلی اجرا ────────────────────────────────────
HR_ENABLE_ENV = "HRP_EMAIL_FROM_HR"
HR_ROLES_ENV = "HRP_EMAIL_HR_ROLES"
HR_MANAGEMENTS_ENV = "HRP_EMAIL_HR_MANAGEMENTS"
HR_DEPARTMENTS_ENV = "HRP_EMAIL_HR_DEPARTMENTS"
HR_MAX_ENV = "HRP_EMAIL_HR_MAX"

#: پیش‌فرض: سطوح مدیریتی. گزارش عملکرد، سند مدیریتی است.
DEFAULT_HR_ROLES = ("مدیر", "رئیس", "مسئول")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

#: نام‌های محتمل ستون ایمیل در جدول پرسنلی
EMAIL_COLUMNS = ("email", "Email", "EMAIL", "hr_email", "HR_EMAIL",
                 "ایمیل", "پست الکترونیک", "پست الکترونیکی")


def _csv_env(name: str, default=()) -> tuple:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return tuple(default)
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def hr_recipients(people) -> List[str]:
    """گیرندگان را از ستون ایمیل جدول پرسنلی همین اجرا برمی‌دارد.

    فیلترها: فقط **فعال**، نشانی معتبر، و در صورت تعیین، انطباق با
    نقش / مدیریت / اداره. نشانی‌ها لاگ یا ذخیره نمی‌شوند؛ فقط تعداد.
    """
    if people is None or getattr(people, "empty", True):
        return []
    col = next((c for c in EMAIL_COLUMNS if c in people.columns), None)
    if col is None:
        return []

    mail = people[col].fillna("").astype(str).str.strip()
    keep = mail.map(lambda x: bool(_EMAIL_RE.match(x)))

    if "active" in people.columns:
        act = people["active"]
        keep &= act.map(lambda v: str(v).strip() not in
                        ("0", "False", "false", "غیرفعال", "nan", ""))
    elif "status" in people.columns:
        st = people["status"].fillna("").astype(str)
        keep &= st.str.contains("فعال", na=False) & ~st.str.contains("غیرفعال", na=False)

    for env, col_name, default in ((HR_ROLES_ENV, "role", DEFAULT_HR_ROLES),
                                   (HR_MANAGEMENTS_ENV, "management", ()),
                                   (HR_DEPARTMENTS_ENV, "department", ())):
        wanted = _csv_env(env, default)
        if not wanted or col_name not in people.columns:
            continue
        text = people[col_name].fillna("").astype(str)
        keep &= text.apply(lambda v: any(w in v for w in wanted))

    out = sorted({m.lower() for m in mail[keep] if m})
    cap = os.environ.get(HR_MAX_ENV, "").strip()
    if cap.isdigit():
        out = out[:int(cap)]
    return out


def recipients_path() -> Optional[Path]:
    explicit = os.environ.get(RECIPIENTS_FILE_ENV, "").strip()
    if explicit:
        return Path(explicit)
    home = os.environ.get("HRP_HOME") or str(Path.home() / ".hrperf")
    for c in (Path(home) / RECIPIENTS_BASENAME, Path.cwd() / RECIPIENTS_BASENAME):
        if c.exists():
            return c
    return None


def recipients(people=None) -> List[str]:
    raw = os.environ.get(RECIPIENTS_ENV, "")
    if raw.strip():
        return _split(raw)
    p = recipients_path()
    if p:
        found = _from_file(p)
        if found:
            return found
    if os.environ.get(HR_ENABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
        return hr_recipients(people)
    return []


def build_email_html(title: str, ref_date: str, summary_rows: List[tuple],
                     body_note: str = "") -> str:
    """HTML ساده و سازگار با Outlook — بدون CSS خارجی، بدون JS."""
    import html as _h
    cards = "".join(
        f'<td style="padding:10px 14px;background:{aqua.LIGHT["highlight"]};border:1px solid {aqua.LIGHT["border-soft"]};'
        f'border-radius:10px;text-align:center">'
        f'<div style="font-size:20px;font-weight:700;color:{aqua.LIGHT["header"]}">{_h.escape(str(v))}</div>'
        f'<div style="font-size:11px;color:{aqua.LIGHT["text-2"]}">{_h.escape(str(k))}</div></td>'
        f'<td style="width:10px"></td>'
        for k, v in summary_rows)
    return f"""<html><body dir="rtl" style="font-family:'IRANSans Light',Tahoma,Arial;
background:{aqua.LIGHT["surface"]};color:{aqua.LIGHT["text"]};margin:0;padding:18px">
<div style="max-width:900px;margin:auto">
<div style="background:linear-gradient(120deg,{aqua.LIGHT["header"]},{aqua.LIGHT["brand-strong"]});color:#fff;
padding:18px 22px;border-radius:14px">
<div style="font-size:20px;font-weight:700">{_h.escape(title)}</div>
<div style="font-size:12px;opacity:.9;margin-top:5px">تاریخ مرجع {_h.escape(ref_date)}</div>
</div>
<table style="margin-top:14px;border-collapse:separate"><tr>{cards}</tr></table>
<p style="font-size:12px;color:{aqua.LIGHT["text-2"]};line-height:2">{_h.escape(body_note)}</p>
<p style="font-size:11px;color:{aqua.LIGHT["text-3"]}">رتبه‌ها فقط درون گروه همتا
(مدیریت + اداره + نوع کار) معنا دارند. جزئیات در فایل‌های پیوست است.</p>
</div></body></html>"""


def send_via_outlook(subject: str, body_html: str,
                     attachments: Optional[List[Path]] = None,
                     send: bool = False, display: bool = True,
                     people=None) -> dict:
    """ساخت/ارسال ایمیل با Outlook کلاسیک (فقط ویندوز)."""
    to = recipients(people)
    if not to:
        raise NoRecipients(
            "هیچ گیرنده‌ای پیکربندی نشده است. یکی از این‌ها را تنظیم کنید:\n"
            f"    {RECIPIENTS_ENV}=\"a@example.invalid;b@example.invalid\"\n"
            f"    {RECIPIENTS_FILE_ENV}=/path/to/{RECIPIENTS_BASENAME}\n"
            f"    یا {RECIPIENTS_BASENAME} را در HRP_HOME بگذارید،\n"
            f"    یا {HR_ENABLE_ENV}=1 تا از ستون email جدول پرسنلی خوانده شود.")
    if not (send or display):
        return {"recipients": to, "sent": False}
    try:
        import win32com.client as win32
    except ImportError as ex:
        raise RuntimeError("برای Outlook باید pywin32 و Classic Outlook نصب باشد.") from ex
    outlook = win32.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.BodyFormat = 2
    mail.Subject = subject
    mail.To = "; ".join(to)
    sender = os.environ.get("HRP_EMAIL_SENDER", "").strip().lower()
    if sender:
        try:
            for acc in outlook.Session.Accounts:
                if getattr(acc, "SmtpAddress", "").lower() == sender:
                    mail._oleobj_.Invoke(*(64209, 0, 8, 0, acc))
                    break
        except Exception:
            pass
    for a in (attachments or []):
        if Path(a).exists():
            mail.Attachments.Add(str(Path(a).resolve()))
    mail.HTMLBody = body_html
    mail.Save()
    if send:
        mail.Send()
        return {"recipients": to, "sent": True}
    mail.Display()
    return {"recipients": to, "sent": False}

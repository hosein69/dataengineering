# -*- coding: utf-8 -*-
"""زبان یک‌دست برای عنوان ستون‌ها: همه فارسی یا همه انگلیسی.

سه نوع عنوان در برنامه هست:

1. **کلید فنی** (``BLREG_STATUS``، ``MOGH_PR_NO``) — برچسب فارسی از کاتالوگ
   فیلد می‌آید و برچسب انگلیسی با قاعده توکنی ساخته می‌شود
   (``MOGH`` ← Expert، ``CRD`` ← Credit، ``PCT`` ← %).
2. **برچسب فارسی کاتالوگ** («شرح کالا · بارنامه») — برای انگلیسی به کلید
   فنی برگردانده می‌شود و از همان قاعده انگلیسی می‌گیرد.
3. **عنوان فارسی نوشته‌شده در کد نماها** («مرحله جاری»، «روز انتظار») —
   از واژه‌نامه ``glossary_fa_en``.

قرارداد: ``label(col, lang)`` هرگز استثنا نمی‌دهد و هرگز عنوان خالی
برنمی‌گرداند؛ ``localize_frame`` عنوان تکراری نمی‌سازد.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Optional

from gsi.i18n.glossary_fa_en import entries
from gsi.i18n.key_fa import fa_from_key

FA, EN = "fa", "en"
LANGS = (FA, EN)
LANG_LABELS = {FA: "فارسی", EN: "English"}

_FA_CHARS = re.compile(r"[؀-ۿ]")
_KEY_RE = re.compile(r"^_?[A-Za-z][A-Za-z0-9_]*$")

# ── توکن‌های کلید فنی ────────────────────────────────────────────────────
TOKEN_EN: Dict[str, str] = {
    # پیشوند سورس‌ها
    "MOGH": "Expert", "MOGHAVEMAT": "Resistance file", "CRD": "Credit",
    "CL": "Customs", "COT": "Cotage", "ORC": "Oracle", "IL": "Import license",
    "DOC": "Doc check", "BL": "B/L", "BLREG": "B/L–Reg", "SATA": "SATA",
    "NTSW": "NTSW", "SAP": "SAP", "HR": "HR", "WH": "Warehouse", "CB": "Central bank",
    "FX": "FX", "ORG": "Org", "IKCO": "IKCO", "SAPCO": "SAPCO",
    # اختصارها
    "REG": "Registration", "PR": "PR", "PO": "PO", "PI": "PI", "LC": "LC",
    "HS": "HS", "ID": "ID", "KPI": "KPI", "EUR": "EUR", "USD": "USD", "CNY": "CNY",
    "AED": "AED", "RIAL": "Rial", "NO": "No.", "QTY": "Qty", "PCT": "%",
    "EQ": "Eq.", "ALLOC": "Allocation", "DESC": "Description", "DESCS": "Descriptions",
    "INV": "Invoice", "REQ": "Request", "FIN": "Finance", "MFR": "Manufacturer",
    "BENEF": "Beneficiary", "DEPT": "Department", "EMP": "Employee",
    "RECON": "Reconciliation", "WAVG": "Weighted avg", "DO": "D/O",
    "DEST": "Destination", "BARAT": "Draft", "FA": "(FA)", "AI": "AI",
    "CRITICALITY": "Criticality", "SWIFT": "SWIFT", "CERTAIN": "Certain",
    "DAYS": "Days", "DATE": "Date", "IN": "in", "ON": "on", "AT": "at", "TO": "to",
    "FOR": "for", "FROM": "from", "PER": "per", "NOT": "not", "WITHOUT": "without",
    "CANONICAL": "", "WHO": "Who", "LOWER": "Lower", "BOUND": "Bound", "ACCT": "Account", "CAT": "Category",
    "GR": "GR", "IND": "Indicator", "MPN": "MPN", "PGR": "Purchasing group", "PURCH": "Purchase",
    "REC": "Receipt", "RFQ": "RFQ", "UOM": "UoM",
}

_SMALL = {"in", "on", "at", "to", "for", "from", "per", "not", "without"}


def _norm(s: str) -> str:
    """نرمال‌سازی برای جستجو: نیم‌فاصله، ی/ک عربی، ٪، فاصله اضافه."""
    s = str(s).replace("‌", " ").replace("ي", "ی").replace("ى", "ی")
    s = s.replace("ك", "ک").replace("ڪ", "ک").replace("ة", "ه").replace("ۀ", "ه")
    s = s.replace("٪", "%").replace("‏", "")
    return re.sub(r"\s+", " ", s).strip()


_GLOSS: Dict[str, str] = {}
_GLOSS_REV: Dict[str, str] = {}
for _fa, _en in entries():
    _GLOSS.setdefault(_norm(_fa), _en)
    _GLOSS_REV.setdefault(_en.lower(), _fa)

#: برچسب‌های فارسی کاتالوگ (از ``register_display``): {کلید: برچسب}
_DISPLAY: Dict[str, str] = {}
_DISPLAY_REV: Dict[str, str] = {}


def register_display(display: Mapping[str, str]) -> None:
    """برچسب‌های کاتالوگ فیلد را ثبت می‌کند تا برگشت فارسی ← کلید ممکن شود."""
    for k, v in (display or {}).items():
        k, v = str(k), str(v)
        _DISPLAY[k] = v
        _DISPLAY_REV.setdefault(_norm(v), k)


def is_persian(text: str) -> bool:
    return bool(_FA_CHARS.search(str(text)))


def humanize_key(key: str) -> str:
    """``BLREG_REG_SHIPPED_PCT`` ← «B/L–Reg Registration Shipped %».

    ``IS_*`` به سؤال تبدیل می‌شود: ``IS_IN_CUSTOMS`` ← «In customs?».
    """
    raw = str(key).strip("_")
    toks = [t for t in raw.split("_") if t]
    if not toks:
        return str(key)
    question = False
    ups = [t.upper() for t in toks]
    if "IS" in ups and len(toks) > 1:
        i = ups.index("IS")
        question = not (i + 1 < len(ups) and ups[i + 1] == "UNKNOWN")
        toks = toks[:i] + toks[i + 1:]
    words: List[str] = []
    for i, t in enumerate(toks):
        up = t.upper()
        if up in TOKEN_EN:
            w = TOKEN_EN[up]
        elif t.isdigit():
            w = t
        elif t.isupper() or t.islower():
            w = t.capitalize()
        else:
            w = t
        if w in _SMALL and i == 0:
            w = w.capitalize()
        if w:
            words.append(w)
    if not words:
        return str(key)
    # «Unknown» در انتهای *_IS_UNKNOWN
    text = " ".join(words).replace(" %", " (%)") if words[-1] == "%" else " ".join(words)
    text = text.replace("  ", " ")
    if question:
        text = text[0].upper() + text[1:].lower() + "?"
    return text


_SUFFIXES = (
    (re.compile(r"\s*\(روز\)$"), " (days)"),
    (re.compile(r"\s*\(%\)$"), " (%)"),
    (re.compile(r"\s*\(ثانیه\)$"), " (s)"),
    (re.compile(r"\s*\(حداقل\)$"), " (min)"),
)


#: عبارت‌های پویای برنامه (پرچم‌های پیوند بارنامه ↔ ثبت سفارش، معنای شکاف جریان پول) که
#: عدد یا کد لاتین دارند و در واژه‌نامه ثابت نمی‌گنجند. ``{0}`` و ``{1}`` هر متنی بدون حرف فارسی است.
_PATTERN_RAW = (
    ("{0} بارنامه با ارزش نامعلوم (در جمع نیامد)", "{0} B/L(s) with unknown value (left out of the total)"),
    ("{0} بارنامه با ارز نامعلوم (در جمع نیامد)", "{0} B/L(s) with unknown currency (left out of the total)"),
    ("{0} بارنامه مشترک با ثبت سفارش دیگر (سهم نامعلوم)", "{0} B/L(s) shared with another registration (share unknown)"),
    ("بارنامه به {0} ثبت سفارش وصل است؛ سهم هر یک در منبع نیست",
     "B/L linked to {0} registrations; the source has no share for each"),
    ("اختلاف ارزش فاکتور ساتا و گمرک ({0}٪)", "SATA and customs invoice values differ ({0}%)"),
    ("ارز فاکتور ساتا ({0}) با ارز اظهار گمرکی ({1}) یکی نیست",
     "SATA invoice currency ({0}) differs from the customs declared currency ({1})"),
    ("ارز بارنامه‌ها: {0}", "B/L currencies: {0}"),
    ("ارز ثبت سفارش: {0}", "Registration currency: {0}"),
    ("اختلاف شاهد {0} با {1}؛ مانده نقدی اثبات‌شده نیست",
     "Difference between the {0} and {1} evidence; not a proven cash balance"),
    ("{0} روز", "{0} days"),
    # مغایرت ارز گام‌ها (29.21): ارز تخصیص، خرید یا تعهد کنار ارز ثبت سفارش؛ گزارش می‌شود، ادغام نمی‌شود
    ("ارز تخصیص ({0}) با ارز ثبت سفارش ({1}) یکی نیست",
     "Allocation currency ({0}) differs from the registration currency ({1})"),
    ("ارز خرید ({0}) با ارز تخصیص ({1}) یکی نیست", "Purchase currency ({0}) differs from the allocation currency ({1})"),
    ("ارز خرید ({0}) با ارز ثبت سفارش ({1}) یکی نیست",
     "Purchase currency ({0}) differs from the registration currency ({1})"),
    ("ارز تعهد ({0}) با ارز تخصیص ({1}) یکی نیست", "Obligation currency ({0}) differs from the allocation currency ({1})"),
    ("ارز تعهد ({0}) با ارز ثبت سفارش ({1}) یکی نیست",
     "Obligation currency ({0}) differs from the registration currency ({1})"),
    ("درخواست رد یا باطل‌شده به ارز {0}", "Rejected or void requests in {0}"),
    ("ارز از اصلاحیه {0} ({1})", "Currency from amendment {0} ({1})"),
    ("مبلغ از اصلاحیه {0}", "Amount from amendment {0}"),
)
_SLOT = r"(?:[^\u0600-\u06FF\u00B7\u2014]|\u060C)+?"


#: همان کار وقتی جای خالی خودش متن فارسی است (نام منبع ثبت سفارش، فهرست «منبع=ارز»): جای
#: خالی جداگانه با ``phrase`` ترجمه می‌شود و از « · »، «؛»، « — » و « | » نمی‌گذرد تا دو پیام
#: کنار هم یک پیام خوانده نشوند.
_PHRASE_PATTERN_RAW = (
    ("ثبت سفارش در {0} باطل‌شده است", "The registration is void in {0}"),
    ("چند مبلغ متفاوت در {0}", "Several different amounts in {0}"),
    ("چند ارز متفاوت در {0}", "Several different currencies in {0}"),
    ("ارز ناشناخته در {0}: {1}", "Unknown currency in {0}: {1}"),
    ("ارز ثبت سفارش در منبع‌ها یکی نیست: {0}", "Registration currency differs between sources: {0}"),
    ("مبلغ ثبت سفارش در منبع‌ها یکی نیست: {0}", "Registration amount differs between sources: {0}"),
    ("مبلغ هست ولی ارز آن معلوم نیست: {0}", "Amount present but its currency is unknown: {0}"),
)
_PHRASE_SLOT = r"[^\u00B7\u061B\u2014|]+?"


def _compile_pattern(fa: str, slot: str = _SLOT) -> "re.Pattern[str]":
    parts = re.split(r"\{(\d)\}", _norm(fa))
    rx = "".join(re.escape(p) if i % 2 == 0 else f"(?P<g{p}>{slot})" for i, p in enumerate(parts))
    return re.compile(f"^{rx}$")


_PATTERNS = tuple((_compile_pattern(fa), en) for fa, en in _PATTERN_RAW)
_PHRASE_PATTERNS = tuple((_compile_pattern(fa, _PHRASE_SLOT), en) for fa, en in _PHRASE_PATTERN_RAW)


def _pattern_en(n: str) -> Optional[str]:
    for rx, en in _PATTERNS:
        m = rx.match(n)
        if m:
            vals = {k: v.strip().replace("، ", ", ").replace("،", ",") for k, v in m.groupdict().items()}
            return re.sub(r"\{(\d)\}", lambda g: vals["g" + g.group(1)], en)
    for rx, en in _PHRASE_PATTERNS:
        m = rx.match(n)
        if m:
            vals = {k: phrase(v, EN) for k, v in m.groupdict().items()}
            return re.sub(r"\{(\d)\}", lambda g: vals["g" + g.group(1)], en)
    return None


def _fa_to_en(text: str) -> Optional[str]:
    n = _norm(text)
    if n in _GLOSS:
        return _GLOSS[n]
    pat = _pattern_en(n)
    if pat:
        return pat
    if n in _DISPLAY_REV:
        return humanize_key(_DISPLAY_REV[n])
    # «برچسب · سورس» از unique_labels
    if " · " in n:
        head, tail = n.rsplit(" · ", 1)
        h = _fa_to_en(head)
        if h:
            t = _fa_to_en(tail) or (humanize_key(tail) if _KEY_RE.match(tail) else None)
            if t:
                return f"{h} · {t}"
    for rx, rep in _SUFFIXES:
        if rx.search(n):
            base = _fa_to_en(rx.sub("", n))
            if base:
                return base + rep
    return None


#: متن ساخت‌یافته برنامه (شاهد مرحله، علت بحرانی): «الف؛ ب»، «کلید=مقدار»، «کد: متن»، «متن (پرانتز)»
_SOFT_SPLITS = (("؛ ", "; "), ("; ", "; "), (" | ", " | "), (" / ", " / "))
_KEY_VALUE = re.compile(r"^(?P<k>[^=]+)=(?P<v>.*)$", re.S)
_CODE_TEXT = re.compile(r"^(?P<c>[^؀-ۿ:]+): (?P<t>.+)$", re.S)
_PAREN = re.compile(r"^(?P<a>.+?) \((?P<b>[^()]+)\)$", re.S)


def _structured_en(t: str) -> Optional[str]:
    """ترجمه تکه‌تکه متن ساخت‌یافته؛ اگر هیچ تکه‌ای ترجمه نشود None (متن همان می‌ماند)."""
    for sep, join in _SOFT_SPLITS:
        if sep in t:
            parts = t.split(sep)
            out = [phrase(p, EN) for p in parts]
            return join.join(out) if out != [p.strip() for p in parts] else None
    m = _KEY_VALUE.match(t)
    if m and is_persian(m["k"]):
        key = _fa_to_en(m["k"].strip())
        return f"{key}={phrase(m['v'], EN)}" if key else None
    m = _CODE_TEXT.match(t)
    if m:
        rest = phrase(m["t"], EN)
        return f"{m['c']}: {rest}" if rest != m["t"].strip() else None
    m = _PAREN.match(t)
    if m:
        a, b = phrase(m["a"], EN), phrase(m["b"], EN)
        return f"{a} ({b})" if (a, b) != (m["a"].strip(), m["b"].strip()) else None
    return None


def phrase(text, lang: str = FA) -> str:
    """متن رابط (نه عنوان ستون): مرحله، وضعیت، یادداشت. فقط متن فارسی ترجمه می‌شود
    (شناسه و کد لاتین دست نمی‌خورد)؛ عبارت ترکیبی «الف — ب»، «الف · ب» یا «الف، ب»
    تکه‌تکه ترجمه می‌شود و متن بی‌معادل همان فارسی می‌ماند (هرگز خالی نمی‌شود).
    متن ساخت‌یافته برنامه («الف؛ ب»، «کلید=مقدار»، «کد: متن»، «متن (۲ روز)») هم تکه‌تکه
    ترجمه می‌شود، ولی فقط وقتی دست‌کم یک تکه معادل دارد."""
    if text is None or (isinstance(text, float) and text != text):
        return ""
    t = str(text).strip()
    if lang != EN or not is_persian(t):
        return t
    out = _fa_to_en(t)
    if out:
        return out
    for sep, join in ((" — ", " — "), (" · ", " · "), ("، ", ", ")):
        if sep in t:
            return join.join(phrase(p, lang) for p in t.split(sep))
    return _structured_en(t) or t


def label(col, lang: str = FA) -> str:
    """عنوان نمایشی یک ستون در زبان خواسته‌شده (بدون استثنا)."""
    s = str(col)
    if lang == EN:
        if is_persian(s):
            return _fa_to_en(s) or s
        if _KEY_RE.match(s) and ("_" in s or s.isupper()):
            # برچسب فارسی کاتالوگ اگر ترجمه دارد، خواناتر از شکستن کلید است
            disp = _DISPLAY.get(s, "")
            if is_persian(disp):
                n = _norm(disp)
                if n in _GLOSS:
                    return _GLOSS[n]
            return humanize_key(s)
        return s
    # فارسی
    if s in _DISPLAY and is_persian(_DISPLAY[s]):
        return _fa_tail(_DISPLAY[s])
    if is_persian(s):
        return _fa_tail(s)
    back = _GLOSS_REV.get(s.lower())
    if back and is_persian(back):
        return back
    if _KEY_RE.match(s) and ("_" in s or s.isupper()):
        return fa_from_key(s)
    if s in _DISPLAY:
        back = _GLOSS_REV.get(_DISPLAY[s].lower())
        if back:
            return back
    return s


def _fa_tail(text: str) -> str:
    """«برچسب · KEY» ← «برچسب · عنوان فارسی KEY» تا عنوان یک‌دست فارسی بماند."""
    if " · " in text:
        head, tail = text.rsplit(" · ", 1)
        if _KEY_RE.match(tail) and not is_persian(tail):
            return f"{head} · {fa_from_key(tail)}"
    return text


def untranslated(cols: Iterable, lang: str = EN) -> List[str]:
    """ستون‌هایی که در زبان مقصد هنوز عنوان یک‌دست ندارند."""
    out = []
    for c in cols:
        lab = label(c, lang)
        if lang == EN and is_persian(lab):
            out.append(str(c))
    return out


def rename_map(cols: Iterable, lang: str) -> Dict:
    """{ستون: عنوان یکتا}؛ عنوان تکراری با شماره یکتا می‌شود."""
    out: Dict = {}
    used: Dict[str, int] = {}
    for c in cols:
        name = label(c, lang)
        if name in used:
            used[name] += 1
            name = f"{name} ({used[name]})"
        used.setdefault(name, 1)
        out[c] = name
    return out


def localize_frame(df, lang: str):
    """نسخه‌ای از df با عنوان‌های ستونِ یک‌زبان (df اصلی دست نمی‌خورد)."""
    try:
        cols = list(df.columns)
    except Exception:
        return df, {}
    mp = rename_map(cols, lang)
    if all(mp[c] == c for c in cols):
        return df, {}
    return df.rename(columns=mp), mp

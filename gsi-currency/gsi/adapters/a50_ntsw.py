# -*- coding: utf-8 -*-
"""NTSW — تعهدات ارزی و تخصیص ارز.

هدرهای واقعی
────────────
Release Commitment (۱۱ ستون):
    ردیف | کد ثبت سفارش | شماره ردیف تعهد | شعبه | ارز | تعهد اولیه |
    مانده تعهد | تاریخ ایجاد تعهد | مهلت رفع تعهد | وضعیت رفع تعهد | شرکت

Allocation (۱۵ ستون):
    ردیف | کد ثبت سفارش | ردیف درخواست | وضعیت | فرآیند فعلی | مبلغ درخواست |
    ارز درخواست | تاریخ ایجاد درخواست | تاریخ تخصیص | محل تامین ارز |
    نرخ ارز | نوع درخواست | شعبه | تاریخ تایید | شرکت

⚠️ دو اصلاح بیزینسی حیاتی
─────────────────────────
۱ **تعهدها باید جمع شوند.** یک «کد ثبت سفارش» چند «شماره ردیف تعهد» دارد.
  نسخه قبل با drop_duplicates فقط یک ردیف را نگه می‌داشت و بقیه مانده تعهد
  را دور می‌ریخت. حالا: جمع تعهد اولیه و مانده، زودترین مهلت، و «رفع نشده»
  اگر حتی یک ردیف باز باشد.

۲ **از تخصیص باید آخرین وضعیت گرفته شود.** یک کد ثبت سفارش چند درخواست
  تخصیص دارد (نمونه واقعی: 97687754 دو بار). ملاک، آخرین درخواست بر اساس
  «تاریخ ایجاد درخواست» و سپس «تاریخ تایید» است، نه ردیف اول فایل.

۳ **درخواست رد یا باطل‌شده هیچ‌وقت ارز یا مبلغ تخصیص را تعیین نمی‌کند** (گزارش
  مالک، ۱۴۰۵/۰۷/۰۶). یک ثبت سفارش یورویی سه بار درخواست داشت: یوان (باطل)،
  یورو (رد) و دلار (تخصیص‌یافته). تا 29.15.13 «باطل» در فهرست رد نبود و «اتمام»
  در «فرآیند فعلی»، که هر درخواست بسته‌شده‌ای دارد، تخصیص شمرده می‌شد؛ پس
  درخواست باطل «تخصیص‌یافته» می‌شد. ارز تخصیص فقط از درخواست تخصیص‌یافته می‌آید و
  ارز ثبت سفارش اصلاً از تخصیص نمی‌آید (از ایمپورت لایسنس و IL Append).
"""
from __future__ import annotations

__contract__ = 3

from typing import Any, Dict, List

import pandas as pd

from ..core.jalali import CalendarEngine
from ..core.text import clean_key, clean_order_ref, is_empty_val, normalize_persian_text, num_safe
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import KEY_ORDER, KEY_REG, KEY_REG_FILE, SourceAdapter, register

#: وضعیت‌هایی که یعنی تخصیص واقعاً انجام شده. «اتمام» اینجا نیست: «فرآیند فعلی»
#: هر درخواست بسته‌شده، از جمله رد و باطل‌شده، «اتمام» است و شاهد تخصیص نیست.
_ALLOCATED_STATES = ("تخصیص یافته", "تخصیص داده شد", "تخصیص شده", "تامین شده", "پذیرفته شده",
                     "تایید", "تأیید")
#: رد یا باطل: چنین درخواستی نه ارز تخصیص را تعیین می‌کند نه در مبلغ باز یا تخصیص جمع می‌شود
_REJECTED_STATES = ("پذیرفته نشده", "رد شده", "ابطال", "باطل", "لغو", "انصراف", "منصرف", "منقضی")
#: هنوز در جریان؛ «منتظر تایید» تخصیص نیست، هرچند «تایید» در آن هست. «آماده برای تخصیص»
#: درخواستی است که در صف تخصیص نشسته؛ «فرآیند فعلی»ش در داده واقعی «اتمام» است.
_WAITING_STATES = ("منتظر", "در انتظار", "در صف", "در حال", "بررسی", "ثبت اولیه", "پیش نویس",
                   "آماده")
#: گردش کار بسته شد؛ فقط وقتی وضعیت خالی یا ناشناخته است «بسته‌شده بدون شاهد تخصیص» می‌شود
_FINISHED_PROCESS = ("اتمام", "خاتمه", "پایان")
_UNRESOLVED = ("رفع تعهد نشده", "رفع نشده", "باز")

#: برچسب فارسی نتیجه هر درخواست برای گزارش
REQUEST_STATE_FA = {"ALLOCATED": "تخصیص‌یافته", "OPEN": "باز / در جریان", "REJECTED": "رد یا باطل‌شده",
                    "CLOSED": "بسته‌شده بدون شاهد تخصیص", "AMBIGUOUS": "وضعیت متعارض"}


def _has(text: str, words) -> bool:
    return any(normalize_persian_text(w) in text for w in words)


def _sort_key(v) -> str:
    """تاریخ شمسی به‌صورت رشته‌ای مرتب‌شدنی (1405/06/10 → 14050610)."""
    d = CalendarEngine.parse(v)
    return d.isoformat() if d else ""


def _row_no(v) -> int:
    """«ردیف درخواست» ترتیب درخواست‌های یک ثبت سفارش است؛ وقتی تاریخ برابر یا
    ناخوانا است، ترتیب را همین شماره تعیین می‌کند، نه جای ردیف در فایل."""
    k = clean_key(v)
    return int(k) if k.isdigit() else -1


def _currency_code():
    """متن ارز → کد ISO شناخته‌شده، وگرنه «». «نامشخص» یا «حواله» ارز نیست و دو متن
    ناشناخته هم یک ارز نیستند؛ هویت ارز در جمع و مقایسه فقط از همین کد می‌آید."""
    from ..finance.registration import currency_coder
    return currency_coder()


def _currency_set(values) -> List[str]:
    code = _currency_code()
    return sorted({c for c in (code(v) for v in values) if c})


def request_state(status: Any, process: Any = "", alloc_date: Any = "") -> str:
    """نتیجه یک درخواست تخصیص: ALLOCATED، OPEN، REJECTED یا CLOSED.

    ترتیب مهم است: رد و باطل پیش از هر چیز (درخواست باطل‌شده تاریخ تخصیص هم
    می‌تواند داشته باشد)؛ وضعیت در جریان («منتظر بررسی بانک»، «آماده برای تخصیص») پیش
    از تاریخ تخصیص و پیش از «تایید»؛ و «اتمام» فرآیند به‌تنهایی تخصیص نیست، فقط وقتی
    وضعیت خالی یا ناشناخته است «بسته‌شده بدون شاهد تخصیص» است.
    """
    status = normalize_persian_text(status)
    proc = normalize_persian_text(process)
    text = f"{status} {proc}"
    if _has(text, _REJECTED_STATES):
        return "REJECTED"
    if _has(status, ("نشده", "عدم", "not approved")):
        return "OPEN"
    if _has(status, _WAITING_STATES):
        return "OPEN"
    if CalendarEngine.parse(alloc_date):
        return "ALLOCATED"
    if _has(status, _ALLOCATED_STATES):
        return "ALLOCATED"
    if _has(proc, _WAITING_STATES):
        return "OPEN"
    if _has(proc, _FINISHED_PROCESS):
        return "CLOSED"
    return "OPEN"


@register
class NtswAdapter(SourceAdapter):
    key, prefix = "ntsw", "NTSW"

    COMMITMENT_MAP = {
        "COMMIT_ROW":     ["شماره ردیف تعهد"],
        "BRANCH":         ["شعبه"],
        "CURRENCY":       ["ارز"],
        "INITIAL_COMMIT": ["تعهد اولیه"],
        "BALANCE":        ["مانده تعهد"],
        "COMMIT_DATE":    ["تاریخ ایجاد تعهد"],
        "DEADLINE":       ["مهلت رفع تعهد"],
        "RELEASE_STATUS": ["وضعیت رفع تعهد"],
        "COMPANY":        ["شرکت"],
    }

    ALLOCATION_MAP = {
        "REQ_ROW":        ["ردیف درخواست"],
        "ALLOC_STATUS":   ["وضعیت"],
        "ALLOC_PROCESS":  ["فرآیند فعلی"],
        "REQ_AMOUNT":     ["مبلغ درخواست"],
        "REQ_CURRENCY":   ["ارز درخواست"],
        "REQ_DATE":       ["تاریخ ایجاد درخواست"],
        "ALLOC_DATE":     ["تاریخ تخصیص"],
        "FX_SOURCE":      ["محل تامین ارز"],
        "FX_RATE_TYPE":   ["نرخ ارز"],
        "FX_RATE_NUMERIC":["نرخ ارز"],
        "REQ_TYPE":       ["نوع درخواست"],
        "ALLOC_BRANCH":   ["شعبه"],
        "APPROVE_DATE":   ["تاریخ تایید"],
        "QUEUE_RANK":     ["رتبه در صف", "اولویت صف", "ردیف صف", "Queue Rank", "Queue Position"],
        "COMPANY":        ["شرکت"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        from ..warehouse.numeric import number
        num_safe = number
        out: Dict[str, pd.DataFrame] = {}
        rb = get_rulebook()
        p = self.p

        # Import Licence is the registration-file hub. It must remain distinct
        # from KEY_REG; both keys may coexist in the same evidence row.
        df_l = sheets.get("Import License")
        if df_l is None or df_l.empty:
            df_l = sheets.get("Import Licence")
        if df_l is not None and not df_l.empty:
            from ..core.columns import find_col
            lic = df_l.copy()
            file_col = find_col(df_l, ["شماره پرونده ثبت سفارش", "شماره پرونده", "پرونده ثبت سفارش"],
                                exclude=["تاریخ", "وضعیت", "شرح"])
            reg_col = find_col(df_l, ["کد ثبت سفارش", "شماره ثبت سفارش", "ثبت سفارش"],
                               exclude=["پرونده", "تاریخ", "ارزش", "شرح"])
            order_col = find_col(df_l, ["شماره سفارش", "سفارش", "Order No", "Order Number"],
                                 exclude=["تاریخ", "شرح", "ثبت", "پرونده", "registration"])
            lic[KEY_REG_FILE] = lic[file_col].map(clean_key) if file_col is not None else ""
            lic[KEY_REG] = lic[reg_col].map(clean_key) if reg_col is not None else ""
            lic[self.p("KEY_REG")] = lic[KEY_REG]
            lic[KEY_ORDER] = lic[order_col].map(clean_order_ref) if order_col is not None else ""  # R8: یک قاعده برای همه سورس‌ها
            status_col = find_col(df_l, ["وضعیت", "وضعیت پرونده", "وضعیت ثبت سفارش", "Status"],
                                  exclude=["تاریخ"])
            lic["NTSW_LICENSE_STATUS"] = lic[status_col] if status_col is not None else ""
            lic["NTSW_STATUS"] = lic["NTSW_LICENSE_STATUS"]
            issue_col = find_col(df_l, ["تاریخ صدور ثبت سفارش"], exclude=["اعتبار"])
            lic["NTSW_REG_DATE"] = lic[issue_col] if issue_col is not None else ""
            # ارزش و ارز ثبت سفارش از خود ایمپورت لایسنس (مرجع رسمی NTSW). تا 29.15.13
            # خوانده نمی‌شد و ارز ثبت سفارش از منابع دیگر (حتی تعهد) برداشته می‌شد.
            # تطبیق فقط دقیق است: «نوع عملیات ارزی» نباید جای «نوع ارز» بنشیند.
            from ..core.columns import exact_col
            value_col = exact_col(df_l, ["مبلغ کل پیش فاکتور", "مبلغ کل پروفرم", "ارزش ثبت سفارش"])
            ccy_col = exact_col(df_l, ["نوع ارز", "ارز"])
            lic["NTSW_LICENSE_VALUE"] = (df_l[value_col].map(num_safe) if value_col is not None
                                         else pd.Series(float("nan"), index=df_l.index))
            lic["NTSW_LICENSE_CURRENCY"] = (df_l[ccy_col].map(rb.normalize_currency) if ccy_col is not None
                                            else pd.Series("", index=df_l.index))
            op_col = exact_col(df_l, ["نوع عملیات ارزی"])
            lic["NTSW_LICENSE_FX_OPERATION"] = df_l[op_col] if op_col is not None else ""
            pi_col = exact_col(df_l, ["شماره پیش فاکتور", "شماره پروفرم"])
            lic["NTSW_PROFORMA_NO"] = df_l[pi_col] if pi_col is not None else ""
            # Repeated file IDs can be revisions or separate REG associations.
            # Retain all rows and statuses; never choose an approved-looking row.
            lic["NTSW_LICENSE_STATUS_CONFLICT"] = False
            keyed = lic[KEY_REG_FILE].ne("")
            lic.loc[keyed, "NTSW_LICENSE_STATUS_CONFLICT"] = (
                lic.loc[keyed].groupby(KEY_REG_FILE)["NTSW_LICENSE_STATUS"]
                .transform(lambda s: s.map(normalize_persian_text).nunique() > 1))
            lic["NTSW_IMPORT_LICENSE_SOURCE_SHEET"] = str(getattr(df_l, "name", "") or "Import Licence")
            out["import_license"] = lic
            log.info(f"   ✅ [ntsw] Import Licence: {len(lic)} ردیف | "
                     f"{int(lic[KEY_REG_FILE].astype(str).str.strip().ne('').sum())} پرونده | "
                     f"{int(lic[KEY_REG].astype(str).str.strip().ne('').sum())} ثبت سفارش")

        df_c = sheets.get("Release Commitment")
        if df_c is not None and not df_c.empty:
            c = self.std(df_c, self.COMMITMENT_MAP, exclude=["توضیح"])
            c[KEY_REG] = self._reg(df_c)
            c[p("KEY_REG")] = c[KEY_REG]
            c[p("CURRENCY")] = c[p("CURRENCY")].map(rb.normalize_currency)
            for f in ("INITIAL_COMMIT", "BALANCE"):
                c[p(f)] = c[p(f)].map(num_safe)
            out["commitment_rows"] = c.copy()
            invalid = c[[p('INITIAL_COMMIT'),p('BALANCE')]].isna().any(axis=1)
            # دو ارز برای یک ثبت سفارش «نامعتبر» نیست؛ دو تعهد است. تا 29.15.13 کل
            # تعهدهای چنین پرونده‌ای قرنطینه می‌شد و مانده‌اش از چرخه حذف می‌شد. حالا
            # هر ارز جدا جمع می‌شود و جمع پرونده برای چند ارز نامعلوم می‌ماند.
            # تعهدی که ارزش کد شناخته‌شده ندارد («نامشخص»، «حواله») هم قرنطینه می‌شود: مبلغ
            # بی‌ارز با هیچ مبلغی جمع نمی‌شود و ردیفش با همان متن در قرنطینه دیده می‌شود.
            invalid |= c[KEY_REG].map(clean_key).eq('') | c[p('CURRENCY')].map(_currency_code()).eq('')
            # A repeated native ID is a snapshot, never another monetary event.
            native_id = p('COMMIT_ROW')
            if native_id in c:
                keyed = c[native_id].map(clean_key).ne('')
                for _, g in c[keyed].groupby([KEY_REG, native_id], dropna=False):
                    if len(g[[p('INITIAL_COMMIT'), p('BALANCE'), p('CURRENCY'),
                              p('RELEASE_STATUS'), p('DEADLINE')]].drop_duplicates()) > 1:
                        invalid.loc[g.index] = True
                # Missing identity cannot distinguish equal independent commitments
                # from repeated snapshots. Retain evidence, exclude uncertain sums.
                no_id = ~keyed
                invalid |= no_id & c.duplicated([KEY_REG, p('CURRENCY')], keep=False)
            out["commitment_quarantine"] = c.loc[invalid].assign(DQ_REASON='INVALID_OR_CONFLICTING_COMMITMENT')
            valid = c.loc[~invalid].copy()
            if native_id in valid:
                keyed = valid[native_id].map(clean_key).ne('')
                valid = pd.concat([valid.loc[keyed].drop_duplicates([KEY_REG,native_id]), valid.loc[~keyed]], ignore_index=True)
            out["commitment"] = self._agg_commitment(valid)
            out["commitment_by_currency"] = self._agg_commitment(valid, by_currency=True)
            log.info(f"   ✅ [ntsw] Release Commitment: {len(c)} ردیف تعهد → "
                     f"{len(out['commitment'])} کد ثبت سفارش")
        else:
            log.warning("   ⚠️ [ntsw] شیت «Release Commitment» یافت نشد.")

        df_a = sheets.get("Allocation")
        if df_a is not None and not df_a.empty:
            a = self.std(df_a, self.ALLOCATION_MAP, exclude=["توضیح"])
            a[KEY_REG] = self._reg(df_a)
            a[p("KEY_REG")] = a[KEY_REG]
            a[p("REQ_AMOUNT")] = a[p("REQ_AMOUNT")].map(num_safe)
            a[p("FX_RATE_NUMERIC")] = a[p("FX_RATE_NUMERIC")].map(num_safe)
            a[p("REQ_CURRENCY")] = a[p("REQ_CURRENCY")].map(rb.normalize_currency)
            # V26.20: درخواست تخصیص موجودیت مستقل است. تاریخچه خام به ledger
            # request-level تبدیل می‌شود تا retry/تغییر وضعیت یک درخواست، مبلغ
            # نیاز را چندبار نشمارد. aggregation فقط خلاصه پرونده است.
            request_ledger = self._allocation_request_ledger(a)
            out["allocation_history"] = a.copy()
            ambiguous = request_ledger[p("REQUEST_STATE")].eq("AMBIGUOUS")
            out["allocation_quarantine"] = request_ledger.loc[ambiguous].assign(
                DQ_REASON="CONFLICTING_EQUAL_DATE_REQUEST")
            out["allocation_rows"] = request_ledger.copy()
            out["allocation"] = self._agg_allocation(request_ledger.loc[~ambiguous])
            log.info(f"   ✅ [ntsw] Allocation: {len(a)} درخواست → "
                     f"{len(out['allocation'])} کد ثبت سفارش")
        else:
            log.warning("   ⚠️ [ntsw] شیت «Allocation» یافت نشد.")
        return out

    @staticmethod
    def _reg(df: pd.DataFrame) -> pd.Series:
        from ..core.columns import find_col
        col = find_col(df, ["کد ثبت سفارش", "شماره ثبت سفارش", "ثبت سفارش"],
                       exclude=["تاریخ", "پرونده"])
        return df[col].map(clean_key) if col is not None else ""

    # ═══ تجمیع تعهدها: جمع، نه انتخاب یک ردیف ═══
    def _agg_commitment(self, c: pd.DataFrame, by_currency: bool = False) -> pd.DataFrame:
        """یک ردیف برای هر ثبت سفارش (یا هر ثبت سفارش × ارز با ``by_currency``).

        مبلغ‌ها فقط در یک ارز جمع می‌شوند. ثبت سفارشی که تعهد در دو ارز دارد در
        جمع پرونده ارز و مبلغ نامعلوم می‌گیرد (``COMMIT_CURRENCIES`` ارزها را نشان
        می‌دهد) و مبلغ هر ارز در فریم ``commitment_by_currency`` است.
        """
        p = self.p
        c = c[c[KEY_REG].astype(str).str.strip() != ""]
        if c.empty:
            return c
        keys = [KEY_REG, p("CURRENCY")] if by_currency else [KEY_REG]
        rows: List[Dict[str, Any]] = []
        for key, g in c.groupby(keys, sort=False):
            reg = key[0] if isinstance(key, tuple) else key
            native_id = p("COMMIT_ROW")
            if native_id in g:
                has_id = g[native_id].map(clean_key).ne("")
                g = pd.concat([g.loc[has_id].drop_duplicates([native_id]), g.loc[~has_id]], ignore_index=True)
            statuses = [normalize_persian_text(s) for s in g[p("RELEASE_STATUS")]]
            open_mask = [any(u in s for u in _UNRESOLVED) for s in statuses]
            unresolved = [s for s, is_open in zip(statuses, open_mask) if is_open]
            # مهلت و تاریخ ایجاد پرونده از تعهدهای هنوز باز؛ تعهد رفع‌شده سه سال پیش نباید مهلت
            # تعهد باز امسال را «معوق» کند یا جریمه مانده امروز را از آن تاریخ بشمارد.
            live = g.loc[open_mask] if any(open_mask) else g
            deadlines = [d for d in (CalendarEngine.parse(x) for x in live[p("DEADLINE")]) if d]
            created = [d for d in (CalendarEngine.parse(x) for x in live[p("COMMIT_DATE")]) if d]
            created_all = [d for d in (CalendarEngine.parse(x) for x in g[p("COMMIT_DATE")]) if d]
            currencies = _currency_set(g[p("CURRENCY")])
            single = len(currencies) == 1
            rows.append({
                KEY_REG: reg,
                p("COMMIT_ROWS"): int(len(g)),
                p("INITIAL_COMMIT"): float(g[p("INITIAL_COMMIT")].sum()) if single else float("nan"),
                p("BALANCE"): float(g[p("BALANCE")].sum()) if single else float("nan"),
                p("OPEN_ROWS"): int(len(unresolved)),
                p("RELEASE_STATUS"): ("رفع تعهد نشده" if unresolved else
                                      (statuses[0] if statuses else "")),
                p("DEADLINE"): min(deadlines).isoformat() if deadlines else "",
                p("COMMIT_DATE"): min(created).isoformat() if created else "",
                p("LAST_COMMIT_DATE"): max(created_all).isoformat() if created_all else "",
                p("CURRENCY"): currencies[0] if single else "",
                p("COMMIT_CURRENCIES"): "، ".join(currencies),
                p("COMMIT_MULTI_CURRENCY"): len(currencies) > 1,
                p("BRANCH"): next((x for x in g[p("BRANCH")] if not is_empty_val(x)), ""),
                p("COMPANY"): next((x for x in g[p("COMPANY")] if not is_empty_val(x)), ""),
            })
        return pd.DataFrame(rows)

    # ═══ تخصیص V26.20: ledger درخواست‌ها، نه جمع تاریخچه ═══
    def _allocation_request_ledger(self, a: pd.DataFrame) -> pd.DataFrame:
        """هر «درخواست تخصیص» را یک بار نگه می‌دارد و آخرین وضعیتش را ثبت می‌کند.

        فایل NTSW ممکن است یک درخواست را در چند snapshot/status تکرار کند. جمع
        ساده همه ردیف‌ها، مبلغ درخواست را متورم می‌کند. کلید اصلی ``REQ_ROW``
        است؛ اگر export آن را نداشته باشد، کلید ترکیبی محافظه‌کارانه می‌سازیم.
        """
        p = self.p
        a = a[a[KEY_REG].astype(str).str.strip() != ""].copy()
        if a.empty:
            return a

        a["_ord"] = [f"{_sort_key(r)}|{_sort_key(v)}|{_sort_key(d)}"
                     for r, v, d in zip(a[p("REQ_DATE")], a[p("APPROVE_DATE")],
                                        a[p("ALLOC_DATE")])]

        def request_key(row: pd.Series) -> str:
            rr = clean_key(row.get(p("REQ_ROW"), ""))
            if rr:
                return f"{clean_key(row.get(KEY_REG,''))}|ROW:{rr}"
            # fallback: شناسه مصنوعی فقط برای dedupe یک export، نه شناسه حقوقی
            return "|".join([
                clean_key(row.get(KEY_REG, "")),
                _sort_key(row.get(p("REQ_DATE"), "")),
                str(row.get(p("REQ_AMOUNT"), "") or ""),
                clean_key(row.get(p("REQ_CURRENCY"), "")),
                normalize_persian_text(row.get(p("REQ_TYPE"), "")),
            ])

        a[p("REQUEST_KEY")] = a.apply(request_key, axis=1)
        # Equal timestamps do not order contradictory statuses. Keep all tied
        # evidence and explicitly quarantine it instead of using workbook order.
        latest = a.groupby(p("REQUEST_KEY"))["_ord"].transform("max")
        tied = a.loc[a["_ord"].eq(latest)]
        signature = [p(x) for x in ("ALLOC_STATUS", "ALLOC_PROCESS", "REQ_AMOUNT", "REQ_CURRENCY")]
        conflict_keys = {k for k, g in tied.groupby(p("REQUEST_KEY"))
                         if len(g[signature].drop_duplicates()) > 1}
        conflicts = tied.loc[tied[p("REQUEST_KEY")].isin(conflict_keys)].copy()
        a = a.loc[~a[p("REQUEST_KEY")].isin(conflict_keys)]
        # آخرین snapshot هر request برنده است؛ مبلغ فقط همان یک بار وارد ledger می‌شود.
        a = (a.sort_values("_ord", kind="mergesort")
              .drop_duplicates(subset=[p("REQUEST_KEY")], keep="last")
              .copy())
        a["_rowno"] = a[p("REQ_ROW")].map(_row_no) if p("REQ_ROW") in a else -1
        a = a.sort_values([KEY_REG, "_ord", "_rowno"], kind="mergesort").drop(columns="_rowno")

        a[p("REQUEST_STATE")] = a.apply(lambda row: request_state(
            row.get(p("ALLOC_STATUS"), ""), row.get(p("ALLOC_PROCESS"), ""), row.get(p("ALLOC_DATE"), "")), axis=1)
        unknown = a.loc[a[p("REQUEST_STATE")].eq("CLOSED"), p("ALLOC_STATUS")].map(normalize_persian_text)
        if len(unknown):
            log.warning("   ⚠️ [ntsw] درخواست تخصیص با «اتمام» ولی وضعیت ناشناخته، تخصیص شمرده نشد: "
                        + "، ".join(sorted({x or "خالی" for x in unknown})[:10]))
        if not conflicts.empty:
            conflicts[p("REQUEST_STATE")] = "AMBIGUOUS"
            a = pd.concat([a, conflicts], ignore_index=True)
        a[p("REQUEST_STATE_FA")] = a[p("REQUEST_STATE")].map(REQUEST_STATE_FA).fillna("")
        a[p("QUEUE_ENTER_DATE")] = a[p("REQ_DATE")].where(
            a[p("REQUEST_STATE")].eq("OPEN"), "")
        # ``QUEUE_RANK`` ممکن است در export رسمی موجود نباشد. خالی باید خالی بماند.
        a[p("QUEUE_RANK")] = a[p("QUEUE_RANK")].where(
            a[p("REQUEST_STATE")].eq("OPEN"), "")
        return a.drop(columns=["_ord"], errors="ignore")

    def _agg_allocation(self, a: pd.DataFrame) -> pd.DataFrame:
        """خلاصه پرونده از request ledger، با تفکیک open/allocated/rejected.

        هر مبلغ فقط به ارز خودش جمع می‌شود: ارز تخصیص فقط از درخواست‌های
        تخصیص‌یافته، ارز صف فقط از درخواست‌های باز. درخواست رد یا باطل‌شده فقط
        در شمارش و فهرست ارزهای ردشده دیده می‌شود.
        """
        p = self.p
        a = a[a[KEY_REG].astype(str).str.strip() != ""].copy()
        if a.empty:
            return a

        # برای تعیین «آخرین وضعیت نمایشی» دوباره ترتیب زمانی می‌سازیم؛ تساوی را
        # «ردیف درخواست» می‌شکند، نه جای ردیف در فایل.
        a["_ord"] = [f"{_sort_key(r)}|{_sort_key(v)}|{_sort_key(d)}"
                     for r, v, d in zip(a[p("REQ_DATE")], a[p("APPROVE_DATE")],
                                        a[p("ALLOC_DATE")])]
        a["_rowno"] = a[p("REQ_ROW")].map(_row_no) if p("REQ_ROW") in a else -1
        rows: List[Dict[str, Any]] = []
        for reg, g in a.groupby(KEY_REG, sort=False):
            g = g.sort_values(["_ord", "_rowno"], kind="mergesort")
            last = g.iloc[-1]
            state = g[p("REQUEST_STATE")]
            allocated = g[state.eq("ALLOCATED")]
            open_q = g[state.eq("OPEN")]
            rejected = g[state.eq("REJECTED")]
            closed = g[state.eq("CLOSED")]
            # وضعیت و فرایند نمایشی پرونده از آخرین درخواست زنده (تخصیص‌یافته یا باز).
            # درخواست رد یا باطل‌شده فقط وقتی نشان داده می‌شود که درخواست زنده‌ای نیست؛
            # وضعیت خام آخرین درخواست جدا در LAST_REQUEST_STATUS می‌ماند.
            live_rows = g[state.isin(["ALLOCATED", "OPEN"])]
            shown = live_rows.iloc[-1] if not live_rows.empty else last
            alloc_dates = [d for d in (CalendarEngine.parse(x) for x in allocated[p("ALLOC_DATE")]) if d]
            open_dates = [d for d in (CalendarEngine.parse(x) for x in open_q[p("REQ_DATE")]) if d]

            def currency(frame: pd.DataFrame) -> str:
                codes = _currency_set(frame[p("REQ_CURRENCY")])
                return codes[0] if len(codes) == 1 else ""

            def amount(frame: pd.DataFrame) -> float:
                """جمع به ارز خود همین دسته؛ چند ارز یا مبلغ نامعلوم ⇒ نامعلوم (نه صفر)."""
                if frame.empty:
                    return 0.0
                codes = frame[p("REQ_CURRENCY")].map(_currency_code())
                values = pd.to_numeric(frame[p("REQ_AMOUNT")], errors="coerce")
                if codes.eq("").any() or codes.nunique() != 1 or values.isna().any():
                    return float("nan")  # Native request ledger retains each currency and amount.
                return float(values.sum())

            alloc_amt = amount(allocated)
            open_amt = amount(open_q)
            rejected_amt = amount(rejected)
            gross_amt = amount(g)
            alloc_ccy, open_ccy = currency(allocated), currency(open_q)
            # مبلغ باز + تخصیص‌یافته فقط وقتی هر دو یک ارزند جمع می‌شود
            if allocated.empty:
                live_amt, live_ccy = open_amt, open_ccy
            elif open_q.empty:
                live_amt, live_ccy = alloc_amt, alloc_ccy
            elif alloc_ccy and alloc_ccy == open_ccy:
                live_amt, live_ccy = alloc_amt + open_amt, alloc_ccy
            else:
                live_amt, live_ccy = float("nan"), ""

            if len(open_q) and len(allocated):
                qstate = "PARTIAL_ALLOCATED"
            elif len(open_q):
                qstate = "IN_QUEUE"
            elif len(allocated):
                qstate = "ALLOCATED"
            elif len(closed):
                qstate = "CLOSED"
            elif len(rejected):
                qstate = "REJECTED"
            else:
                qstate = "NO_REQUEST"

            # آخرین رتبه معتبر میان درخواست‌های باز؛ هرگز 0 جعل نمی‌شود.
            ranks = [x for x in open_q[p("QUEUE_RANK")].tolist()
                     if not is_empty_val(x, treat_zero_as_empty=False)]
            queue_rank = ranks[-1] if ranks else ""
            # نرخ، محل تأمین و نوع درخواست از آخرین درخواست تخصیص‌یافته (وگرنه باز)؛
            # درخواست رد یا باطل‌شده منبع نرخ یا ارز نیست.
            live = allocated if not allocated.empty else open_q
            src = live.iloc[-1] if not live.empty else None

            def pick(field: str):
                return src[p(field)] if src is not None else ""

            rate = pick("FX_RATE_NUMERIC")
            rows.append({
                KEY_REG: reg,
                p("ALLOC_REQUESTS"): int(len(g)),
                p("ALLOCATED_REQUESTS"): int(len(allocated)),
                p("OPEN_REQUESTS"): int(len(open_q)),
                p("REJECTED_REQUESTS"): int(len(rejected)),
                p("CLOSED_REQUESTS"): int(len(closed)),
                p("QUEUE_STATE"): qstate,
                p("ALLOC_STATUS"): shown[p("ALLOC_STATUS")],
                p("ALLOC_PROCESS"): shown[p("ALLOC_PROCESS")],
                p("LAST_REQUEST_STATUS"): last[p("ALLOC_STATUS")],
                p("ALLOC_DATE"): max(alloc_dates).isoformat() if alloc_dates else "",
                p("QUEUE_ENTER_DATE"): min(open_dates).isoformat() if open_dates else "",
                p("QUEUE_RANK"): queue_rank,
                p("REQ_DATE"): last[p("REQ_DATE")],
                p("APPROVE_DATE"): last[p("APPROVE_DATE")],
                # gross صرفاً تاریخچه درخواست است؛ برای نیاز/تخصیص واقعی استفاده نشود.
                p("REQUESTED_GROSS"): gross_amt,
                p("ALLOCATED_AMOUNT"): alloc_amt,
                p("ALLOCATED_CURRENCY"): alloc_ccy,
                p("ALLOCATED_CURRENCIES"): "، ".join(_currency_set(allocated[p("REQ_CURRENCY")])),
                p("OPEN_QUEUE_AMOUNT"): open_amt,
                p("OPEN_CURRENCY"): open_ccy,
                p("REJECTED_AMOUNT"): rejected_amt,
                p("REJECTED_CURRENCIES"): "، ".join(_currency_set(rejected[p("REQ_CURRENCY")])),
                # سازگاری عقب‌رو: REQ_AMOUNT = مبلغ باز + تخصیص‌یافته، نه retry history
                p("REQ_AMOUNT"): live_amt,
                # ارز درخواست زنده (باز، وگرنه تخصیص‌یافته)؛ هرگز از درخواست رد یا باطل‌شده
                p("REQ_CURRENCY"): live_ccy,
                p("FX_SOURCE"): pick("FX_SOURCE"),
                p("FX_RATE_TYPE"): pick("FX_RATE_TYPE"),
                p("FX_RATE_NUMERIC"): (float(rate) if src is not None and not is_empty_val(
                    rate, treat_zero_as_empty=False) else None),
                p("REQ_TYPE"): pick("REQ_TYPE") if src is not None else last[p("REQ_TYPE")],
                p("ALLOC_BRANCH"): pick("ALLOC_BRANCH") if src is not None else last[p("ALLOC_BRANCH")],
                p("ALLOCATED"): bool(len(allocated)),
                p("ALLOC_REJECTED"): bool(len(rejected) and not len(allocated) and not len(open_q)),
            })
        return pd.DataFrame(rows)

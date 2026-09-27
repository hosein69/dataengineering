# -*- coding: utf-8 -*-
"""سورس Commercial Expert Data (فایل کارشناسان) — دقیقاً بر اساس ۳۵ ستون واقعی.

## قرارداد

:data:`EXPERT_HEADERS` تنها منبع حقیقت است: ۳۵ ستون، به همان ترتیب و همان متن
فایل کارشناسان (تأیید مالک ۱۴۰۵/۰۷/۰۵). هیچ ستون دیگری از این فایل خوانده
نمی‌شود و هیچ ستون خیالی ساخته نمی‌شود.

* تطبیق هدر **دقیق** است: فاصله/شکست خط/حروف بزرگ‌وکوچک نادیده گرفته می‌شود و
  هدر کامل، نام پیش از پرانتز یا متن داخل پرانتز پذیرفته می‌شود («Part No.» و
  «Our Reference» همان هدرهای رسمی‌اند) — همیشه نام کامل. تطبیق تقریبی/زیررشته‌ای
  ممنوع است: «Part No.» هرگز «Manufacturer Part Number» را نمی‌گیرد.
* ستون غایب: هشدار صریح و مقدار خالی (هرگز صفر). ستون اضافه: نادیده و گزارش.
* مقدار خالی عدد، ``NaN`` می‌ماند — Unknown با Zero یکی نیست.

## وضعیت پارت (تصمیم مالک ۱۴۰۵/۰۷/۰۵)

«Quantity In Part» هر ردیف در یکی از چهار وضعیت است و وضعیت از ستون
«Order Status» همان ردیف خوانده می‌شود: نزد سازنده، آماده حمل، در راه، در گمرک
(واژگان در ``rules/status_lexicon.yaml → part_states``). مقدار ناشناخته حدس
زده نمی‌شود: مقدار آن پارت «وضعیت نامشخص» گزارش می‌شود و متن ناشناخته در لاگ
می‌آید تا به واژگان افزوده شود. در وضعیت «در گمرک»، «Customs Cleared Quantity»
از مقدار پارت کم می‌شود (کالای ترخیص‌شده دیگر در گمرک نیست).

## خروجی‌ها

    lines  : هر ردیف فایل (۳۵ ستون + کلیدها + وضعیت و مقدار هر پارت)
    main   : یک ردیف برای هر سفارش × متریال (29.15.11) + ردیف هر متریال بدون
             شماره سفارش؛ مقادیر سطح سفارش تکرار می‌شوند و مقدار چهار وضعیت
             مال همان متریال است
    inventory : همان چهار وضعیت در دانه سفارش × متریال (انبار داده و دفتر متریال)
    order_material_pr_item : رابطه سفارش × متریال × PR × قلم PR

ستون «BL No.» در نمونه‌های واقعی شماره فنی یا پروفرما هم داشت (541339،
2036866948، 603111/1)؛ هر مقدار با ``RuleBook.validate_bl`` سنجیده و مقدار مشکوک
قرنطینه می‌شود تا کلید بارنامه آلوده نشود. «Additional Data» قالب «وضعیت
بازرگانی // وضعیت لجستیک» دارد و با ``status_lexicon`` به مرحله تبدیل می‌شود.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..core.columns import _norm
from ..core.numeric_parse import parse_decimal
from ..core.text import (clean_employee_code, clean_key, clean_order_ref, clean_part_no,
                         is_empty_val, order_ref_base)
from .. import health
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import KEY_MATERIAL, KEY_ORDER, KEY_PR, SharedList, SourceAdapter, register

#: ۳۵ ستون فایل کارشناسان — همان متن و همان ترتیب فایل واقعی.
EXPERT_HEADERS: Tuple[Tuple[str, str], ...] = (
    ("ROW_NO", "Row No."),
    ("ORDER_REF", "Order No.\n(Our Reference)"),
    ("PR_NO", "PR No."),
    ("PR_ITEM", "PR Item"),
    ("MATERIAL", "Material"),
    ("MATERIAL_DESC", "Material Description"),
    ("MATERIAL_SHORT", "Material Short Text"),
    ("MFR_PART_NO", "Manufacturer Part Number"),
    ("PGR", "PGR"),
    ("PR_TOTAL_QTY", "PR Total Quantity"),
    ("UOM", "Unit Of Measure"),
    ("REF_LETTER_NO", "Reference Letter No.\n(شماره نامه اتوماسیونی)"),
    ("DATA_TYPE", "Data type "),
    ("QTY_IN_ORDER", "Quantity In Order"),
    ("MFR_VENDOR_CODE", "Manufacturer Vendor Code "),
    ("MFR_PI_NO", "Manufacturer\nPI Number "),
    ("VENDOR_CODE", "Vendor Code "),
    ("VENDOR_PI_NO", "Vendor\nPI Number "),
    ("PI_QTY", "PI Quantity "),
    ("PI_UNIT_PRICE", "PI Unit Price"),
    ("CURRENCY", "Currency"),
    ("PI_LINE_VALUE", "PI Line Value"),
    ("PI_ADDITIONAL", "PI Additional Costs"),
    ("PO_SENT_DATE", " PO Sent Date\n( با فرمت میلادی PO تاریخ ابلاغ فرم)"),
    ("PART_NO_PARTIAL", "Part No.\n(شماره پارت در حمل پارشیالی)"),
    ("QTY_IN_PART", "Quantity In Part"),
    ("CLEARED_QTY", "Customs Cleared Quantity"),
    ("ORDER_STATUS", "Order Status"),
    ("TRANSPORT_MODE", "Mode of Transport"),
    ("TRANSPORT_NO", "Transport No."),
    ("BL_RAW", "BL No."),
    ("CARRIER", "Carrier Name"),
    ("SCHEDULED_SHIP", "Scheduled Shipment Date"),
    ("ADDITIONAL_DATA", "Additional Data (Note , Brand etc.)"),
    ("EMP_CODE", "Employee Code"),
)

#: وضعیت‌های پارت: (کد، عنوان، ستون مقدار). ترتیب همان ترتیب مسیر کالاست.
PART_STATES: Tuple[Tuple[str, str, str], ...] = (
    ("AT_SUPPLIER", "نزد سازنده", "QTY_AT_SUPPLIER"),
    ("READY", "آماده حمل", "QTY_READY"),
    ("IN_TRANSIT", "در راه", "QTY_IN_TRANSIT"),
    ("IN_CUSTOMS", "در گمرک", "QTY_IN_CUSTOMS"),
)
#: مقدار پارت‌هایی که Order Status آن‌ها خالی یا ناشناخته است.
STATE_UNKNOWN_QTY = "QTY_STATE_UNKNOWN"


def _base(header: str) -> str:
    """متن پیش از اولین پرانتز: «Part No.\\n(…)» ← «Part No.»."""
    return header.split("(", 1)[0]


def _inner(header: str) -> str:
    """متن داخل پرانتز: «Order No.\\n(Our Reference)» ← «Our Reference»."""
    return header.split("(", 1)[1].rsplit(")", 1)[0] if "(" in header else ""


def _number(value: Any) -> float:
    """عدد یا NaN. خالی و متن غیرعددی هرگز ۰ نمی‌شوند."""
    if is_empty_val(value, treat_zero_as_empty=False):
        return float("nan")
    parsed = parse_decimal(value, strict=False)
    return float(parsed) if parsed is not None else float("nan")


@register
class MoghavematAdapter(SourceAdapter):
    key, prefix = "moghavemat", "MOGH"
    #: Studio/HTML catalog: this source's group holds exactly EXPERT_HEADERS.
    EXACT_HEADER_CONTRACT = True

    #: نام استاندارد → [هدر رسمی]. فقط برای سازگاری؛ قرارداد EXPERT_HEADERS است.
    COLUMN_MAP: Dict[str, List[str]] = {field: [header] for field, header in EXPERT_HEADERS}

    NUMERIC_FIELDS = ["PR_TOTAL_QTY", "QTY_IN_ORDER", "PI_QTY", "PI_UNIT_PRICE",
                      "PI_LINE_VALUE", "PI_ADDITIONAL", "QTY_IN_PART", "CLEARED_QTY"]

    # ═══════════ نگاشت دقیق ۳۵ ستون ═══════════
    def _map_headers(self, df: pd.DataFrame) -> pd.DataFrame:
        """هر ستون رسمی ← همان ستون فایل؛ بدون تطبیق تقریبی."""
        by_norm: Dict[str, List[Any]] = {}
        for col in df.columns:
            by_norm.setdefault(_norm(col), []).append(col)
        cols: Dict[str, pd.Series] = {}
        used: set = set()
        missing: List[str] = []
        for field, header in EXPERT_HEADERS:
            found = None
            # the whole header, the name before its parentheses, or the text
            # inside them — always a whole name, never a substring
            for key in dict.fromkeys((_norm(header), _norm(_base(header)), _norm(_inner(header)))):
                if not key:
                    continue
                hits = by_norm.get(key, [])
                if len(hits) > 1:
                    raise ValueError(f"AMBIGUOUS_EXPERT_HEADER: «{header.strip()}» ← {hits}")
                if hits:
                    found = hits[0]
                    break
            if found is None:
                missing.append(header.strip())
                cols[self.p(field)] = pd.Series("", index=df.index, dtype=object)
                log.warning(f"   ⚠️ [{self.key}] ستون «{' '.join(header.split())}» در فایل کارشناسان "
                            f"نیست — با مقدار خالی پر شد (صفر فرض نمی‌شود).")
            else:
                used.add(found)
                cols[self.p(field)] = df[found].copy()
        extra = [str(c) for c in df.columns if c not in used and _norm(c)]
        if extra:
            log.info(f"   ℹ️ [{self.key}] {len(extra)} ستون خارج از قرارداد ۳۵ ستونی خوانده نشد: "
                     f"{extra[:8]}")
        out = pd.DataFrame(cols, index=df.index)
        out.attrs["source_headers"] = SharedList(str(c) for c in df.columns)
        out.attrs["missing_mappings"] = SharedList(missing)
        out.attrs["ignored_headers"] = SharedList(extra)
        return out

    # ═══════════ تبدیل ═══════════
    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None or df.empty:
            return {}
        rb = get_rulebook()
        p = self.p
        lines = self._map_headers(df)

        # ── کلیدها (ستون‌های منبع دست نمی‌خورند؛ کلید ستون جدا است) ──
        lines[KEY_ORDER] = lines[p("ORDER_REF")].map(clean_order_ref)
        # دانه موجودی Order × Material است. اگر Material خالی بود، شماره فنی
        # سازنده جایگزین می‌شود؛ خالی هرگز به «0» تبدیل نمی‌شود.
        material = lines[p("MATERIAL")].map(clean_part_no)
        mfr = lines[p("MFR_PART_NO")].map(clean_part_no)
        lines[KEY_MATERIAL] = material.where(material.astype(str).str.strip().ne(""), mfr)
        lines[p("ORDER_BASE")] = lines[p("ORDER_REF")].map(order_ref_base)
        lines[p("KEY_EMP")] = lines[p("EMP_CODE")].map(clean_employee_code)
        lines[KEY_PR] = lines[p("PR_NO")].map(clean_key)
        lines[p("KEY_PR")] = lines[KEY_PR]   # نسخه پیشوندی، تا در ادغام حذف نشود

        # ── عددی‌سازی: خالی = NaN ──
        for f in self.NUMERIC_FIELDS:
            lines[p(f)] = lines[p(f)].map(_number).astype("float64")

        # ── ارز ──
        lines[p("CURRENCY")] = lines[p("CURRENCY")].map(rb.normalize_currency)

        # ── وضعیت و مقدار هر پارت (Order Status × Quantity In Part) ──
        self._part_states(lines, rb)

        # ── اعتبارسنجی بارنامه و قرنطینه مقادیر مشکوک ──
        checks = lines[p("BL_RAW")].map(rb.validate_bl)
        valid = [v for v, _ in checks]
        lines[p("BL_VALID")] = valid
        lines[p("BL_NO")] = [str(v).strip().upper() if ok else ""
                             for v, ok in zip(lines[p("BL_RAW")], valid)]
        # مقدار تهی «مشکوک» نیست؛ فقط مقادیر پرشده‌ای که بارنامه نیستند قرنطینه می‌شوند
        lines[p("BL_SUSPECT")] = ["" if (ok or is_empty_val(v)) else str(v).strip()
                                  for v, ok in zip(lines[p("BL_RAW")], valid)]
        lines[p("BL_REJECT_REASON")] = ["" if (ok or is_empty_val(v)) else reason
                                        for v, (ok, reason) in zip(lines[p("BL_RAW")], checks)]
        n_susp = int((lines[p("BL_SUSPECT")].astype(str).str.strip() != "").sum())
        if n_susp:
            log.warning(
                f"   🚧 [moghavemat] {n_susp} مقدار ستون «BL No.» شماره بارنامه معتبر نبود "
                f"(احتمالاً شماره فنی/پروفرما) و به ستون قرنطینه MOGH_BL_SUSPECT منتقل شد.")

        # ── روش حمل ──
        lines[p("TRANSPORT_MODE_CODE")] = lines[p("TRANSPORT_MODE")].map(rb.transport_mode)

        # ── Additional Data → مرحله چرخه عمر ──
        parsed = [rb.parse_status_note(v) for v in lines[p("ADDITIONAL_DATA")]]
        for field in ("COMMERCIAL_NOTE", "LOGISTICS_NOTE", "STAGE", "STAGE_FA",
                      "PROGRESS", "BLOCKING", "TERMINAL", "EXCLUDED_FROM_KPI",
                      "CLEARANCE_HINT", "ALERTS"):
            lines[p(field)] = [x[field] for x in parsed]

        # ── پیشنهاد کد تعرفه ──
        hs = [rb.infer_hs(d) for d in lines[p("MATERIAL_DESC")]]
        lines[p("HS_SUGGESTED")] = [c for c, _ in hs]
        lines[p("HS_KEYWORD")] = [k for _, k in hs]

        dtypes = sorted({str(v).strip() for v in lines[p("DATA_TYPE")] if not is_empty_val(v)})
        if len(dtypes) > 1:
            log.info(f"   🧩 [moghavemat] فایل چندنوعی است — Data type: {dtypes}")
        elif dtypes:
            log.info(f"   🧩 [moghavemat] تک‌نوع — Data type: {dtypes[0]}")

        lines[p("PRESENT")] = True
        inv = self._aggregate_inventory(lines)
        agg = self._aggregate(lines, inv)
        ompi = self._aggregate_order_material_pr_item(lines)
        n_orders = int(agg[KEY_ORDER].astype(str).str.strip().replace("", pd.NA).nunique()) \
            if KEY_ORDER in agg else len(agg)
        log.info(f"   📊 [moghavemat] {len(lines)} قلم در {n_orders} سفارش و {len(agg)} ردیف "
                 f"سفارش×متریال تجمیع شد؛ {len(inv)} موقعیت پارت Order×Material و {len(ompi)} "
                 f"رابطه Order×Material×PR×PR Item ساخته شد.")
        return {"main": agg, "inventory": inv, "order_material_pr_item": ompi, "lines": lines}

    # ═══════════ وضعیت هر پارت ═══════════
    def _part_states(self, lines: pd.DataFrame, rb) -> None:
        """Order Status → وضعیت؛ Quantity In Part → ستون همان وضعیت."""
        p = self.p
        codes = [rb.part_state(v) for v in lines[p("ORDER_STATUS")]]
        lines[p("PART_STATE")] = codes
        lines[p("PART_STATE_FA")] = [rb.part_state_fa(c) for c in codes]
        qty = lines[p("QTY_IN_PART")]
        cleared = lines[p("CLEARED_QTY")]
        in_customs = (qty - cleared.fillna(0.0)).clip(lower=0.0)
        state = pd.Series(codes, index=lines.index)
        for code, _, col in PART_STATES:
            value = in_customs if code == "IN_CUSTOMS" else qty
            lines[p(col)] = value.where(state.eq(code))
        unknown = sorted({str(v).strip() for v, c in zip(lines[p("ORDER_STATUS")], codes)
                          if c == "UNRECOGNIZED"})
        if unknown:
            log.warning(f"   ⚠️ [{self.key}] Order Status ناشناخته (حدس زده نشد؛ مقدار پارت «وضعیت "
                        f"نامشخص» می‌ماند): {unknown[:10]} — در status_lexicon.yaml → part_states "
                        f"اضافه کنید.")
            health.current().find(
                "وضعیت پارت", health.WARN,
                f"{len(unknown)} مقدار Order Status ناشناخته",
                "مقدار این پارت‌ها در هیچ یک از چهار وضعیت شمرده نشد؛ واژه را به "
                "rules/status_lexicon.yaml → part_states اضافه کنید.")

    @staticmethod
    def _uniq_values(s: pd.Series) -> List[str]:
        """مقادیر یکتا و مرتب، بدون خالی — برای حفظ نسب."""
        seen: List[str] = []
        for v in s:
            if is_empty_val(v):
                continue
            t = str(v).strip()
            if t and t not in seen:
                seen.append(t)
        return sorted(seen)

    # ═══════════ موقعیت پارت‌ها در دانه سفارش × متریال ═══════════
    def _part_position(self, g: pd.DataFrame) -> Dict[str, Any]:
        """چهار وضعیت برای یک سفارش × متریال، بدون دوباره‌شماری.

        هر «Part No.» یک بار شمرده می‌شود (ردیف با بیشترین Quantity In Part؛ یک
        پارت ممکن است در چند قلم PR تکرار شده باشد). ردیف‌های بدون Part No. هم
        یک پارت‌اند (بیشترین مقدار) — همان قاعده پیشین حمل پارشیالی.

        * هیچ پارتی مقدار ندارد ← هر چهار وضعیت نامعلوم (خالی).
        * همه پارت‌ها وضعیت معلوم دارند ← وضعیتی که پارتی ندارد صفرِ واقعی است.
        * پارتی با وضعیت نامعلوم ← مقدارش در «وضعیت نامشخص» و صفرها نامعلوم‌اند
          (آن پارت ممکن است در همان وضعیت باشد).
        * یک پارت با دو وضعیت متفاوت ← تعارض ثبت می‌شود.
        """
        p = self.p
        qty = g[p("QTY_IN_PART")]
        part = g[p("PART_NO_PARTIAL")].map(lambda v: "" if is_empty_val(v) else str(v).strip())
        state = g[p("PART_STATE")]
        counted: List[Any] = []
        conflicts: List[str] = []
        for name, idx in part.groupby(part, sort=True).groups.items():
            q = qty.loc[idx]
            if q.notna().any():
                counted.append(q.idxmax())
            states = sorted({s for s in state.loc[idx] if s not in ("", "UNRECOGNIZED")})
            if len(states) > 1:
                label = f"Part {name}" if name else "بدون Part No."
                conflicts.append(f"{label}: " + " | ".join(
                    get_rulebook().part_state_fa(s) for s in states))
        row: Dict[str, Any] = {p(STATE_UNKNOWN_QTY): float("nan"),
                               p("INVENTORY_CONFLICT"): " ؛ ".join(conflicts)}
        for _, _, col in PART_STATES:
            row[p(col)] = float("nan")
        if not counted:
            return row
        sums = {code: 0.0 for code, _, _ in PART_STATES}
        unknown = 0.0
        for i in counted:
            code = state.loc[i]
            if code in sums:
                col = next(c for k, _, c in PART_STATES if k == code)
                sums[code] += float(g.at[i, p(col)])
            else:
                unknown += float(qty.loc[i])
        row[p(STATE_UNKNOWN_QTY)] = unknown
        for code, _, col in PART_STATES:
            value = sums[code]
            row[p(col)] = value if (value > 0 or unknown == 0) else float("nan")
        return row

    def _aggregate_inventory(self, lines: pd.DataFrame) -> pd.DataFrame:
        """چهار وضعیت پارت در دانه سفارش × متریال — شامل متریال بدون سفارش."""
        p = self.p
        out_cols = [KEY_ORDER, KEY_MATERIAL] + [p(c) for _, _, c in PART_STATES] + \
                   [p(STATE_UNKNOWN_QTY), p("INVENTORY_CONFLICT")]
        src = lines[lines[KEY_MATERIAL].astype(str).str.strip().ne("")]
        if src.empty:
            return pd.DataFrame(columns=out_cols)
        rows = []
        for (order, material), g in src.groupby([KEY_ORDER, KEY_MATERIAL], sort=False):
            rows.append({KEY_ORDER: order, KEY_MATERIAL: material, **self._part_position(g)})
        out = pd.DataFrame(rows, columns=out_cols)
        n_conf = int(out[p("INVENTORY_CONFLICT")].astype(str).str.strip().ne("").sum())
        if n_conf:
            log.warning(f"⚠️ [moghavemat] {n_conf} سفارش×متریال پارتی با دو وضعیت متفاوت دارد؛ "
                        f"تعارض در MOGH_INVENTORY_CONFLICT ثبت شد.")
        return out

    def _aggregate_order_material_pr_item(self, lines: pd.DataFrame) -> pd.DataFrame:
        """Bridge evidence at the business relation grain Order×Material×PR×PR Item.

        Supply Position remains Order×Material, but procurement lineage must preserve
        multiple PRs/items for the same order/material. Repeated raw rows are collapsed
        only at this relation grain and retained as evidence_count/source_rows.
        """
        p = self.p
        cols = [KEY_ORDER, KEY_MATERIAL, KEY_PR, p("PR_ITEM"), p("ROW_NO"),
                p("MATERIAL_DESC"), p("MATERIAL_SHORT")]
        have = [c for c in cols if c in lines.columns]
        src = lines[have].copy()
        empty = pd.DataFrame(columns=[KEY_ORDER, KEY_MATERIAL, KEY_PR, p("PR_ITEM"), p("OMPI_KEY"),
                                      p("EVIDENCE_COUNT"), p("SOURCE_ROWS")])
        if src.empty:
            return empty
        for c in (KEY_ORDER, KEY_MATERIAL, KEY_PR):
            if c not in src.columns:
                src[c] = ""
            src[c] = src[c].fillna("").astype(str).str.strip()
        item = p("PR_ITEM")
        if item not in src.columns:
            src[item] = ""

        def _clean_item(v):
            if is_empty_val(v):
                return ""
            t = str(v).strip()
            # Excel often turns integer PR Item 20 into 20.0; preserve business identity.
            try:
                f = float(t)
                if f.is_integer():
                    return str(int(f))
            except Exception:
                pass
            return t
        src[item] = src[item].map(_clean_item)
        src = src[(src[KEY_ORDER] != "") & (src[KEY_MATERIAL] != "") & (src[KEY_PR] != "")].copy()
        if src.empty:
            return empty
        rows = []
        for (order, material, pr, pr_item), g in src.groupby(
                [KEY_ORDER, KEY_MATERIAL, KEY_PR, item], sort=False, dropna=False):
            source_rows = []
            if p("ROW_NO") in g.columns:
                for v in g[p("ROW_NO")].tolist():
                    if is_empty_val(v):
                        continue
                    t = _clean_item(v)
                    if t and t not in source_rows:
                        source_rows.append(t)
            desc = self._uniq_values(g[p("MATERIAL_DESC")]) if p("MATERIAL_DESC") in g.columns else []
            short = self._uniq_values(g[p("MATERIAL_SHORT")]) if p("MATERIAL_SHORT") in g.columns else []
            rows.append({
                KEY_ORDER: order, KEY_MATERIAL: material, KEY_PR: pr, item: pr_item,
                p("OMPI_KEY"): f"{order}|{material}|{pr}|{pr_item or '<BLANK>'}",
                p("EVIDENCE_COUNT"): int(len(g)),
                p("SOURCE_ROWS"): ",".join(source_rows),
                p("MATERIAL_DESC"): "، ".join(desc),
                p("MATERIAL_SHORT"): "، ".join(short),
            })
        return pd.DataFrame(rows)

    # ═══════════ تجمیع سطح سفارش ═══════════
    @staticmethod
    def _first_valid(s: pd.Series) -> Any:
        for v in s:
            if not is_empty_val(v):
                return v
        return ""

    def _order_rows(self, src: pd.DataFrame) -> pd.DataFrame:
        """یک ردیف برای هر سفارش (مقادیر سطح سفارش)."""
        p = self.p
        _uniq = self._uniq_values
        first_valid = self._first_valid
        rows: List[Dict[str, Any]] = []
        for order, g in src.groupby(KEY_ORDER, sort=False):
            top = g.loc[g[p("PROGRESS")].astype(float).idxmax()] if len(g) else g.iloc[0]
            currency = first_valid(g[p("CURRENCY")])
            one_currency = g[p("CURRENCY")].fillna("").nunique(dropna=False) == 1 and str(currency).strip()
            rows.append({
                KEY_ORDER: order,
                p("PRESENT"): True,
                p("ORDER_BASE"): first_valid(g[p("ORDER_BASE")]),
                p("LINE_COUNT"): int(len(g)),
                p("PR_NO"): first_valid(g[p("PR_NO")]),
                p("KEY_PR"): first_valid(g[p("KEY_PR")]),
                p("PR_COUNT"): int(len(_uniq(g[p("KEY_PR")]))),
                p("PRS_ALL"): "، ".join(_uniq(g[p("KEY_PR")])),
                p("PR_ITEMS_ALL"): "، ".join(_uniq(g[p("PR_ITEM")])),
                p("MULTI_PR"): bool(len(_uniq(g[p("KEY_PR")])) > 1),
                p("MATERIAL"): first_valid(g[p("MATERIAL")]),
                p("MATERIAL_DESC"): first_valid(g[p("MATERIAL_DESC")]),
                p("MATERIAL_DESCS_ALL"): " | ".join(_uniq(g[p("MATERIAL_DESC")])),
                p("MATERIAL_DESC_COUNT"): len(_uniq(g[p("MATERIAL_DESC")])),
                p("KEY_MATERIAL_COUNT"): len(_uniq(g[KEY_MATERIAL])),
                p("MFR_PART_NO"): first_valid(g[p("MFR_PART_NO")]),
                p("VENDOR_CODE"): first_valid(g[p("VENDOR_CODE")]),
                p("VENDOR_PI_NO"): first_valid(g[p("VENDOR_PI_NO")]),
                p("CURRENCY"): currency,
                # A missing PI amount is unknown: the order sum stays unknown
                # when any line has none, and never mixes currencies.
                p("PI_VALUE_SUM"): (float(g[p("PI_LINE_VALUE")].sum(min_count=len(g)))
                                    if one_currency else float("nan")),
                p("PI_ADDITIONAL_SUM"): float(g[p("PI_ADDITIONAL")].sum()),
                p("ORDER_QTY_SUM"): float(g[p("QTY_IN_ORDER")].sum()),
                p("PART_QTY_SUM"): float(g[p("QTY_IN_PART")].sum()),
                p("CLEARED_QTY_SUM"): float(g[p("CLEARED_QTY")].sum()),
                p("PO_SENT_DATE"): first_valid(g[p("PO_SENT_DATE")]),
                p("SCHEDULED_SHIP"): first_valid(g[p("SCHEDULED_SHIP")]),
                p("ORDER_STATUS"): first_valid(g[p("ORDER_STATUS")]),
                p("TRANSPORT_MODE_CODE"): first_valid(g[p("TRANSPORT_MODE_CODE")]),
                p("CARRIER"): first_valid(g[p("CARRIER")]),
                p("BL_NO"): first_valid(g[p("BL_NO")]),
                p("BL_SUSPECT"): first_valid(g[p("BL_SUSPECT")]),
                p("KEY_EMP"): first_valid(g[p("KEY_EMP")]),
                p("HS_SUGGESTED"): first_valid(g[p("HS_SUGGESTED")]),
                p("PROGRESS"): float(g[p("PROGRESS")].max()),
                p("STAGE"): top[p("STAGE")],
                p("STAGE_FA"): top[p("STAGE_FA")],
                p("COMMERCIAL_NOTE"): first_valid(g[p("COMMERCIAL_NOTE")]),
                p("LOGISTICS_NOTE"): first_valid(g[p("LOGISTICS_NOTE")]),
                p("BLOCKING"): bool(g[p("BLOCKING")].any()),
                p("TERMINAL"): bool(g[p("TERMINAL")].all()),
                p("EXCLUDED_FROM_KPI"): bool(g[p("EXCLUDED_FROM_KPI")].any()),
                p("CLEARANCE_HINT"): first_valid(g[p("CLEARANCE_HINT")]),
                p("ALERTS"): " ؛ ".join(sorted({a for a in g[p("ALERTS")] if a})),
                p("MATERIAL_COUNT"): len(_uniq(g[p("MATERIAL")])),
                p("MATERIALS_ALL"): "، ".join(_uniq(g[p("MATERIAL")])),
                p("PARTS_ALL"): "، ".join(_uniq(g[p("MFR_PART_NO")])),
                p("MULTI_MATERIAL"): bool(len(_uniq(g[p("MATERIAL")])) > 1),
            })
        out = pd.DataFrame(rows)
        if out.empty:
            return out
        ordered = out[p("ORDER_QTY_SUM")].astype(float)
        cleared = out[p("CLEARED_QTY_SUM")].astype(float)
        out[p("CLEARED_PCT")] = [round(c / o * 100, 1) if o > 0 else 0.0
                                 for c, o in zip(cleared, ordered)]
        return out

    def _aggregate(self, lines: pd.DataFrame, positions: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        p = self.p
        src = lines[lines[KEY_ORDER].astype(str).str.strip() != ""]
        out = self._order_rows(src) if not src.empty else pd.DataFrame(columns=[KEY_ORDER])
        multi = int(out[p("MULTI_MATERIAL")].sum()) if p("MULTI_MATERIAL") in out else 0
        if multi:
            log.warning(
                f"⚠️ [{self.key}] {multi} سفارش چندمتریاله است. هر متریال ردیف خودش را در "
                f"جمعیت و محاسبات دارد؛ مقادیر سطح سفارش روی همه ردیف‌های آن سفارش تکرار "
                f"می‌شوند و جمع ردیفی آن‌ها مجاز نیست.")
            health.current().find(
                "دانه‌بندی", health.WARN,
                f"{multi} سفارش چندمتریاله در سورس خرید",
                "هر متریال ردیف خودش را دارد (MOGH_ITEM_ROLE). مقادیر سطح سفارش "
                "(PI، مقادیر سفارش، NTSW) روی ردیف‌های سفارش تکرار می‌شوند — مثل "
                "ردیف‌های چند بارنامه — و فقط در دانه سفارش/ثبت سفارش جمع می‌شوند.")
        multi_pr = int(out[p("MULTI_PR")].sum()) if p("MULTI_PR") in out else 0
        if multi_pr:
            log.warning(
                f"⚠️ [{self.key}] {multi_pr} سفارش بیش از یک PR دارد. PR اول فقط برای سازگاری "
                f"legacy نگه داشته شده؛ رابطه کامل در {p('PRS_ALL')} و frame مستقل "
                f"order_material_pr_item حفظ شده است.")
            health.current().find(
                "دانه‌بندی", health.WARN,
                f"{multi_pr} سفارش چند-PR در سورس خرید",
                "هیچ PR حذف نشده است؛ برای تحلیل رابطه از frame Order×Material×PR×PR Item استفاده شود.")
        if positions is None:
            positions = self._aggregate_inventory(lines)
        return self._expand_materials(out, lines, positions)

    # ═══════════ هر سفارش × متریال یک ردیف (29.15.11) ═══════════
    #: Fields that belong to the material, not the order. Everything else on an
    #: order row is order-level and is repeated unchanged on each of its
    #: material rows — exactly as it already is on each of its BL rows.
    _MATERIAL_FIELDS = ("MATERIAL", "MATERIAL_DESC", "MFR_PART_NO", "HS_SUGGESTED")
    _GAP_FIELDS = (("PR_NO", "شماره درخواست خرید"), ("PO_SENT_DATE", "تاریخ ابلاغ سفارش"),
                   ("VENDOR_CODE", "کد تأمین‌کننده"), ("PI_LINE_VALUE", "ارزش PI"))

    def _expand_materials(self, out: pd.DataFrame, lines: pd.DataFrame,
                          positions: pd.DataFrame) -> pd.DataFrame:
        """One population row per Order×Material, and one per order-less material.

        Owner's decision (1405-07-05): the expert file is the criterion — no
        material in it may be dropped from the report or kept out of the
        calculations; if something is wrong, it is investigated, not excluded.

        Each further material of an order is a copy of the order row with only
        the material identity replaced, so every order-level value is exactly
        what the order row already carries (and already repeats on each BL
        row). Every row — first, further and order-less — carries its own
        material's identity and its own four part states.
        """
        p = self.p
        role = p("ITEM_ROLE")
        order_key = lines[KEY_ORDER].fillna("").astype(str).str.strip()
        mat_key = lines[KEY_MATERIAL].fillna("").astype(str).str.strip()
        work = lines.assign(_o_key=order_key.values, _m_key=mat_key.values)
        first_valid = self._first_valid
        pos_cols = [p(c) for _, _, c in PART_STATES] + [p(STATE_UNKNOWN_QTY), p("INVENTORY_CONFLICT")]
        pos = {}
        if isinstance(positions, pd.DataFrame) and not positions.empty:
            for rec in positions.to_dict("records"):
                pos[(str(rec[KEY_ORDER]).strip(), str(rec[KEY_MATERIAL]).strip())] = \
                    {c: rec.get(c) for c in pos_cols}
        blank_pos = {c: (float("nan") if c != p("INVENTORY_CONFLICT") else "") for c in pos_cols}

        def identity(g: pd.DataFrame) -> Dict[str, Any]:
            descs = self._uniq_values(g[p("MATERIAL_DESC")])
            gaps = [label for f, label in self._GAP_FIELDS
                    if any(is_empty_val(v, treat_zero_as_empty=(f != "PI_LINE_VALUE")) for v in g[p(f)])]
            row = {p(f): first_valid(g[p(f)]) for f in self._MATERIAL_FIELDS}
            row.update({p("MATERIAL_DESCS_ALL"): " | ".join(descs),
                        p("MATERIAL_DESC_COUNT"): len(descs),
                        p("ITEM_LINE_COUNT"): int(len(g)),
                        p("ITEM_RECORD_GAPS"): "، ".join(gaps)})
            return row

        rows: List[Dict[str, Any]] = []
        by_order = {o: g for o, g in work[work["_o_key"].ne("")].groupby("_o_key", sort=False)}
        for rec in (out.to_dict("records") if not out.empty else []):
            order = str(rec.get(KEY_ORDER, "")).strip()
            g = by_order.get(order)
            if g is None:
                rows.append({**rec, **blank_pos, role: "FIRST"})
                continue
            groups = [(m, mg) for m, mg in g[g["_m_key"].ne("")].groupby("_m_key", sort=False)]
            # the material the order row already represents (same rule as keys.yaml)
            rep = clean_part_no(rec.get(p("MATERIAL"), "")) or clean_part_no(rec.get(p("MFR_PART_NO"), ""))
            rep_group = next((mg for m, mg in groups if m == rep), None)
            first = {**rec, **pos.get((order, rep), blank_pos), role: "FIRST"}
            if rep_group is not None:
                # Every material attribute from this exact material, including
                # missing ones: the order-level first_valid() may have taken a
                # sibling's description, part number or HS.
                first.update(identity(rep_group))
            rows.append(first)
            for m, mg in groups:
                if m == rep:
                    continue
                ident = identity(mg)
                if is_empty_val(ident.get(p("MATERIAL"), "")):
                    ident[p("MATERIAL")] = ""          # KEY_MATERIAL then comes from the part number
                rows.append({**rec, **ident, **pos.get((order, m), blank_pos), role: "ADDITIONAL"})
        orderless = work[work["_o_key"].eq("") & work["_m_key"].ne("")]
        if not orderless.empty:
            # Same aggregation as any order, one group per material: a
            # placeholder order key groups the lines, then is removed again.
            tmp = orderless.drop(columns=["_o_key", "_m_key"]).copy()
            tmp[KEY_ORDER] = "\x00NO_ORDER\x00" + tmp[KEY_MATERIAL].astype(str)
            agg = self._order_rows(tmp)
            for rec, (m, mg) in zip(agg.to_dict("records"),
                                     tmp.groupby(KEY_ORDER, sort=False)):
                material = str(mg[KEY_MATERIAL].iloc[0]).strip()
                rows.append({**rec, **identity(mg), **pos.get(("", material), blank_pos),
                             KEY_ORDER: "", p("ORDER_BASE"): "", role: "NO_ORDER"})
        result = pd.DataFrame(rows) if rows else out
        if rows:
            n_add = int((result[role] == "ADDITIONAL").sum())
            n_none = int((result[role] == "NO_ORDER").sum())
            if n_add or n_none:
                log.info(f"   🧩 [{self.key}] هر سفارش×متریال یک ردیف: {n_add} متریال اضافهٔ سفارش‌ها و "
                         f"{n_none} متریال بدون شماره سفارش وارد جمعیت و محاسبات شد.")
        return result

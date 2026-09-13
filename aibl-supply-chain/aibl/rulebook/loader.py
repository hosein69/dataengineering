# -*- coding: utf-8 -*-
"""RuleBook — بارگذار کتابخانه قوانین YAML.

فلسفه: هیچ عدد قانونی نباید داخل کد پایتون باشد. تمام مهلت‌ها، آستانه‌ها،
ترم‌های حمل، ارزها و کدهای HS در ``aibl/rules/*.yaml`` زندگی می‌کنند و این
کلاس تنها راه دسترسی به آن‌هاست.

قابلیت‌ها:
  * بارگذاری بسته‌ها طبق ``_manifest.yaml`` (فعال/غیرفعال کردن با یک سطر)
  * دسترسی با مسیر نقطه‌ای:  ``rb.get("fx_governance.deadlines.release_production.days")``
  * نسخه‌بندی زمانی: اگر قاعده‌ای بلوک ``versions`` داشته باشد، نسخه معتبر در
    تاریخ اجرا انتخاب می‌شود.
  * ممیزی: ``rb.needs_verification()`` فهرست قواعدی که باید با آخرین بخشنامه
    تطبیق داده شوند را برمی‌گرداند.
  * بارگذاری از مسیر بیرونی با متغیر محیطی ``AIBL_RULES_DIR`` تا بتوان بدون
    نصب مجدد پکیج، قوانین را به‌روزرسانی کرد.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — aibl/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 1


import os
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import yaml

DEFAULT_RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules")
MANIFEST = "_manifest.yaml"


def _rules_dir() -> str:
    return os.environ.get("AIBL_RULES_DIR", DEFAULT_RULES_DIR)


@dataclass
class RuleIssue:
    pack: str
    path: str
    level: str          # error | warning | info
    message: str


class RuleBook:
    """نقطه واحد دسترسی به تمام قوانین."""

    def __init__(self, rules_dir: Optional[str] = None,
                 as_of: Optional[date] = None) -> None:
        self.dir = rules_dir or _rules_dir()
        self.as_of = as_of or date.today()
        self.manifest: Dict[str, Any] = {}
        self.packs: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ═══════════ بارگذاری ═══════════
    def _read(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load(self) -> None:
        self.manifest = self._read(MANIFEST)
        entries = sorted(self.manifest.get("packs", []),
                         key=lambda p: p.get("load_order", 999))
        for entry in entries:
            if not entry.get("enabled", True):
                continue
            try:
                self.packs[entry["id"]] = self._read(entry["file"])
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"بسته قانونی «{entry['id']}» در {self.dir}/{entry['file']} یافت نشد.")

    def reload(self) -> "RuleBook":
        self.packs.clear()
        self._load()
        return self

    # ═══════════ دسترسی ═══════════
    def get(self, path: str, default: Any = None) -> Any:
        """``rb.get("alarms.thresholds.production.bl_age.red")``"""
        node: Any = self.packs
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return self._resolve_versions(node)

    def _resolve_versions(self, node: Any) -> Any:
        """اگر گره بلوک versions داشته باشد، نسخه معتبر در تاریخ مرجع را برگردان."""
        if not (isinstance(node, dict) and "versions" in node):
            return node
        best, best_date = node.get("value"), None
        for v in node["versions"]:
            eff = v.get("effective_from")
            eff_d = date.fromisoformat(eff) if isinstance(eff, str) else eff
            if eff_d and eff_d <= self.as_of and (best_date is None or eff_d > best_date):
                best, best_date = v.get("value"), eff_d
        return best

    def pack(self, name: str) -> Dict[str, Any]:
        return self.packs.get(name, {})

    # ═══════════ کمک‌کننده‌های دامنه ═══════════
    @lru_cache(maxsize=1)
    def _currency_index(self) -> Dict[str, str]:
        idx: Dict[str, str] = {}
        for c in self.get("currencies.currencies", []) or []:
            code = c["code"]
            idx[code.lower()] = code
            for a in c.get("aliases", []) or []:
                idx[str(a).lower().strip()] = code
            if c.get("fa"):
                idx[c["fa"].strip()] = code
        for d in self.get("currencies.derived_units", []) or []:
            for a in d.get("aliases", []) or []:
                idx[str(a).lower().strip()] = d["code"]
        return idx

    def normalize_currency(self, value: Any) -> str:
        s = str(value or "").strip().lower()
        # مقدار تهی pandas به رشته 'nan' تبدیل می‌شود و نباید ارز شمرده شود
        if not s or s in ("nan", "none", "nat", "-", "<na>"):
            return ""
        idx = self._currency_index()
        if s in idx:
            return idx[s]
        for alias, code in idx.items():
            if alias and len(alias) > 2 and alias in s:
                return code
        return s.upper()[:3]

    def currency_minor_units(self, code: str) -> int:
        for c in self.get("currencies.currencies", []) or []:
            if c["code"] == code:
                return int(c.get("minor_units", 2))
        return 2

    def incoterm(self, code: Any) -> Optional[Dict[str, Any]]:
        s = str(code or "").strip().upper()
        if not s:
            return None
        aliases = {str(k).upper(): v for k, v in (self.get("incoterms.aliases", {}) or {}).items()}
        s = aliases.get(s, s)
        for t in self.get("incoterms.terms", []) or []:
            if t["code"] == s:
                return t
        return None

    def detect_payment_method(self, text: Any) -> str:
        s = str(text or "").strip().lower()
        methods = self.get("fx_governance.payment_methods", []) or []
        if s:
            for m in methods:
                for kw in m.get("keywords", []) or []:
                    if str(kw).lower() in s:
                        return m["code"]
        return next((m["code"] for m in methods if m.get("default")), "OTHER")

    def detect_segment(self, text: Any) -> str:
        s = str(text or "").strip().lower()
        segs = self.get("fx_governance.segments", []) or []
        for seg in segs:
            for kw in seg.get("keywords", []) or []:
                if str(kw).lower() in s:
                    return seg["code"]
        return next((s2["code"] for s2 in segs if s2.get("default")), "production")

    def deadline_days(self, key: str) -> Optional[int]:
        node = self.get(f"fx_governance.deadlines.{key}")
        if isinstance(node, dict):
            return node.get("days")
        return node

    def release_deadline_days(self, segment: str) -> int:
        key = "release_commercial" if segment == "commercial" else "release_production"
        return int(self.deadline_days(key) or 540)

    def penalty_tiers(self) -> List[Tuple[Optional[int], float]]:
        return [(t.get("up_to_months"), float(t["monthly_rate"]))
                for t in self.get("fx_governance.penalties.delay_tiers", []) or []]

    def thresholds(self, segment: str) -> Dict[str, Dict[str, Any]]:
        return self.get(f"alarms.thresholds.{segment}", {}) or {}

    def risk_weights(self) -> Dict[str, float]:
        return {k: float(v) for k, v in (self.get("alarms.risk_engine.weights", {}) or {}).items()}

    def risk_band(self, score: float) -> str:
        for band in self.get("alarms.risk_engine.bands", []) or []:
            if score >= float(band["min"]):
                return band["fa"]
        return "🟢 پایین"

    def status_label(self, code: str) -> str:
        return self.get(f"alarms.statuses.{code}.fa", code)

    def status_rank(self, code: str) -> int:
        return int(self.get(f"alarms.statuses.{code}.rank", 0))

    # ── واژگان وضعیت فارسی ──
    def parse_status_note(self, note: Any) -> Dict[str, Any]:
        """«ترخیص درصدی انجام شد//در انتظار خرید ارز» → مرحله، پیشرفت، هشدارها."""
        sep = self.get("status_lexicon.parsing.separator", "//")
        raw = str(note or "").strip()
        parts = [p.strip() for p in raw.split(sep)] if raw else []
        left = parts[0] if parts else ""
        right = parts[1] if len(parts) > 1 else ""

        out: Dict[str, Any] = {
            "COMMERCIAL_NOTE": left, "LOGISTICS_NOTE": right,
            "STAGE": "", "STAGE_FA": "", "PROGRESS": 0,
            "BLOCKING": False, "TERMINAL": False,
            "EXCLUDED_FROM_KPI": False, "CLEARANCE_HINT": "", "ALERTS": [],
        }
        best_progress = -1
        for chunk in (left, right):
            if not chunk:
                continue
            for ph in self.get("status_lexicon.phrases", []) or []:
                m = str(ph["match"])
                hit = (chunk == m) if ph.get("exact") else (m in chunk)
                if not hit:
                    continue
                if ph.get("blocking"):
                    out["BLOCKING"] = True
                if ph.get("terminal"):
                    out["TERMINAL"] = True
                if ph.get("excluded_from_kpi"):
                    out["EXCLUDED_FROM_KPI"] = True
                if ph.get("clearance_type"):
                    out["CLEARANCE_HINT"] = ph["clearance_type"]
                if ph.get("alert"):
                    out["ALERTS"].append(ph["alert"])
                prog = int(ph.get("progress", 0))
                if prog > best_progress:
                    best_progress = prog
                    out["STAGE"] = ph.get("stage", "")
                    out["STAGE_FA"] = ph.get("fa", "")
        out["PROGRESS"] = max(best_progress, 0)
        out["ALERTS"] = " ؛ ".join(out["ALERTS"])
        return out

    # ── بارنامه و HS ──
    def validate_bl(self, value: Any) -> Tuple[bool, str]:
        """آیا مقدار واقعاً یک شماره بارنامه است؟ (True, دلیل) / (False, دلیل)"""
        s = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
        cfg = self.get("transport.bl_validation", {}) or {}
        if not s:
            return False, "خالی"
        if len(s) < int(cfg.get("min_length", 6)):
            return False, "طول کمتر از حداقل"
        if len(s) > int(cfg.get("max_length", 20)):
            return False, "طول بیش از حداکثر"
        prefixes = cfg.get("known_scac_prefixes", []) or []
        if any(s.startswith(p) for p in prefixes):
            return True, "پیشوند SCAC شناخته‌شده"
        if s.isdigit():
            limit = int(cfg.get("reject_if_pure_digits_shorter_than", 9))
            if len(s) < limit:
                return False, "تماماً عددی و کوتاه (احتمالاً شماره فنی یا پروفرما)"
            return False, "تماماً عددی و بدون پیشوند خط کشتیرانی"
        pattern = cfg.get("strict_pattern")
        if pattern and re.match(pattern, s):
            return True, "منطبق بر الگوی استاندارد"
        return False, "عدم انطباق با الگوی بارنامه"

    def infer_hs(self, description: Any) -> Tuple[str, str]:
        """(کد تعرفه پیشنهادی، کلیدواژه منطبق) — صرفاً پیشنهاد."""
        if not self.get("hs_codes.inference.enabled", False):
            return "", ""
        s = str(description or "")
        if not s:
            return "", ""
        for kw, code in (self.get("hs_codes.inference.keyword_map", {}) or {}).items():
            if str(kw) in s:
                return str(code), str(kw)
        return "", ""

    def transport_mode(self, text: Any) -> str:
        """متنِ آزادِ «نوع حمل» → کدِ روش حمل، یا رشتهٔ خالی.

        دو قاعده که ترتیبِ نتیجه را قطعی می‌کنند:

        ۱ **برابریِ کامل مقدم است.** اگر متن دقیقاً یکی از کدها یا
          نام‌هاست، همان برنده است.
        ۲ **در تطبیقِ زیررشته‌ای، نام بلندتر مقدم است.** بدون این، یک
          نام کوتاه می‌توانست نام بلندتری را که در همان متن هست بپوشاند،
          و نتیجه به ترتیبِ نوشتنِ YAML گره می‌خورد — یعنی یک ویرایشِ
          بی‌ربط در فایل قواعد، خروجی را عوض می‌کرد.
        """
        s = str(text or "").strip().lower()
        if not s:
            return ""
        modes = self.get("transport.modes", []) or []
        pairs = []
        for m in modes:
            code = str(m["code"])
            if s == code.lower() or s == str(m.get("fa", "")).strip().lower():
                return code
            for a in m.get("aliases", []) or []:
                a = str(a).strip().lower()
                if a:
                    pairs.append((len(a), a, code))
        for _n, a, code in sorted(pairs, key=lambda x: -x[0]):
            if a in s:
                return code
        return ""

    def transport_mode_fa(self, code: Any) -> str:
        """کدِ روش حمل → برچسبِ فارسی.

        گزارش و فیلتر باید «دریایی» نشان بدهند، نه ``SEA``. تا پیش از
        این چنین نگاشتی وجود نداشت و ستونِ «روش حمل» کدِ انگلیسی را زیر
        سرستونِ فارسی می‌گذاشت.
        """
        c = str(code or "").strip().upper()
        if not c:
            return ""
        for m in self.get("transport.modes", []) or []:
            if str(m["code"]).upper() == c:
                return str(m.get("fa") or c)
        return c

    def fiscal_year_start(self) -> date:
        v = self.get("fx_governance.fiscal_year.starts_on")
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            return date.fromisoformat(v)
        return date(2026, 3, 21)

    def demurrage_critical_days(self) -> int:
        return int(self.get("customs.demurrage.critical_days", 45))

    # ═══════════ ممیزی و اعتبارسنجی ═══════════
    def needs_verification(self) -> List[RuleIssue]:
        """فهرست قواعدی که status آنها needs_verification است."""
        issues: List[RuleIssue] = []

        def walk(node: Any, pack: str, path: str) -> None:
            if isinstance(node, dict):
                if node.get("status") == "needs_verification":
                    issues.append(RuleIssue(pack, path, "info",
                                            node.get("fa") or node.get("note") or path))
                for k, v in node.items():
                    walk(v, pack, f"{path}.{k}" if path else str(k))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, pack, f"{path}[{i}]")

        for name, data in self.packs.items():
            walk(data, name, "")
        return issues

    def validate(self) -> List[RuleIssue]:
        """اعتبارسنجی ساختاری — قبل از هر اجرا صدا زده می‌شود."""
        issues: List[RuleIssue] = []

        w = self.risk_weights()
        if w and abs(sum(w.values()) - 1.0) > 1e-6:
            issues.append(RuleIssue("alarms", "risk_engine.weights", "error",
                                    f"مجموع وزن‌های ریسک {sum(w.values()):.4f} است، باید ۱٫۰ باشد."))

        stages = {s["code"] for s in self.get("fx_governance.lifecycle.stages", []) or []}
        stages |= {s["code"] for s in self.get("status_lexicon.extra_stages", []) or []}
        for ph in self.get("status_lexicon.phrases", []) or []:
            if ph.get("stage") and ph["stage"] not in stages:
                issues.append(RuleIssue("status_lexicon", f"phrases[{ph['match']}]", "error",
                                        f"مرحله ناشناخته «{ph['stage']}»"))

        for seg in ("production", "commercial"):
            for key, t in (self.thresholds(seg) or {}).items():
                y = t.get("yellow") or []
                if len(y) != 2 or y[0] > y[1]:
                    issues.append(RuleIssue("alarms", f"thresholds.{seg}.{key}", "error",
                                            "بازه zard نامعتبر است."))

        for name, pattern_path in (
            ("transport", "transport.bl_validation.strict_pattern"),
            ("hs_codes", "hs_codes.structure.validation.pattern_8"),
        ):
            p = self.get(pattern_path)
            if p:
                try:
                    re.compile(p)
                except re.error as ex:
                    issues.append(RuleIssue(name, pattern_path, "error", f"regex نامعتبر: {ex}"))

        codes = [t["code"] for t in self.get("incoterms.terms", []) or []]
        if codes and len(codes) != len(set(codes)):
            issues.append(RuleIssue("incoterms", "terms", "error", "کد ترم تکراری وجود دارد."))

        return issues

    def summary(self) -> Dict[str, Any]:
        return {
            "rules_dir": self.dir,
            "as_of": str(self.as_of),
            "packs": {k: v.get("version", "?") for k, v in self.packs.items()},
            "errors": len([i for i in self.validate() if i.level == "error"]),
            "needs_verification": len(self.needs_verification()),
        }


_SINGLETON: Optional[RuleBook] = None


def get_rulebook(reload: bool = False, as_of: Optional[date] = None) -> RuleBook:
    global _SINGLETON
    if _SINGLETON is None or reload:
        _SINGLETON = RuleBook(as_of=as_of)
    return _SINGLETON

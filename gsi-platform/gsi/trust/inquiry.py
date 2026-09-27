# -*- coding: utf-8 -*-
"""Ask first, then heal — the register of answers to «why is this odd?».

The warehouse heals itself only in one sense: once a person has looked at an
anomaly and agreed with a specific correction, the correction is re-applied on
every later run, automatically, with its provenance attached. It never decides
on its own. Every path through this module ends in a sentence a human wrote.

Rules this module enforces rather than documents:

1. **Every answer is a sentence.** Approving a repair, rejecting one, calling a
   value genuine or admitting "we don't know" all require a short written
   reason (``MIN_NOTE_CHARS``). A button click with no reason teaches the
   organisation nothing and cannot be audited later.
2. **"We don't know" expires.** It is a legitimate answer for a short while —
   at most ``UNKNOWN_MAX_DAYS`` — and then the anomaly comes back, marked
   overdue, at the top of the list.
3. **Append-only.** Decisions are rows in ``wh_audit`` (``kind =
   'anomaly_decision'``); nothing is edited or deleted. Undoing a repair is a
   new ``revoke`` decision, so the history of who believed what, when, stays.
4. **A repair is bound to what was approved.** A rescale applies only while
   the source still holds the exact value that was approved; if the value
   changes, the repair lapses (reported as *stale*) and the new value is asked
   about afresh. An approval can never silently cover a different fact.
5. **Original values stay visible.** Every healed row carries
   ``HEALED_FIELDS`` — column, old value, new value, who approved and when.
   Keys are never healed (``anomaly.NEVER_HEAL``); computed outputs have no
   repair at all.

Command line (for the operator without the dashboard)::

    python -m gsi.trust.inquiry list
    python -m gsi.trust.inquiry decide <id> explain --note "..." --actor "..."
    python -m gsi.trust.inquiry decide <id> approve --note "..." --actor "..."
    python -m gsi.trust.inquiry decide <id> unknown --days 14 --note "..." --actor "..."
    python -m gsi.trust.inquiry history
"""
from __future__ import annotations

__contract__ = 1

import json
import sys
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import pandas as pd

from ..core.text import clean_key, normalize_persian_text
from .anomaly import (ALIAS, KIND_FA, NEVER_HEAL, RESCALE, STRENGTH_FA, Anomaly,
                      _blank, _numeric_series, fmt_number)
from .verdict import role_fa

AUDIT_KIND = "anomaly_decision"

# ── states ──────────────────────────────────────────────────────────────────
OPEN = "OPEN"
EXPLAINED = "EXPLAINED"
UNKNOWN = "UNKNOWN"
OVERDUE = "OVERDUE"
REPAIR_APPROVED = "REPAIR_APPROVED"
REPAIR_REJECTED = "REPAIR_REJECTED"

STATUS_FA: Dict[str, str] = {
    OVERDUE: "⏰ مهلت «نمی‌دانیم» گذشت",
    OPEN: "❓ منتظر پاسخ",
    UNKNOWN: "⏳ نمی‌دانیم — موقت",
    REPAIR_APPROVED: "🔧 ترمیم تأیید شد",
    EXPLAINED: "💬 توضیح داده شد",
    REPAIR_REJECTED: "✋ ترمیم رد شد — مقدار حفظ شد",
}
#: Display order: what needs a person first.
STATUS_ORDER: Dict[str, int] = {s: i for i, s in enumerate(STATUS_FA)}
#: States that still need an answer.
NEEDS_ANSWER = frozenset({OPEN, OVERDUE})

# ── actions ─────────────────────────────────────────────────────────────────
EXPLAIN = "explain"
APPROVE = "approve"
REJECT = "reject"
DONT_KNOW = "unknown"
REVOKE = "revoke"

ACTION_FA: Dict[str, str] = {
    EXPLAIN: "واقعی است — توضیح می‌دهم",
    APPROVE: "ترمیم پیشنهادی را تأیید می‌کنم",
    REJECT: "ترمیم را رد می‌کنم — مقدار درست است",
    DONT_KNOW: "هنوز نمی‌دانم — تا تاریخ مشخص",
    REVOKE: "پس‌گرفتن پاسخ قبلی",
}
_ACTION_STATE: Dict[str, str] = {
    EXPLAIN: EXPLAINED, APPROVE: REPAIR_APPROVED, REJECT: REPAIR_REJECTED,
    DONT_KNOW: UNKNOWN, REVOKE: OPEN,
}

MIN_NOTE_CHARS = 8
UNKNOWN_DEFAULT_DAYS = 14
UNKNOWN_MAX_DAYS = 30

#: Answers that fill the box without saying anything.
_EMPTY_NOTES = frozenset({
    "-", "--", ".", "..", "...", "ok", "okay", "باشه", "تایید", "تأیید", "درسته",
    "درست است", "نمیدانم", "نمی دانم", "نمی‌دانم", "نمیدونم", "ندارم", "هیچ",
    "بعدا", "بعداً", "تست", "test",
})


class InquiryError(ValueError):
    """A decision that cannot be accepted, with a message for the person."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════
#  Decision
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Decision:
    """One person's answer to one anomaly."""
    anomaly_id: str
    action: str
    note: str
    actor: str
    at: str
    until: str = ""
    #: ALIAS only: apply the same spelling fix wherever it appears in future
    #: runs, not only on the cases seen when it was approved.
    standing: bool = False
    #: The anomaly as it was when answered — what the person actually saw.
    anomaly: Dict[str, Any] = dc_field(default_factory=dict)

    @property
    def state(self) -> str:
        return _ACTION_STATE.get(self.action, OPEN)

    @property
    def repair(self) -> Optional[Dict[str, Any]]:
        if not self.anomaly:
            return None
        return Anomaly.from_dict(self.anomaly).repair

    def as_dict(self) -> Dict[str, Any]:
        return {"anomaly_id": self.anomaly_id, "action": self.action, "note": self.note,
                "actor": self.actor, "at": self.at, "until": self.until,
                "standing": bool(self.standing), "anomaly": dict(self.anomaly)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Decision":
        return cls(anomaly_id=str(d.get("anomaly_id", "")), action=str(d.get("action", "")),
                   note=str(d.get("note", "")), actor=str(d.get("actor", "")),
                   at=str(d.get("at", "")), until=str(d.get("until", "") or ""),
                   standing=bool(d.get("standing", False)),
                   anomaly=dict(d.get("anomaly") or {}))


def make_decision(
    anomaly: Union[Anomaly, Mapping[str, Any]],
    action: str,
    note: str,
    actor: str,
    *,
    today: Optional[date] = None,
    days: Optional[int] = None,
    standing: bool = False,
) -> Decision:
    """Validate an answer and turn it into a decision, or explain why not."""
    data = anomaly.as_dict() if isinstance(anomaly, Anomaly) else dict(anomaly)
    anomaly_id = str(data.get("id") or Anomaly.from_dict(data).id)
    if action not in _ACTION_STATE:
        raise InquiryError(f"اقدام ناشناخته: {action!r}")
    actor = (actor or "").strip()
    if not actor:
        raise InquiryError("نام پاسخ‌دهنده لازم است — پاسخ بی‌نام قابل پیگیری نیست.")
    text = (note or "").strip()
    if len(text) < MIN_NOTE_CHARS or normalize_persian_text(text).lower() in _EMPTY_NOTES:
        raise InquiryError(
            "در یک جمله بنویسید چرا. حتی «نمی‌دانیم» هم باید بگوید چه چیزی را باید "
            "بفهمیم — این جمله تنها چیزی است که دفعه بعد از این ناهنجاری می‌ماند.")

    repair = Anomaly.from_dict(data).repair
    if action in (APPROVE, REJECT) and not repair:
        raise InquiryError("این ناهنجاری ترمیم پیشنهادی ندارد؛ فقط می‌توانید توضیح دهید "
                           "یا «نمی‌دانم» را با مهلت ثبت کنید.")
    if standing and not (action == APPROVE and repair and repair.get("kind") == ALIAS):
        raise InquiryError("«برای موارد آینده هم اعمال شود» فقط برای یکسان‌سازی املا مجاز است؛ "
                           "هر تغییر عددی جداگانه تأیید می‌شود.")

    until = ""
    if action == DONT_KNOW:
        n = UNKNOWN_DEFAULT_DAYS if days is None else int(days)
        if not 1 <= n <= UNKNOWN_MAX_DAYS:
            raise InquiryError(f"«نمی‌دانیم» فقط موقت است: بین ۱ تا {UNKNOWN_MAX_DAYS} روز.")
        until = ((today or date.today()) + timedelta(days=n)).isoformat()

    return Decision(anomaly_id=anomaly_id, action=action, note=text, actor=actor,
                    at=_now(), until=until, standing=bool(standing), anomaly=data)


# ═══════════════════════════════════════════════════════════════════════════
#  Register
# ═══════════════════════════════════════════════════════════════════════════
class InquiryRegister:
    """Every answer ever given, in order. The latest answer per anomaly wins."""

    def __init__(self, decisions: Iterable[Decision] = ()) -> None:
        self._decisions: List[Decision] = list(decisions)

    def __len__(self) -> int:
        return len(self._decisions)

    @property
    def decisions(self) -> List[Decision]:
        return list(self._decisions)

    @classmethod
    def from_dicts(cls, rows: Iterable[Mapping[str, Any]]) -> "InquiryRegister":
        return cls(Decision.from_dict(r) for r in rows or ())

    @classmethod
    def load(cls, warehouse=None) -> "InquiryRegister":
        """All decisions from the warehouse; empty (never an error) without one."""
        from ..warehouse.store import Warehouse, loads

        wh = warehouse or Warehouse(initialize=False)
        if not wh.path.exists():
            return cls()
        try:
            with wh.read_db() as c:
                rows = c.execute("SELECT payload FROM wh_audit WHERE kind=? ORDER BY id",
                                 (AUDIT_KIND,)).fetchall()
        except Exception:
            return cls()
        out: List[Decision] = []
        for (payload,) in rows:
            try:
                out.append(Decision.from_dict(loads(payload)))
            except Exception:
                continue
        return cls(out)

    def record(self, decision: Decision, *, warehouse=None, persist: bool = True) -> Decision:
        """Append a decision (and store it, unless ``persist`` is False)."""
        if persist:
            from ..warehouse.store import Warehouse
            (warehouse or Warehouse()).audit(AUDIT_KIND, decision.as_dict(),
                                             actor=decision.actor or "operator")
        self._decisions.append(decision)
        return decision

    def latest(self, anomaly_id: str) -> Optional[Decision]:
        for d in reversed(self._decisions):
            if d.anomaly_id == anomaly_id:
                return d
        return None

    def status(self, anomaly_id: str, today: Optional[date] = None) -> str:
        d = self.latest(anomaly_id)
        if d is None:
            return OPEN
        if d.action == DONT_KNOW:
            try:
                expired = (today or date.today()) > date.fromisoformat(d.until)
            except ValueError:
                expired = True
            return OVERDUE if expired else UNKNOWN
        return d.state

    def approved(self) -> List[Decision]:
        """Repairs whose latest decision is an approval, in approval order."""
        latest: Dict[str, Decision] = {}
        for d in self._decisions:
            latest[d.anomaly_id] = d
        return [d for d in latest.values() if d.action == APPROVE and d.repair]

    def history_frame(self) -> pd.DataFrame:
        cols = ["زمان", "شناسه", "نوع", "فیلد", "کلید", "پاسخ", "توضیح", "پاسخ‌دهنده", "تا تاریخ"]
        if not self._decisions:
            return pd.DataFrame(columns=cols)
        rows = []
        for d in reversed(self._decisions):
            a = d.anomaly or {}
            rows.append({
                "زمان": d.at[:16].replace("T", " "), "شناسه": d.anomaly_id,
                "نوع": KIND_FA.get(a.get("kind", ""), a.get("kind", "")),
                "فیلد": a.get("field_fa") or a.get("field", ""), "کلید": a.get("key", ""),
                "پاسخ": ACTION_FA.get(d.action, d.action), "توضیح": d.note,
                "پاسخ‌دهنده": d.actor, "تا تاریخ": d.until,
            })
        return pd.DataFrame(rows, columns=cols)


# ═══════════════════════════════════════════════════════════════════════════
#  Applying approved repairs
# ═══════════════════════════════════════════════════════════════════════════
APPLIED_COLUMNS = ["شناسه", "ستون", "کلید", "از", "به", "ردیف", "تأیید", "تاریخ تأیید", "دلیل"]
STALE_COLUMNS = ["شناسه", "ستون", "کلید", "علت", "تأیید"]


def repair_fa(repair: Optional[Mapping[str, Any]]) -> str:
    """One line describing a proposed correction, before → after."""
    if not repair:
        return ""
    label = repair.get("label") or repair.get("column")
    if repair.get("kind") == RESCALE:
        return (f"«{label}» در {repair.get('key')}: از "
                f"{fmt_number(float(repair.get('original', 0)))} به "
                f"{fmt_number(float(repair.get('new', 0)))}")
    if repair.get("kind") == ALIAS:
        return (f"یکسان‌سازی «{repair.get('variant')}» با «{repair.get('canonical')}» "
                f"در «{label}»")
    return str(repair.get("kind", ""))


def apply_repairs(df: pd.DataFrame, decisions: Sequence[Decision]
                  ) -> Tuple[pd.DataFrame, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply human-approved repairs; report the ones that no longer fit.

    Returns ``(df, applied, stale)``. ``df`` always gains ``HEALED_FIELDS``
    (blank on untouched rows) so the column's presence never depends on
    whether anyone approved anything.
    """
    healed = [[] for _ in range(len(df))]
    applied: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []

    for d in decisions:
        rep = d.repair
        if not rep:
            continue
        column = str(rep.get("column", ""))
        key_col = str(rep.get("key_column", ""))
        who = f"{d.actor} · {d.at[:10]}"

        def lapse(reason: str) -> None:
            stale.append({"شناسه": d.anomaly_id, "ستون": column,
                          "کلید": rep.get("key", rep.get("variant", "")),
                          "علت": reason, "تأیید": who})

        if column in NEVER_HEAL:
            lapse("ستون کلید قابل ترمیم نیست")
            continue
        if column not in df.columns:
            lapse("این ستون در داده این اجرا نیست")
            continue

        if rep.get("kind") == RESCALE:
            if key_col not in df.columns:
                lapse("ستون کلید پرونده در داده نیست")
                continue
            original = float(rep["original"])
            factor = float(rep["factor"])
            numbers = _numeric_series(df[column])
            tolerance = max(1e-9, abs(original) * 1e-9)
            match = (df[key_col].map(clean_key) == str(rep.get("key", ""))) & \
                    (numbers - original).abs().le(tolerance)
            if not match.any():
                lapse("مقدار سورس دیگر همان مقدار تأییدشده نیست (یا پرونده نیست) — "
                      "ترمیم اعمال نشد؛ اگر هنوز عجیب است، دوباره پرسیده می‌شود")
                continue
            new = original / factor
            if pd.api.types.is_numeric_dtype(df[column]) and not pd.api.types.is_float_dtype(df[column]):
                df[column] = df[column].astype(float)
            df.loc[match, column] = new
            before, after = fmt_number(original), fmt_number(new)
            key = str(rep.get("key", ""))
        elif rep.get("kind") == ALIAS:
            variant, canonical = str(rep.get("variant", "")), str(rep.get("canonical", ""))
            text = df[column].map(lambda v: "" if _blank(v) else str(v).strip())
            match = text == variant
            if not d.standing and rep.get("keys") and key_col in df.columns:
                match &= df[key_col].map(clean_key).isin(set(rep["keys"]))
            if not match.any():
                if not d.standing:
                    lapse(f"«{variant}» دیگر در این پرونده‌ها نیست — احتمالاً در سورس اصلاح شده")
                continue
            df.loc[match, column] = canonical
            before, after, key = variant, canonical, ("همه موارد" if d.standing else "")
        else:
            lapse(f"نوع ترمیم ناشناخته: {rep.get('kind')}")
            continue

        positions = [i for i, hit in enumerate(match.tolist()) if hit]
        for i in positions:
            healed[i].append(f"{column}: از {before} به {after} (تأیید {who})")
        applied.append({"شناسه": d.anomaly_id, "ستون": column, "کلید": key,
                        "از": before, "به": after, "ردیف": len(positions),
                        "تأیید": d.actor, "تاریخ تأیید": d.at[:10], "دلیل": d.note})

    df["HEALED_FIELDS"] = [" · ".join(parts) for parts in healed]
    return df, applied, stale


# ═══════════════════════════════════════════════════════════════════════════
#  Views
# ═══════════════════════════════════════════════════════════════════════════
INQUIRY_COLUMNS = [
    "وضعیت", "نوع", "چه چیزی عجیب است", "محتمل‌ترین توضیح", "شاهد",
    "ترمیم پیشنهادی", "چه کسی می‌تواند جواب دهد", "نقش", "اداره", "فیلد", "کلید",
    "مقدار", "معمول", "محل در سورس", "آخرین پاسخ", "مهلت", "شناسه",
    "_status", "_severity", "_payload",
]


def inquiries_frame(anomalies: Sequence[Anomaly], register: InquiryRegister,
                    today: Optional[date] = None) -> pd.DataFrame:
    """One row per anomaly with its current answer state, most urgent first."""
    rows = []
    for a in anomalies:
        status = register.status(a.id, today)
        last = register.latest(a.id)
        lead = a.leading
        rows.append({
            "وضعیت": STATUS_FA.get(status, status),
            "نوع": a.kind_fa,
            "چه چیزی عجیب است": a.headline_fa,
            "محتمل‌ترین توضیح": (f"{lead.title_fa} ({STRENGTH_FA.get(lead.strength, '')})"
                                 if lead else ""),
            "شاهد": lead.evidence_fa if lead else "",
            "ترمیم پیشنهادی": repair_fa(a.repair),
            "چه کسی می‌تواند جواب دهد": a.owner_name,
            "نقش": role_fa(a.owner_role),
            "اداره": a.owner_dept,
            "فیلد": a.field_fa or a.field,
            "کلید": a.key,
            "مقدار": a.observed_fa,
            "معمول": a.expected_fa,
            "محل در سورس": a.locator_fa,
            "آخرین پاسخ": (f"{ACTION_FA.get(last.action, last.action)} — {last.note} "
                           f"({last.actor})" if last and last.action != REVOKE else ""),
            "مهلت": last.until if last and last.action == DONT_KNOW else "",
            "شناسه": a.id,
            "_status": status,
            "_severity": round(a.severity, 3),
            "_payload": json.dumps(a.as_dict(), ensure_ascii=False),
        })
    frame = pd.DataFrame(rows, columns=INQUIRY_COLUMNS)
    if frame.empty:
        return frame
    frame["_order"] = frame["_status"].map(lambda s: STATUS_ORDER.get(s, 99))
    frame = frame.sort_values(["_order", "_severity"], ascending=[True, False], kind="stable")
    return frame.drop(columns="_order").reset_index(drop=True)


def summarize(frame: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Counts for the headline and the trend snapshot."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return {"total": 0, "needs_answer": 0, "by_status": {}, "by_kind": {}}
    by_status = frame["_status"].value_counts().to_dict()
    return {
        "total": int(len(frame)),
        "needs_answer": int(sum(by_status.get(s, 0) for s in NEEDS_ANSWER)),
        "by_status": {str(k): int(v) for k, v in by_status.items()},
        "by_kind": {str(k): int(v) for k, v in frame["نوع"].value_counts().items()},
    }


def headline_fa(summary: Mapping[str, Any], applied: int = 0) -> str:
    total = int(summary.get("total", 0))
    if not total:
        return "ناهنجاری تازه‌ای دیده نشد."
    waiting = int(summary.get("needs_answer", 0))
    text = f"{total} ناهنجاری دیده شد؛ {waiting} مورد منتظر پاسخ شماست"
    overdue = int((summary.get("by_status") or {}).get(OVERDUE, 0))
    if overdue:
        text += f" ({overdue} مورد مهلت «نمی‌دانیم»ش گذشته)"
    if applied:
        text += f" · {applied} ترمیم تأییدشده در این اجرا اعمال شد"
    return text + ". هیچ‌کدام حذف یا بی‌صدا اصلاح نشده است."


# ═══════════════════════════════════════════════════════════════════════════
#  Command line
# ═══════════════════════════════════════════════════════════════════════════
def _latest_anomalies() -> List[Anomaly]:
    """The published run's anomalies, read from that run's own frame.

    29.15.0 also copied them into every trust snapshot, where they were 97% of
    the payload (1 KB → 125 KB per run, twice with report_metadata) and every
    trend-page load decoded up to 60 of them. Found by A/B, 29.15.1.
    """
    from ..warehouse.store import Warehouse
    wh = Warehouse(initialize=False)
    if not wh.path.exists():
        return []
    try:
        rid = wh.current_run("report")
        with wh.read_db() as c:
            row = c.execute("SELECT id FROM wh_frame WHERE run_id=? AND layer='mart' "
                            "AND name='extras/anomaly_inquiries' ORDER BY created DESC LIMIT 1",
                            (rid,)).fetchone()
        frame = wh.read_frame(row[0]) if row else None
    except Exception:
        return []
    if not isinstance(frame, pd.DataFrame) or "_payload" not in frame.columns:
        return []
    return [Anomaly.from_dict(json.loads(p)) for p in frame["_payload"]]


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import os

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(prog="python -m gsi.trust.inquiry",
                                     description="ناهنجاری‌ها: اول بپرس، بعد ترمیم کن")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="ناهنجاری‌های آخرین اجرا و وضعیت پاسخشان")
    sub.add_parser("history", help="همه پاسخ‌های ثبت‌شده")
    p = sub.add_parser("decide", help="ثبت پاسخ برای یک ناهنجاری")
    p.add_argument("id")
    p.add_argument("action", choices=sorted(_ACTION_STATE))
    p.add_argument("--note", required=True)
    p.add_argument("--actor", default=os.environ.get("USERNAME") or os.environ.get("USER") or "")
    p.add_argument("--days", type=int, default=None)
    p.add_argument("--standing", action="store_true")
    args = parser.parse_args(argv)

    register = InquiryRegister.load()
    if args.cmd == "history":
        frame = register.history_frame()
        print(frame.to_string(index=False) if not frame.empty else "هنوز پاسخی ثبت نشده است.")
        return 0

    anomalies = _latest_anomalies()
    if args.cmd == "list":
        if not anomalies:
            print("در آخرین اجرای ثبت‌شده ناهنجاری‌ای نیست (یا هنوز اجرایی ثبت نشده).")
            return 0
        frame = inquiries_frame(anomalies, register)
        for row in frame.to_dict("records"):
            print(f"[{row['شناسه']}] {row['وضعیت']} · {row['نوع']}")
            print(f"   {row['چه چیزی عجیب است']}")
            print(f"   محتمل‌ترین توضیح: {row['محتمل‌ترین توضیح']}")
            if row["ترمیم پیشنهادی"]:
                print(f"   ترمیم پیشنهادی: {row['ترمیم پیشنهادی']}")
        return 0

    target = next((a for a in anomalies if a.id == args.id), None)
    if target is None:
        prior = register.latest(args.id)
        if prior is None:
            print(f"شناسه {args.id} در آخرین اجرا نیست.", file=sys.stderr)
            return 2
        target = Anomaly.from_dict(prior.anomaly)
    try:
        decision = make_decision(target, args.action, args.note, args.actor,
                                 days=args.days, standing=args.standing)
    except InquiryError as ex:
        print(f"ثبت نشد: {ex}", file=sys.stderr)
        return 2
    register.record(decision)
    print(f"ثبت شد: {ACTION_FA[decision.action]} — {target.headline_fa}")
    if decision.action == APPROVE:
        print("ترمیم در اجرای بعدی خط لوله اعمال می‌شود؛ مقدار اصلی در HEALED_FIELDS می‌ماند.")
    return 0


__all__ = [
    "OPEN", "EXPLAINED", "UNKNOWN", "OVERDUE", "REPAIR_APPROVED", "REPAIR_REJECTED",
    "STATUS_FA", "NEEDS_ANSWER", "EXPLAIN", "APPROVE", "REJECT", "DONT_KNOW", "REVOKE",
    "ACTION_FA", "MIN_NOTE_CHARS", "UNKNOWN_DEFAULT_DAYS", "UNKNOWN_MAX_DAYS",
    "InquiryError", "Decision", "make_decision", "InquiryRegister", "apply_repairs",
    "repair_fa", "inquiries_frame", "summarize", "headline_fa", "AUDIT_KIND",
    "APPLIED_COLUMNS", "STALE_COLUMNS", "INQUIRY_COLUMNS",
]


if __name__ == "__main__":
    sys.exit(main())

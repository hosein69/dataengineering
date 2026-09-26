from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .patterns import match_cases

VERSION = "offline-process-2"
MAX_BYTES = 20 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _first_col(df: pd.DataFrame, *names: str) -> str | None:
    lookup = {str(c).casefold(): str(c) for c in df.columns}
    for name in names:
        if name.casefold() in lookup:
            return lookup[name.casefold()]
    return None


def _shown(value: object) -> str:
    if value is None or pd.isna(value):
        return "مشاهده نشده"
    text = str(value).strip()
    return text if text else "مشاهده نشده"


def _parse_optional_time(value: object, *, field: str) -> pd.Timestamp | None:
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    ts = pd.to_datetime(value, errors="coerce", utc=True, format="ISO8601")
    if pd.isna(ts):
        raise ValueError(f"Invalid {field} timestamp; use ISO 8601")
    return ts


def _handoff_analysis(df: pd.DataFrame) -> dict[str, Any]:
    from_col = _first_col(df, "FROM_TEAM", "from_team")
    to_col = _first_col(df, "TO_TEAM", "to_team")
    if not from_col and not to_col:
        return {
            "status": "not_computable",
            "rows": [],
            "summary": {},
            "note": "ستون‌های صریح from_team و to_team در منبع مشاهده نشد؛ تحویل بین واحدها قابل محاسبه نیست.",
        }
    if not from_col or not to_col:
        raise ValueError("Handoff needs both from_team and to_team when either is supplied")

    cols = {
        "handoff_id": _first_col(df, "HANDOFF_ID", "handoff_id"),
        "sent_at": _first_col(df, "SENT_AT", "sent_at"),
        "accepted_at": _first_col(df, "ACCEPTED_AT", "accepted_at"),
        "completed_at": _first_col(df, "COMPLETED_AT", "completed_at"),
        "channel": _first_col(df, "CHANNEL", "channel"),
        "document_ref": _first_col(df, "DOCUMENT_REF", "document_ref"),
        "return_reason": _first_col(df, "RETURN_REASON", "return_reason"),
        "owner_team": _first_col(df, "OWNER_TEAM", "owner_team"),
    }
    rows = []
    for _, row in df.iterrows():
        from_team, to_team = _shown(row[from_col]), _shown(row[to_col])
        # Empty/absent handoff cells on ordinary event rows are ignored. If one side
        # is present, both sides must be explicit; we do not invent an organizational link.
        raw_from = "" if pd.isna(row[from_col]) else str(row[from_col]).strip()
        raw_to = "" if pd.isna(row[to_col]) else str(row[to_col]).strip()
        if not raw_from and not raw_to:
            continue
        if not raw_from or not raw_to:
            raise ValueError("Incomplete handoff row: from_team and to_team must both be present")
        sent = _parse_optional_time(row[cols["sent_at"]], field="sent_at") if cols["sent_at"] else None
        accepted = _parse_optional_time(row[cols["accepted_at"]], field="accepted_at") if cols["accepted_at"] else None
        completed = _parse_optional_time(row[cols["completed_at"]], field="completed_at") if cols["completed_at"] else None
        if sent is not None and accepted is not None and accepted < sent:
            raise ValueError("accepted_at precedes sent_at")
        if accepted is not None and completed is not None and completed < accepted:
            raise ValueError("completed_at precedes accepted_at")
        if sent is not None and completed is not None and completed < sent:
            raise ValueError("completed_at precedes sent_at")
        def val(key: str) -> str:
            c = cols[key]
            return _shown(row[c]) if c else "مشاهده نشده"
        rec = {
            "case_key": str(row["_CASE_KEY"]),
            "handoff_id": val("handoff_id"),
            "from_team": from_team,
            "to_team": to_team,
            "owner_team": val("owner_team"),
            "sent_at": sent.isoformat() if sent is not None else "مشاهده نشده",
            "accepted_at": accepted.isoformat() if accepted is not None else "مشاهده نشده",
            "completed_at": completed.isoformat() if completed is not None else "مشاهده نشده",
            "channel": val("channel"),
            "document_ref": val("document_ref"),
            "return_reason": val("return_reason"),
            "source_row": int(row["source_row"]),
        }
        if sent is not None and accepted is not None:
            rec["acceptance_hours"] = round((accepted - sent).total_seconds() / 3600, 3)
        else:
            rec["acceptance_hours"] = None
        rows.append(rec)
    if not rows:
        return {
            "status": "not_computable",
            "rows": [],
            "summary": {},
            "note": "ستون‌های تحویل وجود دارند اما هیچ ردیف تحویل کامل مشاهده نشد؛ صفر گزارش نمی‌شود.",
        }
    returned = sum(1 for r in rows if r["return_reason"] != "مشاهده نشده")
    acceptance = [r["acceptance_hours"] for r in rows if r["acceptance_hours"] is not None]
    return {
        "status": "ready",
        "rows": rows,
        "summary": {
            "handoff_rows": len(rows),
            "unique_cases": len({r["case_key"] for r in rows}),
            "returns_with_reason": returned,
            "median_acceptance_hours": round(float(pd.Series(acceptance).median()), 3) if acceptance else None,
        },
        "note": "فقط تحویل‌های صریح منبع نمایش داده می‌شوند؛ نبود زمان/سند به صفر یا انجام‌شدن تبدیل نمی‌شود.",
    }


def _case_status(df: pd.DataFrame) -> list[dict[str, Any]]:
    owner = _first_col(df, "OWNER_TEAM", "owner_team")
    state = _first_col(df, "CASE_STATE", "case_state")
    action = _first_col(df, "NEXT_ACTION", "next_action")
    quality = _first_col(df, "EVIDENCE_QUALITY", "evidence_quality")
    out = []
    for _, row in df.groupby("_CASE_KEY", sort=False).tail(1).iterrows():
        out.append({
            "case_key": str(row["_CASE_KEY"]),
            "current_activity": str(row["ACTIVITY_FA"]),
            "observed_at": row["EVENTTIME"].isoformat(),
            "case_state": _shown(row[state]) if state else "مشاهده نشده",
            "owner_team": _shown(row[owner]) if owner else "مشاهده نشده",
            "evidence_quality": _shown(row[quality]) if quality else "مشاهده نشده",
            "next_action": _shown(row[action]) if action else "مشاهده نشده",
            "source_row": int(row["source_row"]),
        })
    return out


def profile(events: pd.DataFrame, *, source: str = "input", reference: str = "unspecified",
            pattern_spec: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Strict event contract; no inferred completion, SLA or financial metrics."""
    if not isinstance(events, pd.DataFrame) or not 0 < len(events) <= 200000:
        raise ValueError("Event count must be 1..200000")
    df = events.copy()
    if "_CASE_KEY" not in df and "CASE_KEY" in df:
        df = df.rename(columns={"CASE_KEY": "_CASE_KEY"})
    cols = ["_CASE_KEY", "ACTIVITY_FA", "EVENTTIME"]
    if not set(cols).issubset(df.columns):
        raise ValueError("Required: _CASE_KEY, ACTIVITY_FA, EVENTTIME")
    for c in cols[:2]:
        if df[c].isna().any() or df[c].astype(str).str.strip().eq("").any():
            raise ValueError("Missing case or activity")
        df[c] = df[c].astype(str).str.strip()
        if df[c].str.len().max() > 300:
            raise ValueError("Case/activity exceeds 300 characters")
    df["EVENTTIME"] = pd.to_datetime(df.EVENTTIME, errors="coerce", utc=True, format="ISO8601")
    if df.EVENTTIME.isna().any():
        raise ValueError("Invalid timestamp; use ISO 8601")
    order = ["_CASE_KEY", "EVENTTIME"]
    if "_SORTING" in df:
        df["_SORTING"] = pd.to_numeric(df["_SORTING"], errors="coerce")
        import numpy as np
        if not np.isfinite(df["_SORTING"]).all():
            raise ValueError("Invalid event ordering")
        order.append("_SORTING")
    if df.duplicated(order).any():
        raise ValueError("Ambiguous simultaneous events: supply distinct _SORTING values")
    # Source row is assigned before sorting so evidence points to the input file row.
    df["source_row"] = range(2, len(df) + 2)
    df = df.sort_values(order, kind="stable").reset_index(drop=True)

    activities = sorted(df.ACTIVITY_FA.unique())
    if len(activities) > 60:
        raise ValueError("Graph limit is 60 activities; narrow the input scope")
    ids = {a: f"n{i}" for i, a in enumerate(activities)}
    latest = df.groupby("_CASE_KEY", sort=False).tail(1).ACTIVITY_FA.value_counts()
    nodes = [{"id": ids[a], "label": a, "count": int(latest.get(a, 0)), "status": "neutral"}
             for a in activities]

    routes: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    occurrences: defaultdict[tuple[str, str], int] = defaultdict(int)
    durations: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    rework = 0
    for case, g in df.groupby("_CASE_KEY", sort=False):
        acts = g.ACTIVITY_FA.tolist()
        times = g.EVENTTIME.tolist()
        rework += int(len(acts) != len(set(acts)))
        for a, b, ta, tb in zip(acts, acts[1:], times, times[1:]):
            routes[a, b].add(str(case))
            occurrences[a, b] += 1
            hours = (tb - ta).total_seconds() / 3600
            if hours < 0:
                raise ValueError("Negative transition duration after event ordering")
            durations[a, b].append(float(hours))

    edges = []
    route_metrics = []
    for (a, b), cases in sorted(routes.items()):
        vals = pd.Series(durations[a, b], dtype="float64")
        median_hours = round(float(vals.median()), 3)
        p90_hours = round(float(vals.quantile(0.90)), 3)
        edge = {
            "source": ids[a], "target": ids[b], "count": len(cases),
            "occurrences": occurrences[a, b], "median_hours": median_hours,
            "p90_hours": p90_hours,
        }
        edges.append(edge)
        route_metrics.append({
            "from_activity": a, "to_activity": b, "unique_cases": len(cases),
            "occurrences": occurrences[a, b], "median_hours": median_hours,
            "p90_hours": p90_hours,
        })

    spans = df.groupby("_CASE_KEY").EVENTTIME.agg(["min", "max"])
    median = float(((spans["max"] - spans["min"]).dt.total_seconds() / 86400).median())
    kpis = [
        {"label": "پرونده مشاهده‌شده", "value": len(spans), "status": "neutral"},
        {"label": "رویداد معتبر", "value": len(df), "status": "neutral"},
        {"label": "پرونده با فعالیت تکراری", "value": rework, "status": "neutral"},
        {"label": "میانه بازه مشاهده (روز)", "value": round(median, 2), "status": "neutral"},
    ]

    evidence_cols = cols + (["_SORTING"] if "_SORTING" in df.columns else []) + ["source_row"]
    evidence = df[evidence_cols].copy()
    evidence["EVENTTIME"] = evidence.EVENTTIME.map(lambda x: x.isoformat())
    records = evidence.to_dict("records")
    cases = _case_status(df)
    handoff = _handoff_analysis(df)
    patterns = match_cases(records, pattern_spec)

    return {
        "version": VERSION,
        "source": str(source),
        "reference": str(reference),
        "kpis": kpis,
        "graph": {"nodes": nodes, "edges": edges},
        "route_metrics": route_metrics,
        "case_status": cases,
        "handoff": handoff,
        "patterns": patterns,
        "events": records,
        "notes": (
            "گره: آخرین مرحله مشاهده‌شده، نه الزاماً کار باز. مسیر: پرونده یکتا و دفعات عبور جدا. "
            "زمان مسیر فقط فاصله رویدادهای مشاهده‌شده است، نه اتلاف قابل حذف یا SLA. "
            "تکرار فعالیت الزاماً خطا نیست؛ داده ناموجود به صفر تبدیل نمی‌شود."
        ),
    }


def build_bundle(events: pd.DataFrame, *, source: str = "input", reference: str = "unspecified",
                 title: str = "گزارش فرآیند", recipient: str = "",
                 pattern_spec: Mapping[str, Any] | None = None) -> dict[str, bytes]:
    if os.environ.get("GSI_AUTOMATION_DISABLED") == "1":
        raise RuntimeError("Automation paused")
    if any(c in recipient + title for c in "\r\n"):
        raise ValueError("Invalid mail header")
    facts = profile(events, source=source, reference=reference, pattern_spec=pattern_spec)
    kit = Path(__file__).resolve().parents[2] / "process-mining-ui-kit"
    if str(kit) not in sys.path:
        sys.path.append(str(kit))  # append: never shadow GSI modules (kit ships app.py)
    from pm_ui.export.standalone_html import build_standalone_html
    from pm_ui.export.html_report import build_report_html
    from pm_ui.export.excel_report import build_excel_report

    graph = facts["graph"]
    data = {
        "kpis": facts["kpis"],
        "graph": graph,
        "case_status": facts["case_status"],
        "route_metrics": facts["route_metrics"],
        "handoff": facts["handoff"],
        "patterns": facts["patterns"],
        "evidence": {
            "title": "شواهد رویدادها (حداکثر ۱۰۰ ردیف؛ JSON شامل همه ردیف‌ها)",
            "columns": [{"key": k, "label": v} for k, v in [
                ("_CASE_KEY", "پرونده"), ("ACTIVITY_FA", "فعالیت"),
                ("EVENTTIME", "زمان"), ("source_row", "ردیف ورودی")]],
            "rows": facts["events"][:100], "source_meta": str(source),
            "gap_note": facts["notes"], "gap_warning": True,
        },
    }
    subtitle = f"مرجع: {reference} | {facts['notes']}"
    analysis = {
        "version": facts["version"], "source": facts["source"], "reference": facts["reference"],
        "case_status": facts["case_status"], "route_metrics": facts["route_metrics"],
        "handoff": facts["handoff"], "patterns": facts["patterns"], "notes": facts["notes"],
    }
    files = {
        "report.html": build_standalone_html(title=title, data=data, subtitle=subtitle).encode("utf-8"),
        "email-body.html": build_report_html(
            title=title, kpis=facts["kpis"], nodes=graph["nodes"], edges=graph["edges"],
            subtitle=subtitle).encode("utf-8"),
        "report.xlsx": build_excel_report(
            kpis=facts["kpis"], nodes=graph["nodes"], edges=graph["edges"],
            case_status=facts["case_status"], handoff=facts["handoff"], patterns=facts["patterns"]),
        "evidence.json": encoded(facts),
        "process-analysis.json": encoded(analysis),
    }
    msg = EmailMessage()
    msg["Subject"] = title
    msg["X-Unsent"] = "1"
    if recipient:
        msg["To"] = recipient
    msg.set_content(subtitle)
    msg.add_alternative(files["email-body.html"].decode("utf-8"), subtype="html")
    msg.add_attachment(files["report.html"], maintype="text", subtype="html", filename="report.html")
    files["outlook-draft.eml"] = msg.as_bytes()
    if sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError("Export exceeds 20 MiB; narrow scope")

    kit_hashes = {
        str(f.relative_to(kit)): digest(f.read_bytes())
        for f in sorted(kit.rglob("*"))
        if f.is_file() and f.suffix in (".py", ".json")
    }
    identity = digest(encoded({
        "facts": facts, "title": title, "recipient": recipient,
        "implementation": digest(Path(__file__).read_bytes()), "kit": kit_hashes,
    }))
    files["manifest.json"] = encoded({
        "version": VERSION, "task_id": identity,
        "files": {n: digest(b) for n, b in files.items()},
    })
    return files


def zip_bundle(files: Mapping[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in files.items():
            z.writestr(n, b)
    return out.getvalue()


def verify_bundle(path: str | Path, task_id: str) -> None:
    path = Path(path)
    m = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    expected = {
        "report.html", "email-body.html", "report.xlsx", "evidence.json",
        "process-analysis.json", "outlook-draft.eml",
    }
    if (m["task_id"] != task_id or set(m["files"]) != expected or
            {p.name for p in path.iterdir()} != expected | {"manifest.json"}):
        raise ValueError("Manifest mismatch")
    for n, h in m["files"].items():
        if (path / n).is_symlink() or digest((path / n).read_bytes()) != h:
            raise ValueError("Artifact integrity failure")


def publish_bundle(files: Mapping[str, bytes], root: str | Path) -> Path:
    """Immutable directory publication. Atomic directory lock; never auto-break locks."""
    if os.environ.get("GSI_AUTOMATION_DISABLED") == "1":
        raise RuntimeError("Automation paused")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if (root / ".paused").exists():
        raise RuntimeError("Share publication paused")
    task = json.loads(files["manifest.json"])["task_id"]
    if len(task) != 64 or any(c not in "0123456789abcdef" for c in task):
        raise ValueError("Invalid task ID")
    lock = root / ".gsi-publish.lock"
    lock.mkdir()  # another publisher, stale lock or missing permission: fail closed
    stage = None
    try:
        (lock / "owner.json").write_bytes(encoded({"pid": os.getpid(), "task_id": task}))
        final = root / task
        if final.exists():
            verify_bundle(final, task)
            return final
        stage = Path(tempfile.mkdtemp(prefix=".gsi-staging-", dir=root))
        for n, b in files.items():
            if Path(n).name != n:
                raise ValueError("Invalid artifact path")
            with (stage / n).open("xb") as f:
                f.write(b)
                f.flush()
                os.fsync(f.fileno())
        verify_bundle(stage, task)
        stage.rename(final)
        stage = None
        return final
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        shutil.rmtree(lock)

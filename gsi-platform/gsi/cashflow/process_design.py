# -*- coding: utf-8 -*-
"""Interactive cash-flow process explorer for HTML and Streamlit.

The graph renderer is deliberately sourced from the bundled Process Explorer UI kit
(`process-mining-ui-kit/pm_ui/charts/process_flow.py`) that ships with GSI.  This
module only adapts GSI financial evidence to that graph contract and adds drill-down
and path/evidence tables.  It does not infer missing business events.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from html import escape
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd


RESULT_STAGES: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    ("ORDER_REG", "ثبت سفارش", "تجاری", ("REGISTRATION",)),
    ("ALLOCATION_QUEUE", "درخواست / صف تخصیص", "ارزی", ("QUEUE",)),
    ("ALLOCATION", "تخصیص ارز", "ارزی", ("ALLOCATION",)),
    ("COMMITMENT", "ایجاد تعهد ارزی", "بانکی", ("COMMITMENT",)),
    ("FX_PURCHASE", "خرید ارز", "بانکی", ("FX_BUY", "FX_SELL")),
    ("FUNDING", "تأمین وجه", "بانکی", ("FUNDING",)),
    ("PAYMENT", "پرداخت / سوئیفت", "بانکی", ("PAYMENT",)),
    ("SHIPMENT", "حمل", "لجستیک", ("SHIPMENT",)),
    ("CUSTOMS", "ورود / EPL", "گمرک", ("CUSTOMS",)),
    ("CLEARANCE", "ترخیص", "گمرک", ("CLEARANCE",)),
    ("BANK_DOCS", "ارائه سند به بانک", "بانکی", ("BANK_DOCS",)),
    ("SETTLEMENT", "رفع / عودت تعهد", "بانکی", ("SETTLEMENT", "COMMITMENT_RETURN")),
)

STAGE56_STAGES: Tuple[Tuple[str, str, str], ...] = (
    ("ORDER_REG", "ثبت سفارش", "تجاری"),
    ("ALLOCATION_QUEUE", "صف تخصیص", "ارزی"),
    ("ALLOCATION", "تخصیص ارز", "ارزی"),
    ("COMMITMENT", "ایجاد تعهد ارزی", "بانکی"),
    ("FX_PURCHASE", "خرید ارز", "بانکی"),
    ("FUNDING", "تأمین وجه", "بانکی"),
    ("SWIFT_CONVERSION", "سوئیفت / تبدیل / وصول ذی‌نفع", "بانکی"),
    ("SHIPMENT", "حمل", "لجستیک"),
    ("CUSTOMS", "ورود / EPL", "گمرک"),
    ("CLEARANCE", "ترخیص", "گمرک"),
    ("BANK_DOCS", "ارائه/تطبیق سند ترخیص با بانک", "بانکی"),
    ("SETTLEMENT", "رفع تعهد", "بانکی"),
)

LEDGER_TO_STAGE = {
    "REGISTRATION_VALUE": "ORDER_REG", "ORDER_REG": "ORDER_REG",
    "ALLOCATION_REQUEST": "ALLOCATION_QUEUE", "ALLOCATION_QUEUE": "ALLOCATION_QUEUE",
    "ALLOCATION": "ALLOCATION",
    "FX_PURCHASE": "FX_PURCHASE", "FX_BUY": "FX_PURCHASE", "FX_SELL": "FX_PURCHASE",
    "BANK_FUNDING_IRR": "FUNDING", "FUNDING": "FUNDING",
    "SUPPLIER_PAYMENT": "SWIFT_CONVERSION", "PAYMENT": "SWIFT_CONVERSION",
    "SWIFT": "SWIFT_CONVERSION", "SWIFT_CONVERSION": "SWIFT_CONVERSION",
    "SHIPMENT": "SHIPMENT", "CUSTOMS": "CUSTOMS", "CLEARANCE": "CLEARANCE",
    "BANK_DOCS": "BANK_DOCS", "SETTLEMENT": "SETTLEMENT",
    "COMMITMENT_INITIAL": "COMMITMENT",
    "COMMITMENT_RELEASED": "SETTLEMENT", "COMMITMENT_RETURN": "SETTLEMENT",
    "COMMITMENT_BALANCE": "SETTLEMENT",
}

STATUS_LABELS = {
    "DONE": "دارای شاهد", "OBSERVED": "دارای شاهد", "MATCH": "تطبیق‌شده",
    "CURRENT": "مرحله جاری", "PARTIAL": "شاهد ناقص", "PENDING": "در انتظار شاهد",
    "NO_EVIDENCE": "بدون شاهد در منبع", "EVIDENCE_GAP": "شکاف شاهد",
    "WARNING": "نیازمند بررسی", "OVERDUE": "مهلت گذشته", "CRITICAL": "بحرانی",
    "MISMATCH": "مغایرت", "CONFLICT": "تعارض", "LEDGER_ONLY": "فقط دفتر",
    "NOT_APPLICABLE": "نامشمول/نامعلوم", "SOURCE_FACT": "شاهد منبع",
}


def _text(v: Any) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v).strip()


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return None


def _date_value(v: Any) -> Optional[str]:
    """Same calendar semantics as the rest of GSI (Jalali-aware, D/M/Y).

    ``pd.to_datetime`` alone read «1403/05/12» as out-of-range (lost) and read
    «05/03/2026» as May 3rd while CalendarEngine reads it as 5 March — so the
    performance view could disagree with the ledger on the same evidence.
    """
    s = _text(v)
    if not s:
        return None
    from ..core.jalali import CalendarEngine
    d = CalendarEngine.parse(s)
    if d is not None:
        return datetime(d.year, d.month, d.day).isoformat()
    try:
        ts = pd.to_datetime(s, errors="coerce", format="ISO8601")
        if pd.isna(ts):
            return None
        return ts.isoformat()
    except Exception:
        return None


def _status_token(status: str) -> str:
    s = _text(status).upper()
    if s in {"CRITICAL", "OVERDUE", "MISMATCH", "CONFLICT"}:
        return "critical"
    if s in {"EVIDENCE_GAP", "WARNING", "PARTIAL", "LEDGER_ONLY"}:
        return "warning"
    if s in {"DONE", "OBSERVED", "MATCH", "SOURCE_FACT"}:
        return "good"
    if s in {"CURRENT"}:
        return "serious"
    if s in {"PENDING", "NO_EVIDENCE", "NOT_APPLICABLE", ""}:
        return "unknown"
    return "neutral"


def _worst_status(values: Iterable[str]) -> str:
    rank = {"CRITICAL": 7, "OVERDUE": 7, "MISMATCH": 6, "CONFLICT": 6,
            "EVIDENCE_GAP": 5, "WARNING": 4, "PARTIAL": 4, "CURRENT": 3,
            "PENDING": 2, "NO_EVIDENCE": 1, "NOT_APPLICABLE": 0,
            "DONE": 0, "OBSERVED": 0, "MATCH": 0, "SOURCE_FACT": 0}
    vals = [_text(v).upper() or "NO_EVIDENCE" for v in values]
    return max(vals, key=lambda x: rank.get(x, 1), default="NO_EVIDENCE")


def _amounts(rows: Sequence[Mapping[str, Any]]) -> str:
    # Currency safety: aggregate only within the same currency; never across currencies.
    by: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    seen = False
    for r in rows:
        n = _num(r.get("amount"))
        cur = _text(r.get("currency")) or "?"
        if n is None:
            continue
        seen = True
        by[cur] += Decimal(str(n))
    if not seen:
        return "—"
    return " | ".join(f"{format(v, 'f')} {k}" for k, v in sorted(by.items()))


def _flow_renderer(nodes: Sequence[dict], edges: Sequence[dict], *, mode: str = "frequency") -> str:
    """Use the Process Explorer renderer bundled from the user's flowchart ZIP."""
    kit = Path(__file__).resolve().parents[2] / "process-mining-ui-kit"
    render_edges=[dict(e) for e in edges]
    if render_edges and max(int(e.get("count") or 0) for e in render_edges) <= 0:
        # The UI kit intentionally scales line width by frequency.  Preserve a
        # faint structural pipeline even when the selected scope has no paired
        # observations, while keeping the visible label at the real count=0.
        for e in render_edges: e["count"]=1
    # Add the bundled kit once and leave it: Streamlit renders sessions on
    # parallel threads, and the former insert/remove pair could drop the path
    # while another session was importing ``pm_ui``.
    if str(kit) not in sys.path:
        sys.path.append(str(kit))
    from pm_ui.charts.process_flow import flowgraph_svg
    width = max(1180, 190 * max(6, len(nodes)))
    return flowgraph_svg(nodes, render_edges, width=width, height=430, node_w=170, node_h=68,
                         mode=mode, abstraction=100)


def _frame_records(df: Any) -> List[dict]:
    return df.to_dict("records") if isinstance(df, pd.DataFrame) and not df.empty else []


def _normalize_result(result: Mapping[str, Any]) -> dict:
    stages = [{"code":c,"label":l,"phase":p,"kinds":list(k)} for c,l,p,k in RESULT_STAGES]
    kind_to_stage = {kind:s[0] for s in RESULT_STAGES for kind in s[3]}
    events = _frame_records(result.get("events"))
    chain = _frame_records(result.get("chain"))
    links = _frame_records(result.get("links"))
    recs = _frame_records(result.get("reconciliation"))

    evidence: Dict[str, List[dict]] = defaultdict(list)
    case_stage: Dict[str, Dict[str, dict]] = defaultdict(dict)
    all_cases = set()

    for r in events:
        case = _text(r.get("case_id")); kind = _text(r.get("kind")).upper(); code = kind_to_stage.get(kind)
        if not case or not code: continue
        all_cases.add(case)
        evidence[case].append({
            "stage":code,"event":kind,"date":_text(r.get("date")),"amount":_num(r.get("amount")),
            "currency":_text(r.get("currency")),"source":_text(r.get("source")),
            "document":_text(r.get("document")),"reference":_text(r.get("source_event_id")),
            "status":_text(r.get("status")) or "SOURCE_FACT","note":_text(r.get("note")),
        })

    chain_by: Dict[Tuple[str,str], dict] = {}
    chain_stage_map = {
        "PI":"ORDER_REG", "REGISTRATION":"ORDER_REG", "ALLOCATION_REQUEST":"ALLOCATION_QUEUE",
        "QUEUE":"ALLOCATION_QUEUE", "ALLOCATION":"ALLOCATION", "COMMITMENT":"COMMITMENT",
        "FX_BUY":"FX_PURCHASE", "FUNDING":"FUNDING", "PAYMENT":"PAYMENT",
        "SETTLEMENT_RETURN":"SETTLEMENT", "REMAINING_COMMITMENT":"SETTLEMENT",
    }
    for r in chain:
        case = _text(r.get("case_id")); code = chain_stage_map.get(_text(r.get("stage")).upper())
        if case and code:
            all_cases.add(case); chain_by[(case,code)] = r

    for case in sorted(all_cases):
        by_stage = defaultdict(list)
        for e in evidence.get(case, []): by_stage[e["stage"]].append(e)
        for s in stages:
            code=s["code"]; rows=by_stage.get(code,[]); cr=chain_by.get((case,code),{})
            status=_text(cr.get("status")).upper()
            if not status: status="DONE" if rows else "NO_EVIDENCE"
            dates=[_date_value(x.get("date")) for x in rows]; dates=[x for x in dates if x]
            if not dates and _text(cr.get("dates")): dates=[x.strip() for x in _text(cr.get("dates")).split("|") if x.strip()]
            documents=sorted({_text(x.get("document")) for x in rows if _text(x.get("document"))})
            amount_text=_text(cr.get("amounts")) or _amounts(rows)
            case_stage[case][code]={
                "status":status,"status_label":STATUS_LABELS.get(status,status),
                "date":min(dates) if dates else "", "dates":" | ".join(dates),
                "amounts":amount_text, "documents":" | ".join(documents) or _text(cr.get("documents")),
                "gap":_text(cr.get("gap_code")), "detail":_text(cr.get("detail")),
                "event_count":len(rows) if rows else int(_num(cr.get("event_count")) or 0),
            }

    # Links are preserved as explicit evidence; no inferred relationship is added.
    by_event = {_text(r.get("event_id")): r for r in events if _text(r.get("event_id"))}
    traced=[]
    for l in links:
        a=by_event.get(_text(l.get("from_event")),{}); b=by_event.get(_text(l.get("to_event")),{})
        src=kind_to_stage.get(_text(a.get("kind")).upper()); tgt=kind_to_stage.get(_text(b.get("kind")).upper())
        traced.append({
            "case":_text(l.get("source_case")) or _text(a.get("case_id")), "source_stage":src or "",
            "target_stage":tgt or "", "from_event":_text(l.get("from_event")), "to_event":_text(l.get("to_event")),
            "from_amount":_text(l.get("from_amount")), "from_currency":_text(l.get("from_currency")),
            "to_amount":_text(l.get("to_amount")), "to_currency":_text(l.get("to_currency")),
            "authorization":_text(l.get("authorization")), "status":_text(l.get("status")),
        })

    # Reconciliation stays attached to settlement; it is evidence, not a synthetic event.
    for r in recs:
        case=_text(r.get("case_id"))
        if not case: continue
        all_cases.add(case)
        evidence[case].append({"stage":"SETTLEMENT","event":"RECONCILIATION","date":_text(r.get("observed_at")),
            "amount":_num(r.get("variance")),"currency":_text(r.get("currency")),"source":_text(r.get("source")),
            "document":_text(r.get("document")),"reference":_text(r.get("measurement_id")),"status":_text(r.get("status")),
            "note":"تطبیق مانده دفتر و Snapshot؛ اختلاف، تراکنش مالی نیست."})

    return _aggregate_payload(stages, case_stage, evidence, traced)


def _normalize_extras(extras: Mapping[str, Any]) -> dict:
    stages=[{"code":c,"label":l,"phase":p} for c,l,p in STAGE56_STAGES]
    timeline=_frame_records(extras.get("fx_stage_timeline")); ledger=_frame_records(extras.get("fx_money_ledger"))
    recon=_frame_records(extras.get("fx_money_reconciliation"))
    case_stage: Dict[str, Dict[str, dict]] = defaultdict(dict); evidence: Dict[str,List[dict]]=defaultdict(list)
    for r in timeline:
        case=_text(r.get("KEY_REG")) or _text(r.get("FX_CASE_KEY")); code=_text(r.get("STAGE_CODE"))
        if not case or not code: continue
        status=_text(r.get("STATUS")).upper() or "NO_EVIDENCE"
        case_stage[case][code]={"status":status,"status_label":STATUS_LABELS.get(status,status),
            "date":_text(r.get("EVENT_DATE")),"dates":_text(r.get("EVENT_DATE")),"amounts":"—",
            "documents":_text(r.get("EVIDENCE")),"gap":"" if status in {"DONE","CURRENT"} else status,
            "detail":("مهلت: "+_text(r.get("DUE_DATE"))+" · "+_text(r.get("DEADLINE_BASIS"))).strip(" ·"),"event_count":1 if _text(r.get("EVENT_DATE")) or _text(r.get("EVIDENCE")) else 0}
    for r in ledger:
        case=_text(r.get("KEY_REG")) or _text(r.get("FX_CASE_KEY")); code=LEDGER_TO_STAGE.get(_text(r.get("EVENT_CODE")).upper())
        if not case or not code: continue
        evidence[case].append({"stage":code,"event":_text(r.get("EVENT_FA")) or _text(r.get("EVENT_CODE")),
            "date":_text(r.get("EVENT_DATE")),"amount":_num(r.get("AMOUNT")),"currency":_text(r.get("CURRENCY")),
            "source":_text(r.get("SOURCE")),"document":_text(r.get("REFERENCE")),"reference":_text(r.get("REFERENCE")),
            "status":_text(r.get("STATUS")) or "SOURCE_FACT","note":_text(r.get("NOTE"))})
    for r in recon:
        case=_text(r.get("KEY_REG")) or _text(r.get("FX_CASE_KEY"));
        if not case: continue
        evidence[case].append({"stage":"SETTLEMENT","event":"تطبیق پول/تعهد","date":_text(r.get("EVENT_DATE")),
            "amount":_num(r.get("VARIANCE")),"currency":_text(r.get("CURRENCY")),"source":_text(r.get("SOURCE")),
            "document":_text(r.get("REFERENCE")),"reference":_text(r.get("REFERENCE")),
            "status":_text(r.get("STATUS")),"note":_text(r.get("DETAIL")) or _text(r.get("NOTE"))})
    # Fill amount/document detail from ledger without overwriting timeline status.
    for case, rows in evidence.items():
        by=defaultdict(list)
        for e in rows: by[e["stage"]].append(e)
        for code, evs in by.items():
            cs=case_stage.setdefault(case,{}).setdefault(code,{"status":"DONE","status_label":"دارای شاهد","date":"","dates":"","amounts":"—","documents":"","gap":"","detail":"","event_count":0})
            cs["amounts"]=_amounts(evs); cs["event_count"]=max(int(cs.get("event_count") or 0),len(evs))
            docs=sorted({_text(e.get("document")) for e in evs if _text(e.get("document"))});
            if docs: cs["documents"]=" | ".join(docs)
            ds=sorted({_text(e.get("date")) for e in evs if _text(e.get("date"))});
            if ds and not cs.get("date"): cs["date"]=ds[0]; cs["dates"]=" | ".join(ds)
    for case in set(case_stage)|set(evidence):
        for s in stages:
            case_stage[case].setdefault(s["code"],{"status":"NO_EVIDENCE","status_label":"بدون شاهد در منبع","date":"","dates":"","amounts":"—","documents":"","gap":"NO_EVIDENCE","detail":"شاهدی برای این مرحله در محدوده انتخابی موجود نیست؛ این به معنی انجام‌نشدن مرحله نیست.","event_count":0})
    return _aggregate_payload(stages, case_stage, evidence, [])


def _aggregate_payload(stages: List[dict], case_stage: Mapping[str,Mapping[str,dict]], evidence: Mapping[str,List[dict]], traced: List[dict]) -> dict:
    cases=sorted(set(case_stage)|set(evidence)); stage_stats=[]; edges=[]
    order=[s["code"] for s in stages]
    label={s["code"]:s["label"] for s in stages}
    for s in stages:
        code=s["code"]; vals=[case_stage.get(c,{}).get(code,{}) for c in cases]
        observed=sum(1 for v in vals if int(v.get("event_count") or 0)>0 or v.get("status") in {"DONE","CURRENT","MATCH","OBSERVED"})
        bad=sum(1 for v in vals if _status_token(v.get("status","")) in {"critical","warning"})
        worst=_worst_status(v.get("status","") for v in vals)
        stage_stats.append({**s,"cases":observed,"total_cases":len(cases),"exceptions":bad,"status":worst,
            "status_label":STATUS_LABELS.get(worst,worst),"coverage":0 if not cases else round(observed*100/len(cases),1)})
    for a,b in zip(order,order[1:]):
        pairs=[]; count=0; deviating=False
        for c in cases:
            x=case_stage.get(c,{}).get(a,{}); y=case_stage.get(c,{}).get(b,{})
            if int(x.get("event_count") or 0)>0 and int(y.get("event_count") or 0)>0:
                count+=1
                dx=_date_value(x.get("date")); dy=_date_value(y.get("date"))
                if dx and dy:
                    try:
                        delta=(pd.Timestamp(dy)-pd.Timestamp(dx)).total_seconds()/3600
                        if delta>=0: pairs.append(delta)
                    except Exception: pass
            if _status_token(y.get("status","")) in {"critical","warning"}: deviating=True
        med=statistics.median(pairs) if pairs else None
        text=f"{count} پرونده" + (f" · میانه {med/24:.1f} روز" if med is not None else "")
        edges.append({"source":a,"target":b,"count":count,"median_hours":med,"deviating":deviating,"critical":False,"label":text})
    nodes=[{"id":s["code"],"label":s["label"],"count":s["cases"],"status":_status_token(s["status"]),
            "hint":f"پوشش {s['coverage']}٪"} for s in stage_stats]
    return {"stages":stages,"stage_stats":stage_stats,"nodes":nodes,"edges":edges,"cases":cases,
            "case_stage":{k:dict(v) for k,v in case_stage.items()},"evidence":{k:list(v) for k,v in evidence.items()},"traced":traced,
            "labels":label}


def build_cashflow_process_html(*, result: Optional[Mapping[str,Any]]=None, extras: Optional[Mapping[str,Any]]=None,
                                instance_id: str="cashflow", compact: bool=False) -> str:
    """Return an interactive RTL process + drill-down fragment.

    Exactly one of ``result`` (standalone cashflow engine output) or ``extras``
    (pipeline stage-56 extras) should be supplied.
    """
    payload=_normalize_extras(extras or {}) if extras is not None else _normalize_result(result or {})
    uid="".join(ch if ch.isalnum() else "_" for ch in str(instance_id))[:60] or "cashflow"
    svg_frequency=_flow_renderer(payload["nodes"],payload["edges"],mode="frequency")
    svg_performance=_flow_renderer(payload["nodes"],payload["edges"],mode="performance")
    # The pipeline strip is also rendered by the exact system_flow module from the
    # supplied Process Explorer ZIP.  We namespace its generic class names before
    # embedding so it cannot collide with the surrounding report CSS.
    kit = Path(__file__).resolve().parents[2] / "process-mining-ui-kit"
    if str(kit) not in sys.path:          # idempotent; see _flow_renderer
        sys.path.append(str(kit))
    from pm_ui.charts.system_flow import system_flow_html
    sys_stages=[]
    for i, stg in enumerate(payload.get("stage_stats", []), 1):
        sys_stages.append({
            "label": stg.get("label", stg.get("code", "")),
            "icon": str(i),
            "sub": f"{stg.get('phase','')} · {stg.get('cases',0)}/{stg.get('total_cases',0)} پرونده",
            "status": _status_token(stg.get("status", "")),
        })
    pipeline_html = system_flow_html(sys_stages)
    # Namespace the kit's intentionally generic CSS/HTML class names.
    for a,b in [("pipeline","cfp-pipeline"),("stage","cfp-sys-stage"),("card","cfp-sys-card"),
                ("arrow","cfp-sys-arrow"),("icon","cfp-sys-icon"),("label","cfp-sys-label"),("sub","cfp-sys-sub")]:
        pipeline_html=pipeline_html.replace(f'class="{a}"',f'class="{b}"').replace(f'.{a}',f'.{b}')
    safe_payload=json.dumps(payload,ensure_ascii=False,separators=(",",":"),default=str).replace("</","<\\/")
    # The SVG and pipeline strip come from the Process Explorer kit. The surrounding controls add drill-down only.
    style=f"""
<style>
#{uid}.cfp{{font-family:'IRANSansWeb','IRANSansX','IRANSans','YekanBakh','Vazirmatn',Tahoma,'Segoe UI',Arial,sans-serif;color:#0b1f33;direction:rtl}}
#{uid} *{{box-sizing:border-box}} #{uid} .cfp-head{{display:flex;gap:12px;align-items:end;justify-content:space-between;flex-wrap:wrap;margin:0 0 12px}}
#{uid} .cfp-title{{font-size:18px;font-weight:800}} #{uid} .cfp-sub{{font-size:12px;color:#5a6b79;margin-top:4px;max-width:900px}}
#{uid} .cfp-modebar{{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 8px}} #{uid} .cfp-modebar button{{border:1px solid #cdd9de;background:#fff;color:#0b1f33;border-radius:999px;padding:7px 12px;font:inherit;font-size:11px;cursor:pointer}} #{uid} .cfp-modebar button[aria-pressed=\"true\"]{{background:#e7f1f2;border-color:#0a7c86;color:#075e65;font-weight:800}}
#{uid} .cfp-pipeline-wrap{{border:1px solid #dbe3e7;border-radius:14px;background:#f9fbfb;padding:8px;margin:8px 0 12px;overflow:auto}}
#{uid} .cfp-graph[hidden]{{display:none!important}}
#{uid} label{{font-size:11px;color:#5a6b79;display:grid;gap:5px}} #{uid} select{{min-width:220px;min-height:40px;border:1px solid #cdd9de;border-radius:10px;padding:8px;background:#fff;color:#0b1f33;font:inherit}}
#{uid} .cfp-flow{{border:1px solid #dbe3e7;border-radius:14px;background:#fff;overflow-x:auto;padding:8px;scrollbar-width:thin}}
#{uid} .cfp-flow svg{{min-width:{max(1180,190*max(6,len(payload['nodes'])))}px}} #{uid} .cfp-flow .node{{cursor:pointer}} #{uid} .cfp-flow .node.is-selected rect:first-child{{stroke:#0A7C86!important;stroke-width:3px!important;filter:drop-shadow(0 5px 10px rgba(10,124,134,.18))}}
#{uid} .cfp-flow .edge{{transition:opacity .15s}} #{uid} .cfp-grid{{display:grid;grid-template-columns:minmax(280px,.8fr) minmax(0,1.7fr);gap:12px;margin-top:12px}}
#{uid} .cfp-card{{border:1px solid #dbe3e7;border-radius:14px;background:#fff;padding:14px;min-width:0}} #{uid} .cfp-card h4{{margin:0 0 10px;font-size:14px}} #{uid} .cfp-kv{{display:grid;grid-template-columns:110px 1fr;gap:7px 10px;font-size:12px}}
#{uid} .cfp-kv b{{color:#5a6b79;font-weight:600}} #{uid} .cfp-chip{{display:inline-flex;padding:3px 8px;border-radius:999px;background:#eef2f4;font-size:11px;margin:2px}}
#{uid} .cfp-tablewrap{{overflow:auto;border:1px solid #dbe3e7;border-radius:14px;margin-top:12px;background:#fff;max-height:{'360px' if compact else '520px'}}}
#{uid} table{{width:100%;border-collapse:collapse;font-size:11.5px;min-width:960px}} #{uid} th{{position:sticky;top:0;background:#f7f9fa;z-index:1;text-align:right;padding:9px;border-bottom:1px solid #dbe3e7;white-space:nowrap}} #{uid} td{{padding:8px 9px;border-bottom:1px solid #edf1f3;vertical-align:top}} #{uid} tbody tr{{cursor:pointer}} #{uid} tbody tr:hover,#${uid} tbody tr.is-selected{{background:#e7f1f2}}
#{uid} .cfp-empty{{color:#5a6b79;font-size:12px;padding:12px}} #{uid} .cfp-status{{font-weight:700}} #{uid} .cfp-evidence{{margin-top:12px}}
#{uid} .cfp-legend{{display:flex;gap:8px;flex-wrap:wrap;font-size:10.5px;color:#5a6b79;margin:8px 0}} #{uid} .cfp-legend span{{background:#f7f9fa;border:1px solid #e5ecef;border-radius:999px;padding:4px 8px}}
@media(max-width:760px){{#{uid} .cfp-grid{{grid-template-columns:1fr}} #{uid} select{{min-width:0;width:100%}}}}
</style>""".replace("#$", "#")
    opts="".join(f'<option value="{escape(c,quote=True)}">{escape(c)}</option>' for c in payload["cases"])
    html=f"""<section id="{uid}" class="cfp" data-gsi-cashflow-process="1">
{style}
<div class="cfp-head"><div><div class="cfp-title">نقشه الگوریتمی مسیر پول و تعهد</div><div class="cfp-sub">گراف از Process Explorer خود GSI ساخته شده است. ضخامت مسیر = تعداد پرونده دارای شاهد در دو مرحله؛ برچسب یال = تعداد و میانه زمان گذار. نبود شاهد به معنی انجام‌نشدن مرحله نیست.</div></div><label>پرونده برای Drill-down<select data-role="case"><option value="">نمای کل فرآیند</option>{opts}</select></label></div>
<div class="cfp-legend"><span>کلیک روی هر مرحله = جزئیات</span><span>کلیک روی ردیف جدول = همان مرحله</span><span>ارزهای مختلف هرگز با هم جمع نمی‌شوند</span><span>خط‌چین = شکاف/استثنا در مسیر</span></div>
<div class="cfp-pipeline-wrap" aria-label="خط لوله کلان مسیر پول">{pipeline_html}</div>
<div class="cfp-modebar" role="group" aria-label="حالت نمایش گراف"><button type="button" data-mode="frequency" aria-pressed="true">شدت مسیر / تعداد پرونده</button><button type="button" data-mode="performance" aria-pressed="false">عملکرد / زمان گذار</button></div>
<div class="cfp-flow cfp-graph" data-role="graph-frequency">{svg_frequency}</div>
<div class="cfp-flow cfp-graph" data-role="graph-performance" hidden>{svg_performance}</div>
<div class="cfp-grid"><div class="cfp-card"><h4>جزئیات مرحله انتخاب‌شده</h4><div data-role="detail" class="cfp-empty">یک مرحله از نمودار یا جدول را انتخاب کنید.</div></div><div class="cfp-card"><h4>شواهد مالی / اسنادی مرحله</h4><div data-role="evidence" class="cfp-empty">در نمای کل، مرحله‌ای را انتخاب کنید؛ یا یک پرونده انتخاب کنید تا سند، مبلغ، منبع و وضعیت نمایش داده شود.</div></div></div>
<div class="cfp-tablewrap"><table aria-label="مسیر پول"><thead><tr><th>#</th><th>مرحله</th><th>فاز</th><th>وضعیت</th><th>تاریخ شاهد</th><th>مبلغ‌ها برحسب ارز</th><th>سند / Evidence</th><th>شکاف / توضیح</th></tr></thead><tbody data-role="path"></tbody></table></div>
<div class="cfp-tablewrap cfp-evidence"><table aria-label="ارتباط‌های مستند پول"><thead><tr><th>پرونده</th><th>از مرحله</th><th>به مرحله</th><th>مبلغ مبدأ</th><th>مبلغ مقصد</th><th>مجوز/وضعیت</th><th>شناسه رویدادها</th></tr></thead><tbody data-role="trace"></tbody></table></div>
<script type="application/json" data-role="payload">{safe_payload}</script>
<script>(function(){{
 const root=document.getElementById({json.dumps(uid)}); if(!root||root.dataset.ready==='1')return;root.dataset.ready='1';
 const D=JSON.parse(root.querySelector('[data-role=payload]').textContent),sel=root.querySelector('[data-role=case]'),path=root.querySelector('[data-role=path]'),detail=root.querySelector('[data-role=detail]'),evidence=root.querySelector('[data-role=evidence]'),trace=root.querySelector('[data-role=trace]');
 let stage=''; const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c]));
 const statusLabel=s=>({json.dumps(STATUS_LABELS,ensure_ascii=False)}[s]||s||'—');
 function rowData(code){{const c=sel.value; if(c)return (D.case_stage[c]||{{}})[code]||{{status:'NO_EVIDENCE',status_label:'بدون شاهد در منبع',amounts:'—'}}; const z=D.stage_stats.find(x=>x.code===code)||{{}}; return {{status:z.status,status_label:z.status_label,date:'',amounts:'—',documents:'',gap:z.exceptions?z.exceptions+' پرونده نیازمند بررسی':'',detail:'پوشش '+(z.coverage??0)+'٪ · '+(z.cases??0)+' از '+(z.total_cases??0)+' پرونده',event_count:z.cases||0}};}}
 function renderPath(){{path.innerHTML='';D.stages.forEach((s,i)=>{{const r=rowData(s.code),tr=document.createElement('tr');tr.dataset.stage=s.code;if(s.code===stage)tr.classList.add('is-selected');tr.innerHTML='<td>'+(i+1)+'</td><td><b>'+esc(s.label)+'</b></td><td>'+esc(s.phase||'')+'</td><td class="cfp-status">'+esc(r.status_label||statusLabel(r.status))+'</td><td>'+esc(r.dates||r.date||'—')+'</td><td>'+esc(r.amounts||'—')+'</td><td>'+esc(r.documents||'—')+'</td><td>'+esc([r.gap,r.detail].filter(Boolean).join(' · ')||'—')+'</td>';tr.addEventListener('click',()=>selectStage(s.code));path.appendChild(tr)}})}}
 function renderTrace(){{const c=sel.value;const rows=(D.traced||[]).filter(x=>!c||x.case===c);trace.innerHTML='';if(!rows.length){{trace.innerHTML='<tr><td colspan="7" class="cfp-empty">ارتباط صریح مبلغی در این محدوده ثبت نشده است؛ رابطه حدسی ساخته نمی‌شود.</td></tr>';return}} rows.forEach(x=>{{const tr=document.createElement('tr');tr.innerHTML='<td>'+esc(x.case)+'</td><td>'+esc(D.labels[x.source_stage]||x.source_stage||'—')+'</td><td>'+esc(D.labels[x.target_stage]||x.target_stage||'—')+'</td><td>'+esc((x.from_amount||'—')+' '+(x.from_currency||''))+'</td><td>'+esc((x.to_amount||'—')+' '+(x.to_currency||''))+'</td><td>'+esc([x.authorization,x.status].filter(Boolean).join(' · ')||'—')+'</td><td>'+esc((x.from_event||'')+' → '+(x.to_event||''))+'</td>';trace.appendChild(tr)}})}}
 function selectStage(code){{stage=code;root.querySelectorAll('.cfp-flow .node').forEach(n=>n.classList.toggle('is-selected',n.dataset.id===code));renderPath();renderDetail()}}
 function renderDetail(){{if(!stage){{detail.className='cfp-empty';detail.textContent='یک مرحله از نمودار یا جدول را انتخاب کنید.';evidence.className='cfp-empty';evidence.textContent='مرحله‌ای انتخاب نشده است.';return}} const s=D.stages.find(x=>x.code===stage)||{{code:stage,label:stage}},r=rowData(stage),c=sel.value;detail.className='cfp-kv';detail.innerHTML='<b>مرحله</b><span>'+esc(s.label)+'</span><b>وضعیت</b><span>'+esc(r.status_label||statusLabel(r.status))+'</span><b>تاریخ</b><span>'+esc(r.dates||r.date||'—')+'</span><b>مبلغ‌ها</b><span>'+esc(r.amounts||'—')+'</span><b>اسناد</b><span>'+esc(r.documents||'—')+'</span><b>شکاف</b><span>'+esc(r.gap||'—')+'</span><b>توضیح</b><span>'+esc(r.detail||'—')+'</span>';
   let rows=[]; if(c)rows=(D.evidence[c]||[]).filter(x=>x.stage===stage); else D.cases.forEach(k=>{{(D.evidence[k]||[]).forEach(x=>{{if(x.stage===stage)rows.push(Object.assign({{case:k}},x))}})}}); evidence.className=''; if(!rows.length){{evidence.innerHTML='<div class="cfp-empty">شاهد ردیفی برای این مرحله در محدوده انتخابی موجود نیست.</div>';return}} const cap=rows.slice(0,250);evidence.innerHTML='<div class="cfp-tablewrap" style="margin:0"><table><thead><tr><th>پرونده</th><th>رویداد</th><th>تاریخ</th><th>مبلغ</th><th>ارز</th><th>منبع</th><th>سند/مرجع</th><th>وضعیت/یادداشت</th></tr></thead><tbody>'+cap.map(x=>'<tr><td>'+esc(x.case||c||'')+'</td><td>'+esc(x.event||'')+'</td><td>'+esc(x.date||'—')+'</td><td>'+esc(x.amount??'—')+'</td><td>'+esc(x.currency||'')+'</td><td>'+esc(x.source||'—')+'</td><td>'+esc(x.document||x.reference||'—')+'</td><td>'+esc([x.status,x.note].filter(Boolean).join(' · ')||'—')+'</td></tr>').join('')+'</tbody></table></div>'+(rows.length>250?'<div class="cfp-empty">۲۵۰ ردیف اول نمایش داده شد؛ جدول اصلی گزارش همه شواهد را نگه می‌دارد.</div>':''); }}
 root.querySelectorAll('.cfp-modebar button').forEach(b=>b.addEventListener('click',()=>{{const mode=b.dataset.mode;root.querySelectorAll('.cfp-modebar button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));root.querySelector('[data-role=graph-frequency]').hidden=mode!=='frequency';root.querySelector('[data-role=graph-performance]').hidden=mode!=='performance';if(stage)selectStage(stage);}}));
 sel.addEventListener('change',()=>{{stage='';renderPath();renderTrace();renderDetail();}}); root.querySelectorAll('.cfp-flow .node').forEach(n=>{{n.setAttribute('tabindex','0');n.setAttribute('role','button');n.addEventListener('click',()=>selectStage(n.dataset.id));n.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' '){{e.preventDefault();selectStage(n.dataset.id)}}}})}});renderPath();renderTrace();
}})();</script>
</section>"""
    return html


__all__=["build_cashflow_process_html","RESULT_STAGES","STAGE56_STAGES"]

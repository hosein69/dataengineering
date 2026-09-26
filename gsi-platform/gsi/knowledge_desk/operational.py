# -*- coding: utf-8 -*-
"""Read-only semantic DWH context for the Knowledge Desk.

The chatbot never queries the flat report as a source of truth. Operational
answers are assembled from published Business DWH entities, direct-evidence
relations and native-grain facts. No fuzzy joins or synthetic process events.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from ..warehouse.store import Warehouse, loads

_ID_RE = re.compile(r"(?<!\d)(\d{6,16})(?!\d)")


def _clean(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"nan", "none", "<na>"} else s


def _payload(value: str) -> Dict[str, Any]:
    try:
        x = loads(value)
        return x if isinstance(x, dict) else {}
    except Exception:
        try:
            x = json.loads(value)
            return x if isinstance(x, dict) else {}
        except Exception:
            return {}


def _pick(d: Dict[str, Any], *names: str) -> str:
    for n in names:
        v = _clean(d.get(n))
        if v:
            return v
    return ""


def _published_run(conn) -> str:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='dwh_entity'").fetchone() and not conn.execute("SELECT 1 FROM sqlite_master WHERE name='wh_semantic_snapshot'").fetchone():
        raise RuntimeError("LEGACY_SEMANTIC_REBUILD_REQUIRED")
    row = conn.execute("SELECT run_id FROM wh_current WHERE slot='dwh'").fetchone()
    if not row:
        row = conn.execute("SELECT run_id FROM wh_current WHERE slot='report'").fetchone()
    return str(row[0]) if row else ""


def _entity_types(conn, key: str) -> List[str]:
    return [str(r[0]) for r in conn.execute(
        "SELECT entity_type FROM dwh_entity WHERE business_key=? ORDER BY entity_type", (key,)
    ).fetchall()]


def _relations(conn, entity_type: str, key: str) -> List[Dict[str, str]]:
    rows = conn.execute(
        """SELECT left_type,left_key,right_type,right_key,source,frame,rule,evidence_count
           FROM dwh_relation
           WHERE (left_type=? AND left_key=?) OR (right_type=? AND right_key=?)
           ORDER BY source,frame,left_type,right_type""",
        (entity_type, key, entity_type, key),
    ).fetchall()
    out=[]
    for r in rows:
        if r[0] == entity_type and r[1] == key:
            ot, ok = str(r[2]), str(r[3])
        else:
            ot, ok = str(r[0]), str(r[1])
        out.append({"type":ot,"key":ok,"source":str(r[4]),"frame":str(r[5]),
                    "rule":str(r[6]),"evidence_count":int(r[7] or 0)})
    return out


def _pr_semantic(conn, pr: str, run_id: str) -> Dict[str, Any]:
    pr_rows = conn.execute(
        "SELECT pr_item,material_key,payload,last_seen_run FROM dwh_fact_sap_pr_item WHERE pr_key=? ORDER BY pr_item", (pr,)
    ).fetchall()
    po_rows = conn.execute(
        "SELECT po_key,po_item,pr_item,material_key,payload,last_seen_run FROM dwh_fact_sap_po_item WHERE pr_key=? ORDER BY po_key,po_item", (pr,)
    ).fetchall()
    wf_rows = conn.execute(
        "SELECT event_date,payload,last_seen_run FROM dwh_fact_sap_workflow WHERE pr_key=? ORDER BY COALESCE(event_date,''),workflow_key", (pr,)
    ).fetchall()
    rels = _relations(conn, "PR", pr)
    orders = sorted({x["key"] for x in rels if x["type"] == "ORDER"})
    materials = sorted({x["key"] for x in rels if x["type"] == "MATERIAL"} | {str(r[1]) for r in pr_rows if r[1]})
    pos = sorted({x["key"] for x in rels if x["type"] == "PO"} | {str(r[0]) for r in po_rows if r[0]})

    # Follow only explicit ORDER->REG evidence; this is a graph traversal, not a new relation.
    regs=set()
    reg_evidence=[]
    for order in orders:
        for x in _relations(conn, "ORDER", order):
            if x["type"] == "REG":
                regs.add(x["key"]); reg_evidence.append({"order":order, **x})

    pr_payloads = [_payload(r[2]) for r in pr_rows]
    latest_pr = max(pr_payloads, key=lambda p: (_pick(p, "SAP_CHANGED_ON_ISO", "SAP_RELEASE_DATE_ISO", "SAP_REQUISITION_DATE_ISO"), str(p.get("SAP_PR_ITEM", "")))) if pr_payloads else {}
    latest_wf = _payload(wf_rows[-1][1]) if wf_rows else {}
    status = _pick(latest_wf, "SAP_PROCESSING_STATUS", "SAP_OVERALL_RELEASE", "SAP_PACK_PACKED") or _pick(latest_pr, "SAP_PROCESSING_STATUS", "SAP_OVERALL_RELEASE")
    release = _pick(latest_pr, "SAP_RELEASE_DATE_ISO")
    req_date = _pick(latest_pr, "SAP_REQUISITION_DATE_ISO")
    supplier = _pick(latest_pr, "SAP_SUPPLIER_NAME")

    alloc=0; commitments=0
    for reg in regs:
        alloc += int(conn.execute("SELECT count(*) FROM dwh_fact_ntsw_allocation_request WHERE reg_key=?", (reg,)).fetchone()[0])
        commitments += int(conn.execute("SELECT count(*) FROM dwh_fact_ntsw_commitment WHERE reg_key=?", (reg,)).fetchone()[0])

    expert_evidence = [x for x in rels if x["type"] == "ORDER" and x["source"] == "moghavemat"]
    return {
        "kind":"PR", "key":pr, "run_id":run_id,
        "pr_items":len(pr_rows), "po_items":len(po_rows), "workflow_events":len(wf_rows),
        "workflow_observations":len(wf_rows), "evidence_state":"OBSERVED", "confidence":"SOURCE_OBSERVED",
        "item_evidence":[{"business_key":f"{pr}/{row[0]}", "value":_payload(row[2]), "source":"sap/pr_items", "as_of_run":run_id, "evidence_date":_pick(_payload(row[2]), "SAP_CHANGED_ON_ISO", "SAP_REQUISITION_DATE_ISO")} for row in pr_rows],
        "materials":materials, "pos":pos, "orders":orders, "regs":sorted(regs),
        "expert_intake":bool(expert_evidence), "allocation_requests":alloc, "commitments":commitments,
        "status":status, "requisition_date":req_date, "release_date":release, "supplier":supplier,
        "relations":rels, "reg_evidence":reg_evidence,
    }


def _generic_semantic(conn, typ: str, key: str, run_id: str) -> Dict[str, Any]:
    rels=_relations(conn,typ,key)
    return {"kind":typ,"key":key,"run_id":run_id,"relations":rels}


def _render(x: Dict[str, Any]) -> str:
    typ=x["kind"]; key=x["key"]
    if typ == "PR":
        lines=[f"PR {key} در Business DWH منتشرشده مشاهده شد."]
        if x.get("requisition_date"): lines.append(f"تاریخ درخواست استاندارد: {x['requisition_date']}.")
        lines.append(f"اقلام PR: {x['pr_items']}؛ مشاهدات Workflow: {x['workflow_events']}؛ اقلام PO مرتبط: {x['po_items']}.")
        lines.append("ورود به فایل کارشناسان: " + ("مشاهده شده" if x.get("expert_intake") else "شاهد مستقیم مشاهده نشد" ) + ".")
        if x.get("status"): lines.append(f"آخرین وضعیت SAP قابل مشاهده: {x['status']}.")
        if x.get("release_date"): lines.append(f"Release Date: {x['release_date']}.")
        if x.get("materials"): lines.append("Material: " + ", ".join(x["materials"][:12]) + (" …" if len(x["materials"])>12 else "") + ".")
        if x.get("pos"): lines.append("اسناد خرید/PO: " + ", ".join(x["pos"][:12]) + (" …" if len(x["pos"])>12 else "") + ".")
        if x.get("orders"): lines.append("ORDERهای دارای شاهد مستقیم: " + ", ".join(x["orders"][:12]) + ".")
        if x.get("regs"): lines.append("REGهای قابل دستیابی از روابط مستقیم ORDER→REG: " + ", ".join(x["regs"][:12]) + ".")
        if x.get("regs"): lines.append(f"درخواست‌های تخصیص NTSW: {x['allocation_requests']}؛ تعهدهای ارزی موجود: {x['commitments']}.")
        lines.append(f"As-of published DWH run: {x['run_id']}.")
        lines.append("Source: sap/pr_items, sap/po_items, sap/workflow_rows؛ جزئیات روابط در semantic.relations.")
        lines.append("توجه: نبود شاهد به معنی انجام‌نشدن قطعی مرحله نیست؛ فقط یعنی در DWH منتشرشده شاهد قابل‌استناد مشاهده نشده است.")
        return "\n".join(lines)
    rels=x.get("relations") or []
    lines=[f"شناسه {key} به‌عنوان {typ} در Business DWH مشاهده شد."]
    if rels:
        grouped={}
        for r in rels: grouped.setdefault(r['type'],set()).add(r['key'])
        for t,vals in sorted(grouped.items()): lines.append(f"{t}: " + ", ".join(sorted(vals)[:20]) + ".")
    else:
        lines.append("رابطه مستقیم دیگری برای این شناسه مشاهده نشد.")
    lines.append(f"As-of published DWH run: {x['run_id']}.")
    return "\n".join(lines)


def operational_search(question: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Return structured operational hits for explicit business identifiers."""
    ids=[]
    explicit = re.findall(r"\b(?:ORDER|BL|MATERIAL|PO|PR|REG)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9._/-]*)", str(question or ""), re.I)
    for x in _ID_RE.findall(str(question or "")) + explicit:
        if x not in ids: ids.append(x)
    if not ids:
        return []
    try:
        wh=Warehouse(initialize=False)
        if not wh.path.exists(): return []
        with wh.read_db() as conn:
            run_id=_published_run(conn)
            if not run_id: return []
            out=[]
            for key in ids[:8]:
                for typ in _entity_types(conn,key):
                    sem=_pr_semantic(conn,key,run_id) if typ=="PR" else _generic_semantic(conn,typ,key,run_id)
                    out.append({
                        "title": f"DWH {typ} {key}",
                        "path": f"dwh://{typ}/{key}",
                        "source": "Published Business DWH",
                        "source_type": "operational_dwh",
                        "body": _render(sem),
                        "semantic": sem,
                        "score": -1000.0,
                    })
                    if len(out) >= limit: return out
            return out
    except Exception as exc:
        raise RuntimeError("OPERATIONAL_SOURCE_UNAVAILABLE") from exc


def operational_chunks(limit: int = 20000) -> List[Dict[str, Any]]:
    """Compact published-PR snapshot for the zero-server static chatbot."""
    try:
        wh=Warehouse(initialize=False)
        if not wh.path.exists(): return []
        with wh.read_db() as conn:
            run_id=_published_run(conn)
            if not run_id: return []
            prs=[str(r[0]) for r in conn.execute("SELECT pr_key FROM dwh_dim_pr ORDER BY pr_key LIMIT ?", (int(limit),)).fetchall()]
            out=[]
            for i,pr in enumerate(prs,1):
                sem=_pr_semantic(conn,pr,run_id)
                out.append({"id":f"op-pr-{i}","title":f"وضعیت عملیاتی PR {pr}","source":"Published Business DWH",
                            "source_type":"operational_dwh","chunk_no":0,"body":_render(sem)})
            return out
    except Exception as exc:
        raise RuntimeError("OPERATIONAL_SOURCE_UNAVAILABLE") from exc

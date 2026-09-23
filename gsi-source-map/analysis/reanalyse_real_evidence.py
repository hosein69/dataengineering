#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-derive the key map from a real evidence pack using the reviewed classifier.

The upstream profiler produced the real pack (41 frames, 631,576 rows) before the
defects in MAP_DEFECTS.md were fixed, so its `process_key_index` is contaminated:
it published quantity, type and amount columns as business keys. This re-runs the
classification over the headers already in the pack, so a corrected map is
available without re-reading the source workbooks.

It emits SCHEMA-LEVEL FACTS ONLY — headers, roles, counts, ratios. No business
value from any sample row is read or written, because the published output goes
to a public repository.

    python reanalyse_real_evidence.py --evidence evidence.txt --output analysis_out
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixed"))
from gsi_source_profiler import (                                    # noqa: E402
    classify_column, column_side, KEY_ROLES, NON_BUSINESS_KEY_ROLES,
)

# What the GSI package's adapters actually read, from gsi/config/sources.yaml
# and each adapter's `sheets` setting in V29.7.7 RC1.
GSI_CONSUMES = {
    "SAP": ["Data"],
    "Commercial_Expert": ["Expert Data"],
    "NTSW": ["Release Commitment", "Allocation", "Import License", "Import Licence"],
    "Oracle": ["<all sheets, physical-cell reader>"],
    "IL_Append": ["Append"],
    "Abbasi": ["BLs Tracking"],
    "SATA": ["Sata Tracking"],
    "FX_Transactions": ["<all sheets, physical-cell reader>"],
    "FX_Transactions_1405": ["<not in registry>"],
    "Sea_Clearance": ["<largest data sheet>"],
    "Land_Clearance": ["<largest data sheet>"],
    "Air_Clearance": ["<largest data sheet>"],
    "Customs": ["Cottage Tracking"],
    "Credit_Dept": ["PURCREDIT"],
}


def load_evidence(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return json.loads(raw[raw.index("{"):])


def frame_id(p: dict) -> str:
    return f"{p['source']}/{p['sheet']}"


def reclassify(profiles: list[dict]) -> list[dict]:
    """Corrected roles per frame, from headers only."""
    out = []
    for p in profiles:
        cols = []
        for h in p["headers"]:
            c = classify_column(str(h))
            cols.append({"column": str(h), "key_role": c["key_role"],
                         "measure_roles": c["measure_roles"], "side": c["side"]})
        by_role: dict[str, list[str]] = {}
        for c in cols:
            if c["key_role"]:
                by_role.setdefault(c["key_role"], []).append(c["column"])
        out.append({"frame": frame_id(p), "source": p["source"], "sheet": p["sheet"],
                    "rows": p["row_count"], "columns": p["column_count"],
                    "key_roles": by_role,
                    "unclassified": [c["column"] for c in cols
                                     if not c["key_role"] and not c["measure_roles"]],
                    "columns_detail": cols})
    return out


def compare_key_index(old_index: dict, new_frames: list[dict]) -> dict:
    """What the upstream map published as a joinable key vs what survives review."""
    old: dict[str, set[tuple[str, str]]] = {}
    for role, refs in old_index.get("roles", {}).items():
        for r in refs:
            old.setdefault(role, set()).add((f"{r['source']}/{r['sheet']}", r["column"]))
    new: dict[str, set[tuple[str, str]]] = {}
    for f in new_frames:
        for role, cols in f["key_roles"].items():
            if role in NON_BUSINESS_KEY_ROLES:
                continue
            for c in cols:
                new.setdefault(role, set()).add((f["frame"], c))
    report = {}
    for role in sorted(set(old) | set(new)):
        o, n = old.get(role, set()), new.get(role, set())
        withdrawn = sorted(o - n)
        report[role] = {
            "published_by_upstream": len(o), "retained_after_review": len(n),
            "withdrawn": [{"frame": f, "column": c,
                           "why": "; ".join(classify_column(c)["measure_roles"])
                                  or (f"reclassified to {classify_column(c)['key_role']}"
                                      if classify_column(c)["key_role"] else "no role")}
                          for f, c in withdrawn],
            "added": sorted([{"frame": f, "column": c} for f, c in (n - o)],
                            key=lambda x: (x["frame"], x["column"])),
        }
    return report


def topology_gap(profiles: list[dict]) -> list[dict]:
    """Sheets that exist in the real workbooks but no adapter reads."""
    gaps = []
    for p in profiles:
        consumed = GSI_CONSUMES.get(p["source"], [])
        explicit = [c for c in consumed if not c.startswith("<")]
        if explicit:
            status = "CONSUMED" if str(p["sheet"]) in explicit else "NOT_CONSUMED"
        else:
            status = "CONSUMED_BY_STRATEGY" if consumed else "SOURCE_NOT_IN_REGISTRY"
        gaps.append({"frame": frame_id(p), "source": p["source"], "sheet": p["sheet"],
                     "rows": p["row_count"], "columns": p["column_count"],
                     "adapter_reads": consumed or ["<none>"], "status": status})
    return sorted(gaps, key=lambda g: -g["rows"])


def conflict_candidates(frames: list[dict]) -> list[dict]:
    """Frames where two columns claim one key role — a merge would fabricate lineage.

    Header-level only: the pack does not carry the per-row values needed to say
    whether they actually disagree, so this names the frames to re-profile.
    """
    out = []
    for f in frames:
        for role, cols in sorted(f["key_roles"].items()):
            if len(cols) > 1 and role not in NON_BUSINESS_KEY_ROLES:
                out.append({"frame": f["frame"], "role": role, "columns": cols,
                            "sides": sorted({column_side(c) for c in cols})})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--output", default="analysis_out")
    args = ap.parse_args()
    ev = load_evidence(Path(args.evidence))
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    profiles = ev["profiles"]

    frames = reclassify(profiles)
    index_diff = compare_key_index(ev.get("process_key_index", {}), frames)
    gaps = topology_gap(profiles)
    conflicts = conflict_candidates(frames)

    corrected_index: dict[str, list[dict]] = {}
    for f in frames:
        for role, cols in f["key_roles"].items():
            if role in NON_BUSINESS_KEY_ROLES:
                continue
            for c in cols:
                corrected_index.setdefault(role, []).append(
                    {"frame": f["frame"], "column": c, "side": column_side(c)})

    payload = {
        "source_evidence": {"format": ev.get("format"), "generated_at": ev.get("generated_at"),
                            "profiled_frames": ev.get("profiled_frames"),
                            "total_native_rows": ev.get("total_native_rows"),
                            "errors": ev.get("errors")},
        "disclaimer": "Schema-level facts only. No business value from any sample row is "
                      "included. Roles are heuristic until confirmed by the source owner.",
        "corrected_key_index": corrected_index,
        "upstream_vs_reviewed": index_diff,
        "topology_gap": gaps,
        "same_role_conflict_candidates": conflicts,
        "frames": [{k: v for k, v in f.items() if k != "columns_detail"} for f in frames],
    }
    (out / "corrected_key_map.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    withdrawn_total = sum(len(v["withdrawn"]) for v in index_diff.values())
    not_consumed = [g for g in gaps if g["status"] in ("NOT_CONSUMED", "SOURCE_NOT_IN_REGISTRY")]
    print(f"frames: {len(frames)} | rows: {ev.get('total_native_rows'):,}")
    print(f"key columns withdrawn from the join map: {withdrawn_total}")
    print(f"frames not read by any adapter: {len(not_consumed)} "
          f"({sum(g['rows'] for g in not_consumed):,} rows)")
    print(f"same-role conflict candidates: {len(conflicts)}")
    print(f"written: {out/'corrected_key_map.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Explicit Excel export from the last published warehouse snapshot.

This module never reads operational source workbooks and never runs ETL. It is
safe to use while Streamlit is open because it only hydrates the published mart.
"""
from __future__ import annotations
from pathlib import Path
from datetime import date


def export_published_snapshot(output_path=None, ref_date=None, max_rows=200000):
    from .service import last_report
    from .store import Warehouse
    from ..studio_core.excel_export import build_custom_excel
    exact = last_report(ref_date) if ref_date else None
    stored = exact or last_report(None)
    if stored is None:
        raise RuntimeError("No published GSI snapshot exists. Run refresh first.")
    df, main, extras, _official = stored
    data = main if main is not None and not main.empty else df
    published_ref = str(extras.get("published_reference_date") or ref_date or date.today().isoformat())
    if output_path is None:
        root = Warehouse(initialize=False).path.parent / "exports"
        output_path = root / f"{published_ref}_GSI_PUBLISHED_SNAPSHOT.xlsx"
    output_path = Path(output_path)
    process_keys = ("eventlog", "case_table", "bottlenecks", "variants",
                    "conformance_cases", "conformance_root_causes")
    process_tables = {}
    for key in process_keys:
        try:
            value = extras.get(key)
        except Exception:
            value = None
        if value is not None:
            process_tables[key] = value
    modules = ["criticality", "case_alerts", "resistance", "commitment",
               "org", "expert", "process", "table"]
    return build_custom_excel(
        data, output_path, modules, published_ref, max_rows=int(max_rows),
        selected_fields=list(data.columns), process_tables=process_tables,
        allow_official_overwrite=False)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Export Excel from published GSI warehouse snapshot; no ETL/source read")
    ap.add_argument("--output")
    ap.add_argument("--date", dest="ref_date")
    ap.add_argument("--max-rows", type=int, default=200000)
    ns = ap.parse_args(argv)
    out = export_published_snapshot(ns.output, ns.ref_date, ns.max_rows)
    print(out)
    return 0

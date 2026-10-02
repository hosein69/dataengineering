# -*- coding: utf-8 -*-
"""Command-line access to the local AIBL SQLite warehouse.

Examples
--------
python -m aibl warehouse stats
python -m aibl warehouse runs --limit 20
python -m aibl warehouse case CASE-123
python -m aibl warehouse bottlenecks --org "گمرک"
python -m aibl warehouse prune --keep 365
"""
from __future__ import annotations

import argparse
import json
from typing import Sequence

import pandas as pd

from .historical_store import warehouse_from_settings


def _print_df(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        print("(بدون داده)")
    else:
        with pd.option_context("display.max_columns", 40, "display.width", 220, "display.max_colwidth", 70):
            print(df.to_string(index=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m aibl warehouse", description="SQLite Warehouse / Process Log")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("stats", help="آمار انبار داده")
    r = sub.add_parser("runs", help="فهرست اجراها")
    r.add_argument("--limit", type=int, default=30)
    c = sub.add_parser("case", help="Timeline و تغییرات یک پرونده")
    c.add_argument("case_key")
    c.add_argument("--run-id")
    b = sub.add_parser("bottlenecks", help="گلوگاه‌های transition از SQL")
    b.add_argument("--run-id")
    b.add_argument("--org")
    b.add_argument("--expert")
    b.add_argument("--limit", type=int, default=50)
    a = sub.add_parser("audit", help="Audit/runtime log")
    a.add_argument("--run-id")
    a.add_argument("--limit", type=int, default=100)
    l = sub.add_parser("lineage", help="Lineage سورس‌های یک اجرا")
    l.add_argument("--run-id")
    k = sub.add_parser("kpi", help="روند KPI")
    k.add_argument("metric", nargs="?")
    k.add_argument("--limit", type=int, default=366)
    pr = sub.add_parser("prune", help="حذف snapshotهای قدیمی")
    pr.add_argument("--keep", type=int, default=365)
    sub.add_parser("vacuum", help="فشرده‌سازی فایل SQLite")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    wh = warehouse_from_settings()
    if args.command == "stats":
        print(json.dumps(wh.stats(), ensure_ascii=False, indent=2))
    elif args.command == "runs":
        _print_df(wh.list_runs(args.limit))
    elif args.command == "case":
        print("\n── Timeline ──")
        _print_df(wh.case_timeline(args.case_key, args.run_id))
        print("\n── Snapshot changes ──")
        _print_df(wh.case_changes(args.case_key))
    elif args.command == "bottlenecks":
        _print_df(wh.process_bottlenecks(args.run_id, org_unit=args.org, resource=args.expert, limit=args.limit))
    elif args.command == "audit":
        _print_df(wh.audit_entries(args.limit, args.run_id))
    elif args.command == "lineage":
        _print_df(wh.source_lineage(args.run_id))
    elif args.command == "kpi":
        _print_df(wh.kpi_trend(args.metric, args.limit))
    elif args.command == "prune":
        print(json.dumps(wh.prune(args.keep), ensure_ascii=False, indent=2))
    elif args.command == "vacuum":
        wh.vacuum(); print("VACUUM: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

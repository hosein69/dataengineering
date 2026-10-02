"""Read-only comparison of selected source workbooks and newer matching variants.

Run on the machine that can access the configured source directories:
    python -m tools.source_variant_review --output variant_review.json

This never changes the source registry or publishes a warehouse run.
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import json
from pathlib import Path

import pandas as pd

from gsi.config.sources import get_source
from gsi.core.text import normalize_col_name, clean_order_ref, clean_bl


KEY_CANDIDATES = {
    "abbasi": (("بارنامه", "شماره بارنامه"), clean_bl),
    "moghavemat": (("Order No. (Our Reference)", "Order No.\n(Our Reference)"), clean_order_ref),
}


def inspect(path: Path, sheet_names: list[str], source: str) -> dict:
    result = {"file": path.name, "bytes": path.stat().st_size,
              "modified_ns": path.stat().st_mtime_ns}
    try:
        with pd.ExcelFile(path) as book:
            result["sheets"] = book.sheet_names
            available = {name.strip().casefold(): name for name in book.sheet_names}
            choice = next((available[n.strip().casefold()] for n in sheet_names
                           if n.strip().casefold() in available), None)
            if choice is None:
                result["error"] = "NO_CONTRACTED_SHEET"
                return result
            frame = book.parse(choice, dtype=str)
        frame.columns = [normalize_col_name(c) for c in frame.columns]
        result.update(sheet=choice, rows=len(frame), headers=list(frame.columns))
        names, normalize = KEY_CANDIDATES[source]
        by_name = {normalize_col_name(c).casefold(): c for c in frame.columns}
        col = next((by_name.get(normalize_col_name(n).casefold()) for n in names
                    if normalize_col_name(n).casefold() in by_name), None)
        if col is None:
            result["error"] = "NO_CONTRACTED_BUSINESS_KEY_HEADER"
        else:
            result["key_header"] = col
            keys = frame[col].map(normalize)
            result["populated_key_rows"] = int(keys.ne("").sum())
            result["unique_keys"] = int(keys[keys.ne("")].nunique())
            # Keep private business identifiers out of the summary file.
            result["_keys"] = set(keys[keys.ne("")])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def review(source: str) -> dict:
    spec = get_source(source)
    base_names = {n.casefold() for n in spec.opt("file_names", [])}
    paths = sorted((Path(p) for p in glob.glob(str(Path(spec.folder) / "*.xls*"))
                    if fnmatch.fnmatch(Path(p).stem.casefold(), spec.pattern.casefold())),
                   key=lambda p: p.stat().st_mtime_ns, reverse=True)
    entries = []
    for path in paths:
        if path.name.startswith("~$"):
            continue
        record = inspect(path, list(spec.sheets), source)
        record["role"] = "BASE" if path.name.casefold() in base_names else "VARIANT_REVIEW_ONLY"
        entries.append(record)
    bases = [e for e in entries if e["role"] == "BASE" and "_keys" in e]
    base_keys = bases[0]["_keys"] if len(bases) == 1 else set()
    for entry in entries:
        keys = entry.pop("_keys", set())
        if base_keys and entry["role"] != "BASE" and keys:
            entry["key_overlap_with_base"] = len(keys & base_keys)
            entry["keys_only_in_variant"] = len(keys - base_keys)
            entry["keys_only_in_base"] = len(base_keys - keys)
    return {"source": source, "expected_base_files": sorted(base_names),
            "base_usable": len(bases) == 1, "files": entries,
            "publication_policy": "BASE_ONLY; variants are read-only review evidence"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {name: review(name) for name in ("abbasi", "moghavemat")}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

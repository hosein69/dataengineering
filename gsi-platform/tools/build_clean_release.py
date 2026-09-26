# -*- coding: utf-8 -*-
"""Build a clean distributable GSI ZIP without runtime data/cache artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_PARTS = {
    "__pycache__", ".pytest_cache", ".git", ".DS_Store", "_demo_html_out",
    "offline_feedback", "output", "logs", "D:\\GSI_DATA", ".venv", "venv",
}
SKIP_NAMES = {
    "PACKAGE_SHA256_FINAL_20260925.json",
    "PACKAGE_SHA256.json",
    "generate_demo_html.py",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".sqlite", ".sqlite-wal", ".sqlite-shm", ".pkl", ".pickle"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def allowed(rel: Path) -> bool:
    if any(part in SKIP_PARTS for part in rel.parts):
        return False
    if rel.name in SKIP_NAMES:
        return False
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return False
    return True


def collect(root: Path):
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and allowed(p.relative_to(root))
    )


def _version() -> str:
    import sys
    sys.path.insert(0, str(ROOT))
    from gsi.factsheet import VERSION
    return VERSION


def build(output: Path, manifest_name: str = "PACKAGE_SHA256.json") -> dict:
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix="gsi_release_") as td:
        stage = Path(td) / "GSI"
        stage.mkdir(parents=True)
        for src in collect(ROOT):
            rel = src.relative_to(ROOT)
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        manifest_path = stage / manifest_name
        hashes = {
            str(p.relative_to(stage)).replace(os.sep, "/"): sha256(p)
            for p in collect(stage)
            if p.name != manifest_name
        }
        manifest_path.write_text(json.dumps({
            "schema": 1,
            "release": f"GSI {_version()}",
            "generated": __import__("datetime").date.today().isoformat(),
            "files": hashes,
        }, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(stage.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(stage).as_posix())

    return {"zip": str(output), "sha256": sha256(output), "files": len(hashes) + 1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("output", nargs="?", default=str(ROOT.parent / f"GSI_{_version().replace('.', '_')}.zip"))
    args = ap.parse_args()
    result = build(Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

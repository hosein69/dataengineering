import argparse
import io
from pathlib import Path

import pandas as pd

from .core import build_bundle, publish_bundle, digest
from .patterns import load_spec

p = argparse.ArgumentParser(description="Offline CSV event report; no email sending")
p.add_argument("--events", required=True)
p.add_argument("--publish-root", required=True)
p.add_argument("--reference", required=True)
p.add_argument("--title", default="گزارش فرآیند")
p.add_argument("--pattern-config", help="Optional explicit JSON event-pattern config; observational only")
a = p.parse_args()
b = Path(a.events).read_bytes()
if len(b) > 20 * 1024 * 1024:
    p.error("Input exceeds 20 MiB")
pattern_spec = load_spec(a.pattern_config) if a.pattern_config else None
files = build_bundle(
    pd.read_csv(io.BytesIO(b), dtype={"_CASE_KEY": str, "CASE_KEY": str}),
    source="sha256:" + digest(b), reference=a.reference, title=a.title,
    pattern_spec=pattern_spec,
)
print(publish_bundle(files, a.publish_root))

# -*- coding: utf-8 -*-
"""OP-06: producer/consumer reachability audit for the DERIVED translation map."""
import sys, os, re, json, importlib, pkgutil
sys.path.insert(0, os.environ["PKG"])
from gsi.adapters.base import REGISTRY
import gsi.adapters as A
for m in pkgutil.iter_modules(A.__path__):
    importlib.import_module("gsi.adapters." + m.name)
from gsi.stages.s20_derive import DERIVED

produced = set()
for key, cls in REGISTRY.items():
    pref = cls.prefix
    for attr in dir(cls):
        v = getattr(cls, attr, None)
        if isinstance(v, dict) and attr.endswith("MAP"):
            produced |= {f"{pref}_{k}" for k in v}
    src = open(os.path.join(os.environ["PKG"], "gsi", "adapters",
          cls.__module__.split(".")[-1] + ".py"), encoding="utf-8").read()
    for m in re.finditer(r'(?:self\.)?p\(\s*[\'"]([A-Z0-9_]+)[\'"]', src):
        produced.add(f"{pref}_{m.group(1)}")
    for m in re.finditer(r'[\'"]((?:%s)_[A-Z0-9_]+)[\'"]' % pref, src):
        produced.add(m.group(1))

unreachable = {}
for target, (cands, default, numeric) in DERIVED.items():
    miss = [c for c in cands if re.match(r'^[A-Z]{2,4}_', c) and c not in produced]
    if len(miss) == len(cands) and cands:
        unreachable[target] = {"candidates": cands, "default": default, "numeric": numeric}
print(json.dumps({
  "derived_targets": len(DERIVED),
  "fully_unreachable_targets": len(unreachable),
  "detail": unreachable,
}, ensure_ascii=False, indent=1))

from __future__ import annotations
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(); inv=Path(sys.argv[2]); out=Path(sys.argv[3])
sys.path.insert(0,str(root))
from offline_validation.source_probe import probe_ntsw_semantics
inventory=json.loads(inv.read_text(encoding='utf-8'))
result=probe_ntsw_semantics(root,inventory)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

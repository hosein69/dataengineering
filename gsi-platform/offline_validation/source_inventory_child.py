from __future__ import annotations
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(); data_dir=sys.argv[2]; out=Path(sys.argv[3])
sys.path.insert(0,str(root))
from offline_validation.source_probe import probe_sources
result=probe_sources(root,data_dir)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

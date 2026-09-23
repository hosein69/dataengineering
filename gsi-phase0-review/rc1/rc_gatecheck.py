import sys, os, json, glob
sys.path.insert(0, os.environ["PKG"]); sys.path.insert(0, os.path.join(os.environ["PKG"], "tests"))
import test_validation as tv   # module sets up synthetic inputs on import
res = tv.test_pipeline()
from gsi.config.settings import SETTINGS
rid = res.extras.get("warehouse_run_id")
print(json.dumps({
 "gate_passed": res.extras.get("quality_gate_passed"),
 "blocking_codes": res.extras.get("quality_gate_blocking_codes"),
 "run_id": rid,
 "dashboard_path": res.dashboard_path,
 "extract_paths": len(res.extract_paths or []),
 "OUTPUT_DIR": SETTINGS.OUTPUT_DIR,
 "runs_dir_exists": os.path.isdir(os.path.join(SETTINGS.OUTPUT_DIR, "runs", str(rid))),
 "files": sorted(os.path.basename(p) for p in glob.glob(os.path.join(SETTINGS.OUTPUT_DIR,"runs",str(rid),"*"))),
}, ensure_ascii=False, indent=1))

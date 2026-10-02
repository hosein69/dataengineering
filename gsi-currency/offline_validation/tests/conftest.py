from __future__ import annotations
import json, os, sys
from pathlib import Path
import pytest
ROOT = Path(os.environ.get('GSI_DIAGNOSTIC_TARGET', Path(__file__).resolve().parents[2])).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RESULTS=[]

@pytest.fixture(autouse=True)
def isolate_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv('GSI_DWH_PATH', str(tmp_path / 'diag.sqlite'))
    monkeypatch.setenv('GSI_OFFLINE_DIAGNOSTIC', '1')
    try:
        from datetime import date
        from gsi.rulebook import get_rulebook
        get_rulebook(reload=True, as_of=date(2026, 9, 24))
    except Exception:
        pass

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield; rep=outcome.get_result()
    if rep.when=='call' or (rep.when in ('setup','teardown') and rep.failed):
        RESULTS.append({'id':item.nodeid,'phase':rep.when,'outcome':rep.outcome,'seconds':rep.duration,
          'expectation':(getattr(item,'function',None).__doc__ or '').strip() if getattr(item,'function',None) else '',
          'failure':str(rep.longrepr) if rep.failed else ''})

def pytest_sessionfinish(session,exitstatus):
    dest=os.environ.get('GSI_DIAGNOSTIC_RESULTS')
    if not dest: return
    p=Path(dest); p.mkdir(parents=True,exist_ok=True)
    (p/'test_results.json').write_text(json.dumps({'exitstatus':exitstatus,'target':str(ROOT),'tests':RESULTS},ensure_ascii=False,indent=2),encoding='utf-8')

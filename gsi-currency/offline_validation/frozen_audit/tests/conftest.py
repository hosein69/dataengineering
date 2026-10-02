"""Independent harness. Never imports fixtures, tests or expected outputs from GSI tests."""
import os, sys, json
from pathlib import Path
import pytest
TARGET=Path(os.environ['GSI_AUDIT_TARGET']).resolve()
sys.path.insert(0,str(TARGET))
RESULTS=[]
@pytest.fixture(autouse=True)
def isolated_io(tmp_path,monkeypatch):
    monkeypatch.setenv('GSI_DWH_PATH',str(tmp_path/'isolated.sqlite'))
    from datetime import date
    from gsi.rulebook import get_rulebook
    get_rulebook(reload=True,as_of=date(2026,9,24))

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield
    rep=outcome.get_result()
    if rep.when=='call' or (rep.when in ('setup','teardown') and rep.failed):
        RESULTS.append({'id':item.nodeid,'phase':rep.when,'outcome':rep.outcome,
          'seconds':rep.duration,'expectation':(item.function.__doc__ or '').strip(),
          'failure':str(rep.longrepr) if rep.failed else ''})

def pytest_sessionfinish(session,exitstatus):
    dest=Path(os.environ['GSI_AUDIT_RESULTS']);dest.mkdir(parents=True,exist_ok=True)
    (dest/'test_results.json').write_text(json.dumps({'exitstatus':exitstatus,'target':str(TARGET),
      'tests':RESULTS},indent=2,ensure_ascii=False),encoding='utf-8')

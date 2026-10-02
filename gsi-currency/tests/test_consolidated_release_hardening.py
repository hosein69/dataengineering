"""Regressions identified in FINAL/AUDIT1/AUDIT2 comparison."""
import importlib.util
import sqlite3
from pathlib import Path
from unittest.mock import patch
import pytest
from gsi.warehouse.store import Warehouse
from gsi.warehouse.writer_lock import WriterLock, WarehouseBusyError
from gsi.learning.anythingllm import AnythingLLMClient, AnythingLLMConfig
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('diagnostic_runner',ROOT/'offline_validation/run_offline_diagnostic.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

def test_reset_refuses_active_writer(tmp_path):
    wh=Warehouse(tmp_path/'test.sqlite')
    with wh.run({'test':True}): pass
    with WriterLock(wh.path.with_suffix('.writer.lock'),timeout=.1):
        with pytest.raises(WarehouseBusyError): wh.reset(confirm=True,keep_backup=False)
    with wh.db() as con: assert con.execute('SELECT count(*) FROM wh_run').fetchone()[0]==1

def test_sql_reset_quotes_names(tmp_path,monkeypatch):
    wh=Warehouse(tmp_path/'test.sqlite')
    with wh.db() as c: c.execute('CREATE TABLE "odd""name" (id INTEGER)')
    monkeypatch.setattr('gsi.warehouse.store._unlink_with_retry',lambda p:False)
    assert wh.reset(confirm=True,keep_backup=False)['emptied_in_place']
    with wh.db() as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('SELECT name FROM sqlite_master WHERE name=?',('odd"name',)).fetchone() is None

def test_undeletable_database_never_unlinks_live_sidecars(tmp_path,monkeypatch):
    wh=Warehouse(tmp_path/'test.sqlite');held=sqlite3.connect(wh.path)
    try:
        held.execute('PRAGMA journal_mode=WAL')
        held.execute('CREATE TABLE live_wal (id INTEGER)');held.commit()
        touched=[]
        def refuse(p): touched.append(p);return False
        monkeypatch.setattr('gsi.warehouse.store._unlink_with_retry',refuse)
        wh.reset(confirm=True,keep_backup=False)
        assert touched==[wh.path]
        assert held.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally: held.close()

def test_historical_transaction_closes_on_commit_and_rollback(tmp_path):
    from gsi.warehouse.historical_store import Warehouse as Historical
    wh=Historical(tmp_path/'history.sqlite')
    with wh.transaction() as c: c.execute('CREATE TABLE lifecycle(id INTEGER)')
    with pytest.raises(sqlite3.ProgrammingError): c.execute('SELECT 1')
    with pytest.raises(RuntimeError):
        with wh.transaction() as c:
            c.execute('INSERT INTO lifecycle VALUES (1)');raise RuntimeError('abort')
    with pytest.raises(sqlite3.ProgrammingError): c.execute('SELECT 1')
    with wh.transaction() as c: assert c.execute('SELECT count(*) FROM lifecycle').fetchone()[0]==0

@pytest.mark.parametrize('value',[None,[],[None],[{}],[''],[{'title':''}]])
def test_evidence_client_withholds_uncited_answer(value):
    client=AnythingLLMClient(AnythingLLMConfig('http://localhost','test','workspace'))
    with patch.object(client,'_call',return_value={'textResponse':'unverified claim','sources':value}) as call:
        result=client.ask_evidence('question')
    assert result['status']=='INSUFFICIENT_EVIDENCE'
    assert 'unverified claim' not in str(result)
    assert call.call_args.args[2]['mode']=='query'

@pytest.mark.parametrize('key',['sources','citations','sourceDocuments'])
def test_citations_are_not_factual_verification(key):
    client=AnythingLLMClient(AnythingLLMConfig('http://localhost','test','workspace'))
    with patch.object(client,'_call',return_value={'textResponse':'answer',key:[{'title':'manual'}]}):
        result=client.ask_evidence('question')
    assert result['status']=='CITATIONS_PRESENT' and result['verified'] is False

def test_runner_executes_script_entrypoint(tmp_path):
    p=tmp_path/'legacy.py';p.write_text('if __name__ == "__main__":\n    raise SystemExit(1)\n')
    assert runner.internal_command(p,tmp_path/'tmp')[-1]==str(p)
    assert 'pytest' not in runner.internal_command(p,tmp_path/'tmp')

@pytest.mark.parametrize('broken',[{}, {'exit_code':1,'failed':0,'total_results':173}, {'error':'crash'}, {'exit_code':0,'total_results':0}])
def test_gate_blocks_missing_or_crashed_audit(tmp_path,monkeypatch,broken):
    monkeypatch.setattr(runner,'verify_manifest',lambda:{'status':'PASS'})
    monkeypatch.setattr(runner,'knowledge_check',lambda:{'status':'PASS'})
    result=runner.summarize(tmp_path,{'independent':broken},{'sources':[{'status':'FOUND'}]},{'status':'OK'})
    assert result['release_gate']=='HOLD'
    assert 'INDEPENDENT_SEMANTIC_FAILURES' in result['blockers']

def test_gate_blocks_skipped_tests_and_absent_data(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'verify_manifest',lambda:{'status':'PASS'})
    monkeypatch.setattr(runner,'knowledge_check',lambda:{'status':'PASS'})
    steps={'independent':{'exit_code':0,'total_results':173},'extended':{'exit_code':0,'total_results':77},'internal':{'skipped':True}}
    result=runner.summarize(tmp_path,steps,{}, {'status':'NOT_RUN'})
    assert {'INTERNAL_VALIDATION_INCOMPLETE','SOURCE_INVENTORY_INCOMPLETE','NTSW_ACCEPTANCE_INCOMPLETE'}<=set(result['blockers'])

def test_dependency_check_catches_wrong_pinned_version(monkeypatch):
    import importlib.metadata as md
    original=md.version
    monkeypatch.setattr(md,'version',lambda name:'0.2.0' if name=='streamlit-sortables' else original(name))
    result=runner.dependency_check()
    assert result['status']=='FAIL'
    assert any(p['package']=='streamlit-sortables' for p in result['problems'])

def test_diagnostic_runs_scripts_and_isolates_database(tmp_path,monkeypatch):
    import os
    root=tmp_path/'package';(root/'tests').mkdir(parents=True)
    for name,code in [('test_a.py',0),('legacy_test_b.py',1)]:
        (root/'tests'/name).write_text('import os\nif __name__ == "__main__":\n    print(os.environ["GSI_DWH_PATH"])\n    raise SystemExit('+str(code)+')\n')
    monkeypatch.setattr(runner,'ROOT',root)
    out=tmp_path/'out';out.mkdir()
    result=runner.run_internal_per_file(out,dict(os.environ),10)
    assert result['passed_files']==1 and result['failed_files']==1 and result['no_test_files']==0
    assert (out/'internal/test_a.log').read_text() != (out/'internal/legacy_test_b.log').read_text()

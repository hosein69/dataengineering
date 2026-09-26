"""Independent review counterexamples, 29.7.7-rc1."""
import pandas as pd
import pytest
from gsi.warehouse.store import Warehouse, QualityGateBlockedError
from gsi.warehouse.business_dwh import build
from gsi.warehouse.reliability import Check, BLOCK, validate_frame
from gsi.resolve.process_evidence import build_process_inventory, _state_from_text
from gsi.dataio.merge import safe_merge
from gsi.adapters.a60_finance import SapAdapter

def sap_rows(status='OLD'):
 return pd.DataFrame([{'Purchase Requisition':'6500029693','Item of requisition':'10','Material':'PRMAT','Processing status':status,'Changed On':'2026-01-01','po.Purchasing Document':'4500000001','po.Item':'10','po.Purchase Requisition':'6500029693','po.Material':'POMAT'}])
def publish(wh,sources):
 with wh.run({'test':'rc'}) as rid:build(wh,sources,rid)
 wh.publish(rid)
 return rid

def test_blocked_run_isolation(tmp_path,monkeypatch):
 from gsi.cashflow.dwh import _published_source_frames
 from gsi.knowledge_desk.operational import operational_search
 wh=Warehouse(tmp_path/'w.sqlite');monkeypatch.setenv('GSI_DWH_PATH',str(wh.path))
 sources={'sap':SapAdapter().transform({'Data':sap_rows()}),'ntsw':{'commitment':pd.DataFrame([{'KEY_REG':'88000001','NTSW_BALANCE':50}])}}
 first=publish(wh,sources);before=operational_search('PR 6500029693')[0]
 with wh.run({'blocked':True}) as second:
  sources['sap']=SapAdapter().transform({'Data':sap_rows('NEW_BLOCKED')});build(wh,sources,second)
  wh.record_quality(second,[Check('test','BLOCK',BLOCK,False,{})])
 with pytest.raises(QualityGateBlockedError):wh.publish(second)
 assert operational_search('PR 6500029693')[0]==before
 frames,rid=_published_source_frames(wh)
 assert rid==first and frames['ntsw']['commitment'].iloc[0]['NTSW_BALANCE']==50

def test_published_omission_preserves_history(tmp_path):
 wh=Warehouse(tmp_path/'w.sqlite');first=publish(wh,{'sap':SapAdapter().transform({'Data':sap_rows()})});publish(wh,{})
 with wh.read_db() as c:assert c.execute('SELECT count(*) FROM dwh_fact_sap_pr_item').fetchone()[0]==0
 with wh.db() as c:assert c.execute('SELECT count(*) FROM snap_dwh_fact_sap_pr_item WHERE snapshot_run=?',(first,)).fetchone()[0]==1

def test_no_publication_no_public_evidence(tmp_path):
 wh=Warehouse(tmp_path/'w.sqlite')
 with wh.run({}) as rid:build(wh,{'sap':SapAdapter().transform({'Data':sap_rows()})},rid)
 with wh.read_db() as c:assert c.execute('SELECT count(*) FROM dwh_entity').fetchone()[0]==0

def test_replay_relation_counts(tmp_path):
 wh=Warehouse(tmp_path/'w.sqlite');s={'abbasi':{'main':pd.DataFrame([{'KEY_ORDER':'A','KEY_BL':'BL1'}])}}
 publish(wh,s);publish(wh,s)
 with wh.read_db() as c:assert c.execute('SELECT max(evidence_count) FROM dwh_relation').fetchone()[0]==1

def test_shared_dimensions_do_not_merge():
 obs,cases,m=build_process_inventory({'abbasi':{'main':pd.DataFrame([{'KEY_ORDER':'A','KEY_MATERIAL':'M','KEY_EMP':'E','KEY_BL':'BL1'},{'KEY_ORDER':'B','KEY_MATERIAL':'M','KEY_EMP':'E','KEY_BL':'BL2'}])}})
 assert len(cases)==2 and set(cases.ORDER_COUNT)=={1}

def test_duplicate_orphan_preservation():
 obs,_,_=build_process_inventory({'abbasi':{'main':pd.DataFrame([{'KEY_ORDER':'A'},{'KEY_ORDER':'A'},{'KEY_ORDER':''}])}})
 assert sum(obs.STAGE_CODE=='SOURCE_OBSERVATION')==3
 assert sum(obs.EVIDENCE_STATE=='ORPHAN_NO_BUSINESS_KEY')==1

def test_downstream_gap():
 obs,_,m=build_process_inventory({'abbasi':{'main':pd.DataFrame([{'KEY_ORDER':'A','KEY_BL':'BL1'}])}})
 assert 'SHIPMENT' in set(obs.STAGE_CODE) and 'EVIDENCE_GAP' in set(m.STATUS)
 assert 'PLANNING_PR' not in set(obs.STAGE_CODE)

@pytest.mark.parametrize('status,expected',[('مورد تایید','POSITIVE_OBSERVED'),('در گردش','OBSERVED'),('تایید نشده','NEGATIVE_OBSERVED'),('مورد بررسی','OBSERVED')])
def test_polarity(status,expected):assert _state_from_text(status)==expected

@pytest.mark.parametrize('balance',[0,50])
def test_balance_not_settlement(balance):
 obs,_,_=build_process_inventory({'ntsw':{'commitment':pd.DataFrame([{'KEY_REG':'88000001','NTSW_BALANCE':balance}])}})
 assert 'SETTLEMENT' not in set(obs.STAGE_CODE)

def test_swift_not_payment():
 obs,_,_=build_process_inventory({'credit':{'main':pd.DataFrame([{'KEY_ORDER':'A','CRD_SWIFT_DATE':'2026-01-01'}])}})
 assert 'PAYMENT' not in set(obs.STAGE_CODE) and 'SWIFT_SENT' in set(obs.STAGE_CODE)

@pytest.mark.parametrize('left,right',[(('',''),('','')),((None,None),(None,None)),(('A|B',''),('A','B|')),(('A',None),('A',None))])
def test_null_and_delimiter_keys(left,right):
 l=pd.DataFrame([dict(zip(['A','B'],left))]);r=pd.DataFrame([dict(zip(['A','B'],right))]);r['VALUE']=99
 out=safe_merge(l,r,['A','B'],'rc')
 assert 'VALUE' not in out or out.VALUE.isna().all()

def test_po_own_identity(tmp_path):
 raw=sap_rows();raw['po.Purchase Requisition']='6500029999';raw['po.Item of requisition']='90'
 wh=Warehouse(tmp_path/'w.sqlite');publish(wh,{'sap':SapAdapter().transform({'Data':raw})})
 with wh.read_db() as c:
  fact=c.execute('SELECT pr_key,pr_item,material_key FROM dwh_fact_sap_po_item').fetchone()
  assert fact[0]=='6500029999' and fact[2]=='POMAT'
  assert c.execute("SELECT count(*) FROM dwh_relation WHERE left_type='PR' AND left_key='6500029693' AND right_type='PO'").fetchone()[0]==0

def test_no_hub_product(tmp_path):
 wh=Warehouse(tmp_path/'w.sqlite');publish(wh,{'ntsw':{'import_license':pd.DataFrame([{'KEY_REG_FILE':'F','KEY_REG':'R1'},{'KEY_REG_FILE':'F','KEY_REG':'R2'}])},'ilappend':{'main':pd.DataFrame([{'KEY_REG_FILE':'F','KEY_ORDER':'A'},{'KEY_REG_FILE':'F','KEY_ORDER':'B'}])}})
 with wh.read_db() as c:
  rows=c.execute('SELECT * FROM dwh_registration_hub').fetchall()
  assert len(rows)==4 and not any(reg and order for _,reg,order in rows)

def test_nullable_uniqueness():
 checks=validate_frame('sap/pr_items',pd.DataFrame([{'KEY_PR':'6500029693','SAP_PR_ITEM':''}]*2))
 assert any(x.code=='GRAIN_UNIQUENESS' and not x.passed for x in checks)

def test_legacy_schema_upgrade(tmp_path):
 import sqlite3
 path=tmp_path/'w.sqlite'
 with sqlite3.connect(path) as c:c.executescript('CREATE TABLE wh_meta(key TEXT PRIMARY KEY,value TEXT); PRAGMA user_version=1;')
 wh=Warehouse(path)
 with wh.db() as c:assert c.execute("SELECT 1 FROM sqlite_master WHERE name='wh_quality_check'").fetchone()

def test_download_rerun_contract():
 import ast
 from pathlib import Path
 tree=ast.parse((Path(__file__).parents[1]/'app/warehouse_view.py').read_text())
 calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='download_button']
 assert len(calls)==2
 assert all(any(k.arg=='on_click' and isinstance(k.value,ast.Constant) and k.value.value=='ignore' for k in n.keywords) for n in calls)

def test_missing_process_summary_blocks_before_files(tmp_path,monkeypatch):
 from types import SimpleNamespace
 from datetime import date
 from gsi.warehouse.bridge import run_pipeline
 monkeypatch.setenv('GSI_DWH_PATH',str(tmp_path/'gate.sqlite'))
 empty=pd.DataFrame();result=SimpleNamespace(df=empty,main=empty,to_resolve=empty,excluded=empty,extras={},dashboard_path='')
 def run(flag):
  assert flag is False
  return result
 def forbidden(*args,**kwargs):raise AssertionError('Files must not be written before passing quality gate')
 pipeline=SimpleNamespace(today=date(2026,9,22),sources={},_run_warehouse=run,build_report=forbidden)
 with pytest.raises(QualityGateBlockedError):run_pipeline(pipeline,True,'test')
 assert not list(tmp_path.glob('*.xlsx'))

def test_blocked_schema_does_not_become_baseline(tmp_path):
 from gsi.warehouse.reliability import schema_drift_checks
 wh=Warehouse(tmp_path/'schema.sqlite')
 with wh.run({}) as rid:
  schema_drift_checks(wh,{'x':{'main':pd.DataFrame({'BAD':[1]})}},rid)
  wh.record_quality(rid,[Check('test','BAD',BLOCK,False,{})])
 with pytest.raises(QualityGateBlockedError):wh.publish(rid)
 with wh.db() as c:assert c.execute('SELECT count(*) FROM wh_schema_baseline').fetchone()[0]==0

def test_snapshot_cannot_be_updated(tmp_path):
 import sqlite3
 wh=Warehouse(tmp_path/'s.sqlite');publish(wh,{'sap':SapAdapter().transform({'Data':sap_rows()})})
 with pytest.raises(sqlite3.IntegrityError):
  with wh.db() as c:c.execute("UPDATE snap_dwh_fact_sap_pr_item SET material_key='FORGED'")

def test_backend_error_not_absence(tmp_path,monkeypatch):
 from gsi.knowledge_desk.query import answer
 from gsi.knowledge_desk.config import KnowledgeDeskConfig
 path=tmp_path/'broken.sqlite';path.write_bytes(b'invalid database');monkeypatch.setenv('GSI_DWH_PATH',str(path))
 result=answer(KnowledgeDeskConfig(db_path=str(tmp_path/'kb.sqlite')),'PR 6500029693')
 assert result['status']=='SOURCE_UNAVAILABLE'

def test_kb_outage_then_restoration(tmp_path):
 from gsi.knowledge_desk.indexer import build_index,status
 from gsi.knowledge_desk.config import KnowledgeDeskConfig
 source=tmp_path/'docs';source.mkdir();(source/'policy.md').write_text('Valid documented procurement policy. Keep this evidence during an outage.')
 cfg=KnowledgeDeskConfig(knowledge_path=str(source),db_path=str(tmp_path/'kb.sqlite'))
 build_index(cfg);assert status(cfg)['documents']==1
 source.rename(tmp_path/'offline');build_index(cfg);assert status(cfg)['documents']==1
 (tmp_path/'offline').rename(source);build_index(cfg);assert status(cfg)['documents']==1

def test_mixed_currency_allocation_unknown_and_native_intact():
 from gsi.adapters.a50_ntsw import NtswAdapter
 a=NtswAdapter();p=a.p
 raw=pd.DataFrame([{'KEY_REG':'88000001',p('REQ_ROW'):str(i),p('REQ_AMOUNT'):100,p('REQ_CURRENCY'):cur,p('REQ_DATE'):'2026-01-01',p('APPROVE_DATE'):'',p('ALLOC_DATE'):'',p('ALLOC_STATUS'):'تایید نشده',p('ALLOC_PROCESS'):'',p('REQ_TYPE'):'',p('QUEUE_RANK'):'',p('FX_SOURCE'):'',p('FX_RATE_TYPE'):'',p('FX_RATE_NUMERIC'):None,p('ALLOC_BRANCH'):''} for i,cur in enumerate(['USD','EUR'])])
 ledger=a._allocation_request_ledger(raw);summary=a._agg_allocation(ledger)
 assert len(ledger)==2 and set(ledger[p('REQUEST_STATE')])=={'OPEN'}
 assert pd.isna(summary.iloc[0][p('OPEN_QUEUE_AMOUNT')])

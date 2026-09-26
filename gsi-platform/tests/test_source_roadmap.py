"""Contracts grounded in evidence.txt profiles, not full-data certification."""
import json
from pathlib import Path
import pandas as pd
import pytest
from gsi.adapters.a60_finance import SapAdapter,FxTransactionAdapter,CreditAdapter,IlAppendAdapter
from gsi.adapters.a30_customs import ClearanceAdapter
from gsi.adapters.a50_ntsw import NtswAdapter
from gsi.resolve.process_evidence import _observations
from gsi.config.sources import SourceSpec
from gsi.dataio.reader import _read_targets
@pytest.fixture
def evidence():
 t=(Path(__file__).parents[1]/'review/roadmap/evidence.txt').read_text(encoding='utf-8-sig');return json.loads(t[t.index('{'):])['profiles']
def sample(e,i):
 p=e[i];d=pd.DataFrame(p['sample_rows']);d['_SOURCE_SHEET']=p['sheet'];return d

def test_sap_five_grains_do_not_cross_join(evidence):
 r=SapAdapter().transform({evidence[i]['sheet']:sample(evidence,i) for i in range(5)})
 for f in ['pr_items','po_items','workflow_rows','inbound_deliveries','goods_receipts']:assert len(r[f])==30
 assert r['po_items'].KEY_PO.ne('').all() and r['pr_items'].KEY_PO.eq('').all()
 assert 'SAP_GR_MOVEMENT_TYPE' in r['goods_receipts'] and 'SAP_GR_REFERENCE' in r['goods_receipts']
 assert 'KEY_ORDER' not in r['goods_receipts']
def test_sap_reader_native_sheets(tmp_path,evidence):
 path=tmp_path/'SAP.xlsx'
 with pd.ExcelWriter(path) as w:
  for i in range(5):sample(evidence,i).to_excel(w,sheet_name=evidence[i]['sheet'],index=False)
 spec=SourceSpec(key='sap',folder=str(tmp_path),pattern='*',sheets=['Data'],extra={'native_sheets':['pr','pack','po','inbound','GR']})
 assert set(_read_targets(spec,[str(path)]))=={'pr','pack','po','inbound','GR'}
def test_sap_legacy_data():
 r=SapAdapter().transform({'Data':pd.DataFrame([{'Purchase Requisition':'1234567890','Item of requisition':'10','Material':'IK100'}])})
 assert len(r['pr_items'])==1

def test_fx_two_layouts(evidence):
 r=FxTransactionAdapter().transform({evidence[i]['sheet']:sample(evidence,i) for i in [30,31]});d=r['main']
 assert len(d)+len(r['quarantine'])==60
 row=d.loc[d.KEY_ORDER.eq('105205C')].iloc[0]
 assert row.FX_AMOUNT==1500000 and row.FX_CURRENCY=='USD'
 assert row.FX_SWIFT_AMOUNT==10084859 and row.FX_SWIFT_CURRENCY=='CNY'
 assert row.FX_RECEIPT_DATE=='1405/06/16'
 legacy=d.loc[d['_SOURCE_SHEET'].eq('Sheet1')]
 assert legacy.FX_SWIFT_CURRENCY.fillna('').eq('').all() and legacy.FX_RATE.notna().any()
def test_credit_unknown_swift_currency(evidence):
 d=CreditAdapter().transform({'PURCREDIT':sample(evidence,40)})['main'];row=d.loc[d.KEY_ORDER.eq('PRI-8006')].iloc[0]
 assert row.CRD_CURRENCY=='CNY' and row.CRD_SWIFT_AMOUNT==110000 and not row.CRD_SWIFT_CURRENCY
def test_rial_proforma_not_funding():
 r=_observations({'credit':{'main':pd.DataFrame([{'KEY_REG':'12345678','CRD_RIAL_AMOUNT':10000}])}})
 assert 'FUNDING' not in set(r.STAGE_CODE)
def test_rejected_historical_allocation():
 r=_observations({'ntsw':{'allocation_rows':pd.DataFrame([{'KEY_REG':'12345678','NTSW_REQUEST_STATE':'REJECTED','NTSW_ALLOC_DATE':'1405/01/01'}])}})
 assert 'ALLOCATION' not in set(r.STAGE_CODE)
def test_licence_status_reaches_process(evidence):
 d=NtswAdapter().transform({'Import License':sample(evidence,8)})['import_license']
 assert d.NTSW_STATUS.equals(d.NTSW_LICENSE_STATUS) and d.NTSW_REG_DATE.fillna('').ne('').any()
 r=_observations({'ntsw':{'import_license':d}})
 assert r.loc[r.STAGE_CODE.eq('REGISTRATION'),'OBSERVED_STATUS'].ne('').any()
def test_il_amendment_status(evidence):
 d=IlAppendAdapter().transform({'Append':sample(evidence,16)})['main']
 assert 'IL_STATUS' in d and d.IL_AMENDMENT_NO.fillna('').ne('').any()
def test_clearance_three_layouts(evidence):
 d=pd.concat([sample(evidence,i) for i in [32,34,36]],ignore_index=True)
 r=ClearanceAdapter().transform({'main':d})['main']
 assert len(r)==90 and r.CL_SOURCE_SHEET.nunique()==3
def test_clearance_all_contracted_sheets(tmp_path):
 path=tmp_path/'Clearance.xlsx'
 with pd.ExcelWriter(path) as w:
  pd.DataFrame({'بارنامه':['A'],'پرونده ترخیص':['C1']}).to_excel(w,sheet_name='Sea Clearance',index=False)
  pd.DataFrame({'بارنامه':['B'],'پرونده ترخیص':['C2']}).to_excel(w,sheet_name='Air Clearance',index=False)
  pd.DataFrame({'lookup':list(range(100))}).to_excel(w,sheet_name='Data',index=False)
 spec=SourceSpec(key='clearance',folder=str(tmp_path),pattern='*',sheets=[None],extra={'sheet_strategy':'all_data_sheets','skip_sheets':['Data']})
 r=_read_targets(spec,[str(path)])['main']
 assert len(r)==2 and r['_SOURCE_SHEET'].nunique()==2


def test_actual_negative_return_keeps_negative_sign(evidence):
 r=SapAdapter().transform({'GR':sample(evidence,4)})['goods_receipts']
 returned=r.loc[r.SAP_GR_MOVEMENT_TYPE.eq('122')]
 assert len(returned)>0 and returned.SAP_GR_QTY.lt(0).all()
 assert returned.SAP_GR_SIGNED_QTY.lt(0).all()

def test_mixed_reference_not_promoted_to_order(evidence):
 r=SapAdapter().transform({'po':sample(evidence,2)})['po_items']
 assert r.KEY_ORDER.eq('').all()
 assert r.SAP_ORDER_REFERENCE_CANDIDATE.eq('6100000380').any()

def test_explicit_missing_run_does_not_expand(tmp_path):
 from gsi.warehouse.store import Warehouse
 from gsi.warehouse.fx_obligation import _scoped_file_ids
 wh=Warehouse(tmp_path/'scoped.sqlite')
 with wh.run({'test':True}):wh.blob(b'a','a.xlsx','ntsw','a.xlsx')
 with wh.db() as conn:
  ids,scope=_scoped_file_ids(conn,'NO_SUCH_RUN')
 assert ids==[] and scope=='run:NO_SUCH_RUN'


def test_fx_discovery_keeps_two_sources_excludes_backups(tmp_path):
 from gsi.dataio.reader import find_files
 names=['IKCO, Foreign Exchange Transaction.xlsx','IKCO, Foreign Exchange Transaction, 1405.xlsx']
 for n in names+['IKCO, Foreign Exchange Transaction BACKUP.xlsx']:(tmp_path/n).touch()
 spec=SourceSpec(key='fx_transaction',folder=str(tmp_path),pattern='*Foreign*Exchange*Transaction*',sheets=[None],multi_file=True,extra={'file_names':names})
 assert {Path(f).name for f in find_files(spec)}==set(names)


def test_planned_purchase_is_not_process_completion():
 d=FxTransactionAdapter().transform({'Sheet1':pd.DataFrame([{'سفارش':'502904B','ثبت سفارش':'12345678','مبلغ خرید ارز':100,'نوع ارز':'EUR','وضعیت':'دربرنامه خريد'}])})['main']
 assert d.iloc[0].FX_PURCHASE_STATE=='PLANNED'
 r=_observations({'fx_transaction':{'main':d}})
 assert 'FX_PURCHASE' not in set(r.STAGE_CODE)


def test_published_cashflow_excludes_plan_and_proforma_funding(tmp_path):
 from gsi.warehouse.store import Warehouse
 from gsi.warehouse.business_dwh import build
 from gsi.cashflow.dwh import bundle_from_dwh
 fx=FxTransactionAdapter().transform({'Sheet1':pd.DataFrame([{'سفارش':'502904B','ثبت سفارش':'12345678','مبلغ خرید ارز':100,'نوع ارز':'EUR','وضعیت':'دربرنامه خريد'}])})
 sources={'fx_transaction':fx,'credit':{'main':pd.DataFrame([{'KEY_REG':'12345678','CRD_FUND_DATE':'1405/01/01','CRD_RIAL_AMOUNT':10000}])}}
 wh=Warehouse(tmp_path/'cash.sqlite')
 with wh.run({'test':True}) as rid:build(wh,sources,rid)
 wh.publish(rid,slots=('dwh','report'))
 bundle=bundle_from_dwh('2026-09-23',wh)
 assert not set(bundle['events']['kind']) & {'FX_BUY','FUNDING'}
 assert {'PLANNED_PURCHASE_NOT_EXECUTED','FUNDING_AMOUNT_UNMEASURED'} <= set(bundle['diagnostics']['code'])

def test_sap_po_bl_relationship_reaches_dwh(tmp_path):
 from gsi.warehouse.store import Warehouse
 from gsi.warehouse.business_dwh import build
 sources={'sap':SapAdapter().transform({'inbound':pd.DataFrame([{'Delivery':'D1','Item':'10','Reference Document':'8300012345','Reference Item':'10','شماره بارنامه':'BL123','Material':'M1'}])})}
 wh=Warehouse(tmp_path/'sap.sqlite')
 with wh.run({'test':True}) as rid:build(wh,sources,rid)
 with wh.db() as c:
  assert c.execute("SELECT count(*) FROM dwh_relation WHERE left_type='PO' AND right_type='BL' AND left_key='8300012345' AND right_key='BL123'").fetchone()[0]==1

def test_legacy_event_consumers_use_actual_swift_not_proforma():
 from types import SimpleNamespace
 from gsi.stages.s55_fx_traceability import FxTraceabilityStage
 from gsi.stages.s56_money_flow_control import MoneyFlowControlStage
 cr=pd.DataFrame([{'KEY_REG':'12345678','CRD_RIAL_AMOUNT':10000,'CRD_EUR_AMOUNT':500,'CRD_FUND_DATE':'1405/01/01','CRD_SWIFT_DATE':'1405/01/02','CRD_SWIFT_AMOUNT':25,'CRD_SWIFT_CURRENCY':'CNY'}])
 ctx=SimpleNamespace(sheet=lambda source,frame:cr if source=='credit' else pd.DataFrame())
 events=FxTraceabilityStage()._build_events(pd.DataFrame(),ctx,pd.DataFrame())
 assert events.loc[events.EVENT_TYPE.eq('FUNDING'),'AMOUNT'].isna().all()
 swift=events.loc[events.EVENT_TYPE.eq('SWIFT')].iloc[0]
 assert swift.AMOUNT==25 and swift.CURRENCY=='CNY'
 money=MoneyFlowControlStage()._build_money_ledger(pd.DataFrame(),ctx)
 assert money.loc[money.EVENT_CODE.eq('BANK_FUNDING_IRR'),'AMOUNT'].isna().all()
 swift=money.loc[money.EVENT_CODE.eq('SWIFT')].iloc[0]
 assert swift.AMOUNT==25 and swift.CURRENCY=='CNY'

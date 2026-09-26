"""Fresh synthetic integration and source-to-export tests; no old project test helpers."""
import io,json,hashlib,base64
from datetime import date
import pandas as pd
import pytest
from openpyxl import load_workbook
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build
from gsi.adapters.a60_finance import FxTransactionAdapter,CreditAdapter,SapAdapter
from gsi.cashflow.dwh import bundle_from_dwh
from gsi.cashflow.engine import build_cashflow
from gsi.cashflow.report import excel_bytes,html_report,TITLES,LABELS
from gsi.stages.base import PipelineContext
from gsi.stages.s55_fx_traceability import FxTraceabilityStage

def warehouse(tmp_path,sources):
    wh=Warehouse(str(tmp_path/'graph.sqlite'))
    with wh.run({'reference_date':'2026-09-24'}) as rid:build(wh,sources,rid)
    wh.publish(rid,slots=('dwh','report'))
    return wh,rid

def test_same_literal_in_different_namespaces_stays_distinct(tmp_path):
    """ORDER and REG with identical strings stay distinct typed nodes connected by a relation."""
    wh,_=warehouse(tmp_path,{'fixture':{'main':pd.DataFrame([dict(KEY_REG='12345678',KEY_ORDER='12345678')])}})
    with wh.db() as c:
        types={r[0] for r in c.execute("SELECT entity_type FROM dwh_entity WHERE business_key='12345678'")}
        assert types=={'ORDER','REG'}
        assert c.execute('SELECT count(*) FROM dwh_relation').fetchone()[0]==1

def test_dwh_does_not_infer_edges_from_separate_rows(tmp_path):
    """ORDER and REG appearing on different records without a bridge do not prove ORDER↔REG."""
    wh,_=warehouse(tmp_path,{'fixture':{'main':pd.DataFrame([dict(KEY_REG='12345678'),dict(KEY_ORDER='602164B')])}})
    with wh.db() as c:assert c.execute('SELECT count(*) FROM dwh_relation').fetchone()[0]==0

def test_graph_many_to_many_retains_all_witnessed_edges(tmp_path):
    """Two orders and two REGs may have four directly witnessed edges; no one-to-one invention."""
    f=pd.DataFrame([dict(KEY_REG=r,KEY_ORDER=o) for r in ['12345678','87654321'] for o in ['602164B','602165B']])
    wh,_=warehouse(tmp_path,{'fixture':{'main':f}})
    with wh.db() as c:
        assert c.execute('SELECT count(*) FROM dwh_relation').fetchone()[0]==4
        assert c.execute("SELECT count(*) FROM dwh_relation WHERE source='fixture' AND frame='main' AND rule LIKE 'DIRECT_COOBSERVED:%'").fetchone()[0]==4

def test_expert_nonshipping_bl_cannot_become_shipping_edge(tmp_path):
    """Existing source authority forbids commercial-expert BL candidates from shipping graph edges."""
    wh,_=warehouse(tmp_path,{'moghavemat':{'main':pd.DataFrame([dict(KEY_ORDER='602164B',KEY_BL='FAKEBL01')])}})
    with wh.db() as c:assert c.execute("SELECT count(*) FROM dwh_relation WHERE left_type='BL' OR right_type='BL'").fetchone()[0]==0

def test_dwh_replay_preserves_counts_and_integrity(tmp_path):
    """Repeated source input does not multiply entities, relations or source facts; SQLite constraints hold."""
    source={'fixture':{'main':pd.DataFrame([dict(KEY_ORDER='602164B',KEY_REG='12345678',amount=100,currency='USD',_SOURCE_ROW=2)])}}
    wh,_=warehouse(tmp_path,source)
    def counts():
        with wh.db() as c:return {t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['dwh_entity','dwh_relation','dwh_fact_source_row']}
    first=counts()
    with wh.run({'reference_date':'2026-09-24'}) as rid:build(wh,source,rid)
    assert first==counts()
    with wh.db() as c:
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def test_dwh_raw_payload_retains_unknown_zero_and_source_row(tmp_path):
    """Unknown and zero remain distinct in stored payload and physical row reference survives."""
    wh,_=warehouse(tmp_path,{'fixture':{'main':pd.DataFrame([dict(KEY_REG='12345678',unknown=None,zero=0,_SOURCE_ROW=7,_SOURCE_FILE_ID='FIXTURE')])}})
    with wh.db() as c:payload=json.loads(c.execute('SELECT payload FROM dwh_fact_source_row').fetchone()[0])
    assert payload['unknown'] is None and payload['zero']==0 and payload['_SOURCE_ROW']==7 and payload['_SOURCE_FILE_ID']=='FIXTURE'

def test_pr_item_grain_retains_distinct_items():
    """PR number repeats legitimately across item10 and item20; source-native PR frame retains both."""
    f=pd.DataFrame([{'Purchase Requisition':'1234567890','Item of requisition':i,'Material':m} for i,m in [(10,'M1'),(20,'M2')]])
    out=SapAdapter().transform({'pr':f})['pr_items']
    assert len(out)==2 and out.KEY_PR.nunique()==1 and out.SAP_PR_ITEM.nunique()==2

def context(fx=None,commitment=None):
    return PipelineContext(rb=None,today=date(2026,9,24),sources={'fx_transaction':{'main':pd.DataFrame(fx or [])},'ntsw':{'commitment':pd.DataFrame(commitment or [])}})

def test_stage_unknown_commitment_not_zero():
    """Unknown source balance cannot turn into zero native/equivalent balance or fully released amount."""
    ctx=context(commitment=[dict(KEY_REG='12345678',NTSW_BALANCE=None,NTSW_INITIAL_COMMIT=100,NTSW_CURRENCY='EUR')])
    out=FxTraceabilityStage().run(pd.DataFrame([dict(CANONICAL_REG='12345678')]),ctx).iloc[0]
    assert pd.isna(out.FX_NTSW_BALANCE) and pd.isna(out.FX_NTSW_BALANCE_EUR_EQ) and pd.isna(out.FX_NTSW_RELEASED)

def test_stage_event_dedupe_preserves_currency():
    """Equal amounts and dates in USD and EUR represent two distinct FX events."""
    ctx=context(fx=[dict(KEY_REG='12345678',FX_AMOUNT=100,FX_CURRENCY=c,FX_BUY_DATE='2026-01-01') for c in ['USD','EUR']])
    ev=FxTraceabilityStage()._build_events(pd.DataFrame(),ctx,pd.DataFrame())
    assert len(ev)==2 and set(ev.CURRENCY)=={'USD','EUR'}

def physical_fx(tmp_path):
    path=tmp_path/'source.xlsx'
    raw=pd.DataFrame([{'ثبت سفارش':'12345678','سفارش':'602164B','تاریخ خرید ارز':'2026-01-01','مبلغ خرید ارز':100,'نوع ارز':'USD','معادل یورویی':90,'مبلغ ریالی':1000,'وضعیت':'خرید شده'},
                      {'ثبت سفارش':'12345678','سفارش':'602164B','تاریخ خرید ارز':'2026-01-02','مبلغ خرید ارز':200,'نوع ارز':'USD','معادل یورویی':180,'مبلغ ریالی':2000,'وضعیت':'دربرنامه خرید'}])
    raw.to_excel(path,index=False,sheet_name='Sheet1');original=hashlib.sha256(path.read_bytes()).hexdigest()
    wh=Warehouse(str(tmp_path/'physical.sqlite'))
    with wh.run({'reference_date':'2026-09-24'}) as rid:
        fid=wh.blob(path.read_bytes(),path.name,'fx_transaction',str(path))
        frame=pd.read_excel(path,dtype=object);frame['_SOURCE_FILE_ID']=fid;frame['_SOURCE_ROW']=[2,3];frame['_SOURCE_SHEET']='Sheet1'
        wh.frame(frame,'raw','fx_transaction/Sheet1')
        sources={'fx_transaction':FxTransactionAdapter().transform({'Sheet1':frame})}
        wh.frame(sources['fx_transaction']['main'],'standardized','fx_transaction/main');build(wh,sources,rid)
    wh.publish(rid,slots=('dwh','report'))
    return path,original,wh,sources,fid

def test_source_archive_to_dwh_lineage(tmp_path):
    """Physical XLSX hash remains unchanged and source file/sheet/row survive into both DWH facts."""
    path,h,wh,sources,fid=physical_fx(tmp_path)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==h
    with wh.db() as c:
        rows=[json.loads(r[0]) for r in c.execute("SELECT payload FROM dwh_fact_source_row WHERE source='fx_transaction' AND frame='main'")]
        stored=c.execute('SELECT content FROM wh_file WHERE id=?',(fid,)).fetchone()[0]
    assert stored==path.read_bytes()
    assert len(rows)==2 and {r['_SOURCE_ROW'] for r in rows}=={2,3}
    assert {r['_SOURCE_FILE_ID'] for r in rows}=={fid}

def test_purchase_semantic_paths_agree_on_planned_exclusion(tmp_path):
    """Same physical source yields USD100 purchased in cashflow and FX ledger; plannedUSD200 is not actual."""
    _,_,wh,sources,_=physical_fx(tmp_path)
    bundle=bundle_from_dwh('2026-09-24',wh)
    result=build_cashflow(bundle['events'],measurements=bundle['measurements'],as_of='2026-09-24')
    ctx=PipelineContext(rb=None,today=date(2026,9,24),sources=sources)
    FxTraceabilityStage().run(pd.DataFrame([dict(CANONICAL_REG='12345678')]),ctx)
    cash=result['summary'].query("currency == 'USD'").iloc[0].purchased
    ledger=ctx.extras['fx_ledger'].iloc[0].FX_PURCHASED_AMOUNT
    assert cash==100 and ledger==100,dict(cashflow=str(cash),fx_ledger=str(ledger))

def test_dwh_cashflow_excel_html_numeric_parity(tmp_path):
    """Source actualUSD100 reaches cashflow and XLSX with USD unit; HTML embeds the identical XLSX bytes."""
    _,_,wh,_,_=physical_fx(tmp_path);bundle=bundle_from_dwh('2026-09-24',wh)
    result=build_cashflow(bundle['events'],measurements=bundle['measurements'],as_of='2026-09-24')
    assert result['summary'].query("currency == 'USD'").iloc[0].purchased==100
    xlsx=excel_bytes(result);html=html_report(result,xlsx)
    ws=load_workbook(io.BytesIO(xlsx),data_only=True)[TITLES['summary'][:31]]
    rows=list(ws.values);headers=rows[0];pc,cc=headers.index(LABELS['purchased']),headers.index(LABELS['currency'])
    assert any(r[pc]==100 and r[cc]=='USD' for r in rows[1:])
    assert base64.b64encode(xlsx).decode() in html

def test_credit_swift_source_does_not_invent_supplier_payment(tmp_path):
    """Credit opening and SWIFT amount are independent source facts, not proof of beneficiary payment."""
    raw=pd.DataFrame([{'شماره ثبت سفارش':'12345678','شماره سفارش':'602164B','شماره اعتبار':'LC1',
        'ارزش پروفرم':100,'نوع ارز':'USD','تاریخ دریافت سوئیفت':'2026-01-01','مبلغ دریافت سوئیفت':40,'نوع ارز6':'USD'}])
    wh,_=warehouse(tmp_path,{'credit':CreditAdapter().transform({'PURCREDIT':raw})})
    bundle=bundle_from_dwh('2026-09-24',wh)
    assert 'PAYMENT' not in set(bundle['events'].get('kind',pd.Series(dtype=str)))

def test_chatbot_reads_published_snapshot_not_unpublished_work(tmp_path,monkeypatch):
    """A later unpublished build cannot change chatbot business evidence for the published run."""
    from gsi.knowledge_desk.operational import operational_search
    monkeypatch.setenv('GSI_DWH_PATH',str(tmp_path/'graph.sqlite'))
    first={'fixture':{'main':pd.DataFrame([dict(KEY_REG='12345678',KEY_ORDER='602164B')])}}
    wh,rid=warehouse(tmp_path,first)
    with wh.run({'reference_date':'2026-09-24'}) as next_id:
        build(wh,{'fixture':{'main':pd.DataFrame([dict(KEY_REG='87654321',KEY_ORDER='602165B')])}},next_id)
    hits=operational_search('REG 12345678')
    assert len(hits)==1 and hits[0]['semantic']['run_id']==rid
    assert any(x['key']=='602164B' for x in hits[0]['semantic']['relations'])
    assert operational_search('REG 87654321')==[]

def test_chatbot_no_evidence_refuses_financial_guess(tmp_path):
    """With no published record or knowledge evidence, chatbot declines instead of inventing a balance."""
    from gsi.knowledge_desk.config import KnowledgeDeskConfig
    from gsi.knowledge_desk.query import answer
    cfg=KnowledgeDeskConfig(db_path=str(tmp_path/'kb.sqlite'))
    r=answer(cfg,'مانده تعهد REG 99999999 چقدر است؟')
    assert not r['sources'] and 'مدرک کافی' in r['answer']

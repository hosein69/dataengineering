import os
import pandas as pd

from gsi.adapters.a60_finance import SapAdapter
from gsi.adapters.base import KEY_PR, KEY_PO, KEY_MATERIAL
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build


def _sap_rows():
    base={
        'Purchase Requisition':'6500029693','Document Type':'ZNPE','Item of requisition':10,
        'Material':'8240055002646','Material Description':'کنترل کننده','Short Text':'FREQUENCY INVERTER',
        'Quantity requested':2,'Unit of Measure':'UN','Material Group':'82-400550','Purchasing Group':'821',
        'Purgroup Description':'pump','Requisitioner':'318','Requisition date':45356,'Created By':'01_71201996',
        'Changed On':45433,'Release Date':45673,'Purchase order':'8500025028','Quantity ordered':0,
        'Goods Receipt':True,'Delivery Date':'20250116','Req. Tracking Number':'11125200','Total Value':98000000,
        'Currency':'IRR','Valuation Price':49000000,'Purchase Order Item':10,'Purchase Order Date':'20/07/1404',
        'pack.Pack Number':'7100004218','pack.Purchase Requisition':'6500029693','pack.Item of requisition':10,
        'pack.Quantity':2,'pack.order Num':'703741','pack.Responsible':'01_94990938','pack.Packed':'X',
        'pack.WorkFlow ID':'DEFAULT','pack.Material':'8240055002646',
        'po.Item':10,'po.Material':'8240055002646','po.Company Code':'1100','po.Plant':'1101',
        'po.Storage Location':'S231','po.Req. Tracking Number':'11125200','po.Material Group':'82-400550',
        'po.Order Quantity':2,'po.Order Unit':'UN','po.Net Order Price':657,'po.Currency':'EUR',
        'po.Purchase Requisition':'6500029693','po.Item of requisition':10,'po.Purchasing Doc. Type':'ZNPE',
        'po.Supplier':'2066377','po.Document Date':45937,'po.Created By':'01_94990938','po.شماره پرونده':'7100004218',
        'po.Your Reference':'2550425-B','po.Purch. Organization':'1101','po.Purchasing Group':'821','po.Our Reference':'703741',
    }
    a=dict(base); a['po.Purchasing Document']='6000078924'; a['po.Last Changed on']=46273; a['po.Net Order Value']=0
    b=dict(base); b['po.Purchasing Document']='8500030155'; b['po.Last Changed on']=46274; b['po.Net Order Value']=1664
    return pd.DataFrame([a,b])


def test_sap_adapter_separates_business_grains_and_normalizes_dates():
    frames=SapAdapter().transform({'Data':_sap_rows()})
    assert set(['main','raw_rows','pr_items','workflow_rows','po_items']) <= set(frames)
    assert len(frames['raw_rows']) == 2
    assert len(frames['pr_items']) == 1  # PO multiplicity must not duplicate requested quantity
    assert len(frames['po_items']) == 2
    assert frames['pr_items'].iloc[0][KEY_PR] == '6500029693'
    assert frames['pr_items'].iloc[0][KEY_MATERIAL] == '8240055002646'
    assert set(frames['po_items'][KEY_PO]) == {'6000078924','8500030155'}
    # Excel serial dates and Jalali dates are normalized, raw values are retained.
    assert frames['raw_rows'].iloc[0]['SAP_REQUISITION_DATE_ISO'].startswith('2024-')
    assert frames['raw_rows'].iloc[0]['SAP_PURCHASE_ORDER_DATE_ISO'].startswith('2025-')


def test_business_dwh_persists_sap_facts_and_direct_pr_po_relations(tmp_path, monkeypatch):
    path=tmp_path/'wh.sqlite'; monkeypatch.setenv('GSI_DWH_PATH',str(path))
    wh=Warehouse(path)
    frames=SapAdapter().transform({'Data':_sap_rows()})
    with wh.run({'test':'sap-v2976'}) as rid:
        counts=build(wh, {'sap':frames}, rid)
    assert counts['sap_pr_items'] == 1
    assert counts['sap_po_items'] == 2
    with wh.db() as c:
        assert c.execute('select count(*) from dwh_fact_sap_pr_item').fetchone()[0] == 1
        assert c.execute('select count(*) from dwh_fact_sap_po_item').fetchone()[0] == 2
        rel=c.execute("select count(*) from dwh_relation where left_type='PR' and right_type='PO' and source='sap'").fetchone()[0]
        assert rel == 2

def test_operational_chatbot_reads_published_semantic_dwh(tmp_path, monkeypatch):
    from gsi.knowledge_desk.operational import operational_search
    path=tmp_path/'chat_wh.sqlite'; monkeypatch.setenv('GSI_DWH_PATH',str(path))
    wh=Warehouse(path)
    frames=SapAdapter().transform({'Data':_sap_rows()})
    with wh.run({'test':'chatbot-v2976'}) as rid:
        build(wh, {'sap':frames}, rid)
    wh.publish(rid, slots=('dwh','report'))
    hits=operational_search('وضعیت PR 6500029693 چیست؟')
    assert hits and hits[0]['source_type']=='operational_dwh'
    body=hits[0]['body']
    assert '6500029693' in body
    assert '6000078924' in body and '8500030155' in body
    assert 'As-of published DWH run' in body

import pandas as pd
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build
from gsi.adapters.base import KEY_ORDER,KEY_MATERIAL,KEY_REG,KEY_REG_FILE


def test_registration_file_hub_and_order_material_grain(tmp_path):
    wh=Warehouse(tmp_path/'w.sqlite')
    sources={
      'ntsw': {'import_license': pd.DataFrame([{KEY_REG_FILE:'664823825',KEY_REG:'98404279',KEY_ORDER:'502805'}])},
      'ilappend': {'main': pd.DataFrame([{KEY_REG_FILE:'664823825',KEY_REG:'98404279',KEY_ORDER:'502805'}])},
      'moghavemat': {'inventory': pd.DataFrame([{KEY_ORDER:'502805',KEY_MATERIAL:'M1','MOGH_SUPPLIER_STOCK_QTY':3}])},
    }
    with wh.run({'t':1}) as rid:
        counts=build(wh,sources,rid)
    with wh.db() as c:
        hub=c.execute("SELECT reg_file_key,reg_key,order_key FROM dwh_registration_hub WHERE reg_file_key='664823825'").fetchall()
        fact=c.execute("SELECT order_key,material_key FROM dwh_fact_supply_position").fetchall()
        rel=c.execute("SELECT source,left_type,right_type FROM dwh_relation WHERE left_key='664823825'").fetchall()
    assert ('664823825','98404279','502805') in hub
    assert fact==[('502805','M1')]
    assert any(x[0]=='ntsw' and x[1]=='REG_FILE' and x[2]=='REG' for x in rel)


def test_moghavemat_does_not_create_bl_relation(tmp_path):
    wh=Warehouse(tmp_path/'w.sqlite')
    sources={'moghavemat': {'lines': pd.DataFrame([{KEY_ORDER:'O1','KEY_BL':'TECHREF1'}])}}
    with wh.run({'t':1}) as rid:
        build(wh,sources,rid)
    with wh.db() as c:
        n=c.execute("SELECT count(*) FROM dwh_relation WHERE source='moghavemat' AND (left_type='BL' OR right_type='BL')").fetchone()[0]
    assert n==0


def test_order_material_pr_item_bridge_preserves_multiple_prs_and_evidence(tmp_path):
    from gsi.adapters.base import KEY_PR
    wh=Warehouse(tmp_path/'w.sqlite')
    rel=pd.DataFrame([
        {KEY_ORDER:'843115',KEY_MATERIAL:'9654003280',KEY_PR:'6100002273','MOGH_PR_ITEM':'','MOGH_EVIDENCE_COUNT':1,'MOGH_SOURCE_ROWS':'124'},
        {KEY_ORDER:'843115',KEY_MATERIAL:'9654003280',KEY_PR:'6100002723','MOGH_PR_ITEM':'20','MOGH_EVIDENCE_COUNT':1,'MOGH_SOURCE_ROWS':'168'},
        {KEY_ORDER:'843120',KEY_MATERIAL:'9654003280',KEY_PR:'6100002854','MOGH_PR_ITEM':'20','MOGH_EVIDENCE_COUNT':2,'MOGH_SOURCE_ROWS':'169,170'},
    ])
    sources={'moghavemat': {'order_material_pr_item': rel}}
    with wh.run({'t':'ompi'}) as rid:
        build(wh,sources,rid)
    with wh.db() as c:
        rows=c.execute('''SELECT order_key,material_key,pr_key,pr_item,evidence_count,source_rows
                          FROM dwh_bridge_order_material_pr_item
                          ORDER BY order_key,pr_key''').fetchall()
    assert ('843115','9654003280','6100002273','',1,'124') in rows
    assert ('843115','9654003280','6100002723','20',1,'168') in rows
    assert ('843120','9654003280','6100002854','20',2,'169,170') in rows

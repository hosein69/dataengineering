# -*- coding: utf-8 -*-
"""R8: کلید و دانه انبار داده کسب‌وکار (داده ساختگی)."""
import pandas as pd

from gsi.adapters.a60_finance import SapAdapter
from gsi.adapters.base import (KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER, KEY_PO, KEY_PR, KEY_REG,
                               KEY_REG_FILE)
from gsi.warehouse import business_dwh as bd
from gsi.warehouse.business_dwh import build, canonical_sources, ensure_schema
from gsi.warehouse.store import Warehouse


def _build(wh, sources, tag):
    with wh.run({'t': tag}) as rid:
        return build(wh, sources, rid)


def _open(wh, sql, *args):
    with wh.db() as c:
        return c.execute(sql, args).fetchall()


# ─────────────── ۱ و ۲: کلید متعارف + EMP کارشناسان ───────────────
def _canon_sources():
    lic = pd.DataFrame([
        {KEY_REG_FILE: '664823825', KEY_REG: '98404279.0', KEY_ORDER: '603128A-Item 1'},
        {KEY_REG_FILE: '000', KEY_REG: '123', KEY_ORDER: '603130B-Items 2 & 3 '},
    ])
    inv = pd.DataFrame([{KEY_ORDER: '603128A', KEY_MATERIAL: 'ab-12', 'MOGH_QTY': 1}])
    main = pd.DataFrame([{KEY_ORDER: '603128A', 'MOGH_KEY_EMP': '201069-A'}])
    pr = pd.DataFrame([{KEY_PR: '6500000001.0', 'SAP_PR_ITEM': '00010', KEY_MATERIAL: 'm-1',
                        'SAP_SOURCE_ROW': 1}])
    hr = pd.DataFrame([{KEY_EMP: '10201069_GS'}])
    bl = pd.DataFrame([{KEY_BL: 'ab-1234', KEY_ORDER: '603128A'}, {KEY_BL: 'x1', KEY_ORDER: '603128A'}])
    return {'ntsw': {'import_license': lic}, 'moghavemat': {'inventory': inv, 'main': main},
            'sap': {'pr_items': pr}, 'hr': {'main': hr}, 'abbasi': {'main': bl}}


def test_canonical_sources_is_shallow_and_leaves_input_untouched():
    src = _canon_sources()
    before = {s: {f: df.copy() for f, df in fr.items()} for s, fr in src.items()}
    out = canonical_sources(src)
    for s, frames in src.items():
        for f, df in frames.items():
            pd.testing.assert_frame_equal(df, before[s][f])
    lic = out['ntsw']['import_license']
    assert lic[KEY_ORDER].tolist() == ['603128A', '603130B']
    assert lic[KEY_REG].tolist() == ['98404279', '']          # غیر ۸ رقمی نامعتبر
    assert lic[KEY_REG_FILE].tolist() == ['664823825', '']    # «000» جای‌نگه‌دار است
    assert out['moghavemat']['inventory'][KEY_MATERIAL].tolist() == ['AB12']
    assert out['moghavemat']['main']['MOGH_KEY_EMP'].tolist() == ['00201069']
    assert out['sap']['pr_items']['SAP_PR_ITEM'].tolist() == ['10']
    assert out['sap']['pr_items'][KEY_PR].tolist() == ['6500000001']
    assert out['hr']['main'][KEY_EMP].tolist() == ['10201069']
    assert out['abbasi']['main'][KEY_BL].tolist() == ['AB1234', '']
    # فریم بی‌تغییر همان شیء است (کپی فقط برای فریم عوض‌شده)
    unchanged = {'x': {'main': pd.DataFrame([{KEY_ORDER: '603128A'}])}}
    assert canonical_sources(unchanged)['x']['main'] is unchanged['x']['main']


def test_build_uses_canonical_keys_everywhere(tmp_path):
    wh = Warehouse(tmp_path / 'w.sqlite')
    src = _canon_sources()
    _build(wh, src, 'canon')
    ents = set(_open(wh, "SELECT entity_type,business_key FROM dwh_entity WHERE to_seq IS NULL"))
    orders = {k for t, k in ents if t == 'ORDER'}
    assert orders == {'603128A', '603130B'}
    assert ('REG', '98404279') in ents and ('REG', '123') not in ents and ('REG', '98404279.0') not in ents
    assert not any(t == 'REG_FILE' and k == '000' for t, k in ents)
    assert ('MATERIAL', 'AB12') in ents and ('BL', 'AB1234') in ents and ('BL', 'X1') not in ents
    # ORDER+MATERIAL از ntsw و کارشناسان روی یک سفارش می‌نشیند
    rel = set(_open(wh, "SELECT left_type,left_key,right_type,right_key,source FROM dwh_relation"))
    assert ('ORDER', '603128A', 'REG', '98404279', 'ntsw') in rel
    assert ('ORDER', '603128A', 'EMP', '00201069', 'moghavemat') in rel
    facts = _open(wh, "SELECT pr_key,pr_item FROM dwh_fact_sap_pr_item")
    assert facts == [('6500000001', '10')]
    assert _open(wh, "SELECT order_key,material_key FROM dwh_fact_supply_position") == [('603128A', 'AB12')]


def test_moghavemat_emp_alias_is_declared():
    assert bd._SOURCE_ALIASES['moghavemat'] == {'EMP': 'MOGH_KEY_EMP'}


# ─────────────── ۳: شاخص یکتای نسخه باز ───────────────
def _index_unique(wh, table):
    rows = _open(wh, f"PRAGMA index_list({table})")
    return {r[1]: r[2] for r in rows}.get(f"{table}_open")


def test_open_index_is_unique_and_old_index_is_migrated(tmp_path):
    wh = Warehouse(tmp_path / 'w.sqlite')
    ensure_schema(wh)
    for t in bd.TABLES:
        assert _index_unique(wh, t) == 1, t
    # انبار قدیمی: همان نام، غیریکتا
    with wh.db() as c:
        c.execute("DROP INDEX dwh_dim_order_open")
        c.execute("CREATE INDEX dwh_dim_order_open ON dwh_dim_order(order_key) WHERE to_seq IS NULL")
    assert _index_unique(wh, 'dwh_dim_order') == 0
    ensure_schema(wh)
    assert _index_unique(wh, 'dwh_dim_order') == 1


def test_open_index_migration_keeps_rows_when_duplicates_exist(tmp_path):
    wh = Warehouse(tmp_path / 'w.sqlite')
    ensure_schema(wh)
    with wh.db() as c:
        c.execute("DROP INDEX dwh_dim_order_open")
        c.execute("CREATE INDEX dwh_dim_order_open ON dwh_dim_order(order_key) WHERE to_seq IS NULL")
        for seq in (1, 2):
            c.execute("INSERT INTO dwh_dim_order(order_key,first_seen_run,from_seq,vhash) VALUES('O1','r',?,'h')",
                      (seq,))
    ensure_schema(wh)
    assert _index_unique(wh, 'dwh_dim_order') == 0
    assert _open(wh, "SELECT count(*) FROM dwh_dim_order")[0][0] == 2
    with wh.db() as c:
        assert bd._unique_open_indexes(c) == ['dwh_dim_order']


def test_unique_open_index_survives_rebuilds_with_changes(tmp_path):
    wh = Warehouse(tmp_path / 'w.sqlite')
    inv1 = pd.DataFrame([{KEY_ORDER: 'O1', KEY_MATERIAL: 'M1', 'Q': 1}])
    inv2 = pd.DataFrame([{KEY_ORDER: 'O1', KEY_MATERIAL: 'M1', 'Q': 2}])
    _build(wh, {'moghavemat': {'inventory': inv1}}, 'a')
    _build(wh, {'moghavemat': {'inventory': inv2}}, 'b')
    assert _open(wh, "SELECT count(*) FROM dwh_fact_supply_position")[0][0] == 2
    assert _open(wh, "SELECT count(*) FROM dwh_fact_supply_position WHERE to_seq IS NULL")[0][0] == 1


# ─────────────── ۴: درخواست تخصیص NTSW تکراری ───────────────
def _alloc(rows):
    return pd.DataFrame([{KEY_REG: '98404279', 'NTSW_REQUEST_KEY': k, 'NTSW_REQUEST_STATE': s,
                          'NTSW_REQ_AMOUNT': a} for k, s, a in rows])


def test_ambiguous_allocation_requests_all_kept_with_stable_suffix(tmp_path):
    rows = [('98404279|ROW:1', 'OPEN', 10), ('98404279|ROW:2', 'AMBIGUOUS', 20),
            ('98404279|ROW:2', 'AMBIGUOUS', 30), ('98404279|ROW:2', 'AMBIGUOUS', 40)]
    wh = Warehouse(tmp_path / 'w.sqlite')
    _build(wh, {'ntsw': {'allocation_rows': _alloc(rows)}}, 'a')
    got = dict(_open(wh, "SELECT request_key,payload FROM dwh_fact_ntsw_allocation_request WHERE to_seq IS NULL"))
    assert set(got) == {'98404279|ROW:1', '98404279|ROW:2#1', '98404279|ROW:2#2', '98404279|ROW:2#3'}
    assert '_DWH_REQUEST_OCCURRENCE' in got['98404279|ROW:2#2']
    assert '_DWH_REQUEST_OCCURRENCE' not in got['98404279|ROW:1']
    # ترتیب ردیف‌های فایل کلید را عوض نمی‌کند
    a, _ = bd._fact_rows('dwh_fact_ntsw_allocation_request', _alloc(rows))
    b, _ = bd._fact_rows('dwh_fact_ntsw_allocation_request', _alloc(list(reversed(rows))))
    strip = lambda rs: {r[0]: r[2].replace(' ', '') for r in rs}
    ka, kb = strip(a), strip(b)
    assert set(ka) == set(kb)
    for k in ka:
        amt = [x for x in ('10', '20', '30', '40') if f'"NTSW_REQ_AMOUNT":{x}' in ka[k]]
        assert amt and f'"NTSW_REQ_AMOUNT":{amt[0]}' in kb[k]
    # بازسازی با ترتیب معکوس نسخه تازه نمی‌سازد
    counts = _build(wh, {'ntsw': {'allocation_rows': _alloc(list(reversed(rows)))}}, 'b')
    v = counts['versions'].get('dwh_fact_ntsw_allocation_request', {})
    assert not v.get('new') and not v.get('gone') and not v.get('changed')


# ─────────────── ۵: متریال بی‌سفارش ───────────────
def test_supply_position_keeps_material_without_order(tmp_path):
    wh = Warehouse(tmp_path / 'w.sqlite')
    inv = pd.DataFrame([{KEY_ORDER: '', KEY_MATERIAL: 'M9', 'Q': 1},
                        {KEY_ORDER: 'O1', KEY_MATERIAL: 'M1', 'Q': 2},
                        {KEY_ORDER: 'O2', KEY_MATERIAL: '', 'Q': 3}])
    _build(wh, {'moghavemat': {'inventory': inv}}, 's')
    facts = set(_open(wh, "SELECT order_key,material_key FROM dwh_fact_supply_position"))
    assert facts == {('', 'M9'), ('O1', 'M1')}
    ents = set(_open(wh, "SELECT entity_type,business_key FROM dwh_entity"))
    assert ('MATERIAL', 'M9') in ents and ('ORDER', '') not in ents
    assert bd._fact_entities({'moghavemat': {'inventory': inv}}) >= {('MATERIAL', 'M9'), ('ORDER', 'O1')}
    assert ('ORDER', 'O2') not in bd._fact_entities({'moghavemat': {'inventory': inv}})


# ─────────────── ۶: قلم خالی SAP ───────────────
def _single_sheet():
    base = {'Purchase Requisition': '6500000001', 'Material': 'M1', 'Changed On': 45433}
    return pd.DataFrame([
        dict(base, **{'Item of requisition': '', 'po.Purchasing Document': '4500000001', 'po.Item': ''}),
        dict(base, **{'Item of requisition': '', 'po.Purchasing Document': '4500000001', 'po.Item': ''}),
        dict(base, **{'Item of requisition': '00010', 'po.Purchasing Document': '4500000001', 'po.Item': '10'}),
    ])


def test_sap_single_sheet_keeps_empty_items_apart(tmp_path):
    frames = SapAdapter().transform({'Data': _single_sheet()})
    pr = frames['pr_items']
    assert len(pr) == 3
    assert sorted(pr['SAP_PR_ITEM']) == ['', '', '10']
    assert sorted(pr['SAP_PR_ITEM_GROUP']) == ['10', 'ROW1', 'ROW2']
    po = frames['po_items']
    assert len(po) == 3 and sorted(po['SAP_PO_ITEM']) == ['', '', '10']
    assert 'SAP_PR_ITEM_GROUP' not in frames['raw_rows'] and 'SAP_PO_ITEM_GROUP' not in frames['raw_rows']
    wh = Warehouse(tmp_path / 'w.sqlite')
    counts = _build(wh, {'sap': frames}, 'sap')
    assert counts['sap_pr_items'] == 3 and counts['sap_po_items'] == 3
    assert set(_open(wh, "SELECT pr_item FROM dwh_fact_sap_pr_item")) == {('10',), ('ROW1',), ('ROW2',)}
    assert set(_open(wh, "SELECT po_item FROM dwh_fact_sap_po_item")) == {('10',), ('ROW1',), ('ROW2',)}


def test_sap_native_keeps_empty_items_apart():
    pr = pd.DataFrame([{'Purchase Requisition': '6500000001', 'Item of requisition': '', 'Material': 'M1'},
                       {'Purchase Requisition': '6500000001', 'Item of requisition': '', 'Material': 'M2'},
                       {'Purchase Requisition': '6500000001', 'Item of requisition': 10, 'Material': 'M3'}])
    po = pd.DataFrame([{'Purchasing Document': '4500000001', 'Item': '', 'Purchase Requisition': '6500000001'},
                       {'Purchasing Document': '4500000001', 'Item': '', 'Purchase Requisition': '6500000001'}])
    frames = SapAdapter().transform({'pr': pr, 'po': po})
    assert len(frames['pr_items']) == 3 and len(frames['po_items']) == 2
    assert sorted(frames['po_items']['SAP_PO_ITEM_GROUP']) == ['ROW1', 'ROW2']
    assert (frames['po_items']['SAP_PO_ITEM'] == '').all()
    assert 'SAP_PR_ITEM_GROUP' not in frames['raw_rows']
    assert set(frames['raw_rows']['SAP_SOURCE_SHEET']) == {'pr', 'po'}


# ─────────────── ۷: کلید source_keys.yaml ───────────────
def test_source_keys_use_real_sheet_columns():
    from gsi.adapters.a30_customs import ClearanceAdapter
    from gsi.warehouse.history import load_specs
    specs = load_specs()
    cl = ClearanceAdapter().transform({'main': pd.DataFrame(
        {'بارنامه': ['ABCD1'], 'پرونده ترخیص': ['C1'], '_SOURCE_SHEET': ['Sea Clearance']})})['main']
    assert specs.get('clearance/main').key_spec(cl.columns)['mode'] == 'keys'
    assert '_SOURCE_SHEET' not in specs.get('clearance/main').keys
    raw = SapAdapter().transform({'pr': pd.DataFrame([{'Purchase Requisition': '6500000001',
                                                         'Item of requisition': 10}])})['raw_rows']
    assert specs.get('sap/raw_rows').key_spec(raw.columns)['mode'] == 'keys'

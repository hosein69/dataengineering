# -*- coding: utf-8 -*-
"""انبار داده نسخه ۲: سوابق بدون حذف، ثبت دقیق تغییرات، و بایگانی دقیق ورودی ساخت.

همه روی SQLite موقت و داده ساختگی؛ هیچ فایل واقعی خوانده یا نوشته نمی‌شود.
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest

from gsi.warehouse.history import FrameSpec, Specs, frame_as_of, record_history
from gsi.warehouse.store import Warehouse

LOC = ('_SOURCE_ROW', '_SOURCE_FILE', '_SOURCE_FILE_ID')
SPECS = Specs(LOC, {'demo/main': FrameSpec(('id',), LOC, 'rows', 'demo')})


def _refresh(wh, df):
    """یک اجرای کامل: فریم استاندارد بایگانی می‌شود و سوابقش ثبت می‌شود."""
    with wh.run({'kind': 'test'}) as rid:
        wh.frame(df, 'standardized', 'demo/main')
    out = record_history(wh, rid, ['demo'], specs=SPECS)
    return rid, wh.run_seq(rid), out['frames']['demo/main']


def _rows(*items):
    return pd.DataFrame([{'id': i, 'amount': a, 'bank': b, '_SOURCE_ROW': r} for i, a, b, r in items])


def _changes(wh, seq):
    with wh.db() as c:
        return c.execute('SELECT rkey,kind,field,old,new FROM src_change WHERE seq=? ORDER BY id', (seq,)).fetchall()


def test_every_row_change_is_logged_with_old_and_new_values_and_nothing_is_deleted(tmp_path):
    wh = Warehouse(tmp_path / 'wh.sqlite')
    _, s1, st1 = _refresh(wh, _rows(('a', 1, 'ملت', 2), ('b', 2, 'ملی', 3), ('c', 3, 'سپه', 4)))
    assert st1['mode'] == 'baseline' and st1['new'] == 3

    # «a» فقط جابه‌جا شد، مبلغ «b» عوض شد، «c» دیگر نیست و «d» تازه است
    _, s2, st2 = _refresh(wh, _rows(('d', 4, 'ملت', 2), ('b', 20, 'ملی', 3), ('a', 1, 'ملت', 5)))
    assert (st2['unchanged'], st2['changed'], st2['gone'], st2['new']) == (1, 1, 1, 1)
    log = _changes(wh, s2)
    assert ('["b"]', 'changed', 'amount', '2', '20') in log
    assert ('["c"]', 'gone', None, None, None) in log
    assert ('["d"]', 'new', None, None, None) in log
    assert not [x for x in log if x[0] == '["a"]'], 'جابه‌جایی ردیف در فایل تغییر داده نیست'

    # «c» با بانک دیگری برمی‌گردد: «برگشته» همراه با فرق با آخرین نسخه‌اش
    _, s3, st3 = _refresh(wh, _rows(('d', 4, 'ملت', 2), ('b', 20, 'ملی', 3), ('a', 1, 'ملت', 5),
                                    ('c', 3, 'تجارت', 6)))
    assert st3['back'] == 1
    assert ('["c"]', 'back', 'bank', '"سپه"', '"تجارت"') in _changes(wh, s3)

    with wh.db() as c:
        total = c.execute("SELECT count(*) FROM src_record WHERE source='demo'").fetchone()[0]
        closed = c.execute("SELECT count(*) FROM src_record WHERE source='demo' AND to_seq IS NOT NULL").fetchone()[0]
        # ۳ خط مبنا + نسخه تازه b + d + برگشت c؛ هیچ نسخه‌ای پاک نشده است
        assert (total, closed) == (6, 2)
        first = frame_as_of(c, 'demo', 'main', s1).sort_values('id').reset_index(drop=True)
        placed = frame_as_of(c, 'demo', 'main', s1, with_location=True)
    assert first[['id', 'amount', 'bank']].values.tolist() == [['a', 1, 'ملت'], ['b', 2, 'ملی'], ['c', 3, 'سپه']]
    assert sorted(placed['_SOURCE_ROW']) == [2, 3, 4]


def test_unchanged_frame_is_not_reopened_and_logs_nothing(tmp_path):
    wh = Warehouse(tmp_path / 'wh.sqlite')
    df = _rows(('a', 1, 'ملت', 2), ('b', 2, 'ملی', 3))
    _refresh(wh, df)
    _, seq, st = _refresh(wh, df.copy())
    assert st['mode'] == 'same'
    assert _changes(wh, seq) == []


def test_type_or_blank_form_changes_are_not_business_changes(tmp_path):
    wh = Warehouse(tmp_path / 'wh.sqlite')
    _refresh(wh, pd.DataFrame({'id': ['a', 'b'], 'amount': [5, 7], 'bank': ['ملت', None], '_SOURCE_ROW': [2, 3]}))
    # همان داده با ستون عددی اعشاری و خانه خالی به شکل NaN
    _, seq, st = _refresh(wh, pd.DataFrame({'id': ['a', 'b'], 'amount': [5.0, 7.0], 'bank': ['ملت', float('nan')],
                                            '_SOURCE_ROW': [2, 3]}))
    assert st['changed'] == 0 and st['new'] == 0 and st['gone'] == 0
    assert [x for x in _changes(wh, seq) if x[1] in ('changed', 'new', 'gone')] == []


def test_history_change_log_and_runs_refuse_delete_and_edit(tmp_path):
    wh = Warehouse(tmp_path / 'wh.sqlite')
    _refresh(wh, _rows(('a', 1, 'ملت', 2)))
    _refresh(wh, _rows(('a', 2, 'ملت', 2)))
    with wh.db() as c:
        closed = c.execute('SELECT id FROM src_record WHERE to_seq IS NOT NULL').fetchone()[0]
        opened = c.execute('SELECT id FROM src_record WHERE to_seq IS NULL').fetchone()[0]
    attempts = [
        ('DELETE FROM src_record', ()),
        ('UPDATE src_record SET payload=x\'00\' WHERE id=?', (opened,)),
        ('UPDATE src_record SET to_seq=NULL WHERE id=?', (closed,)),
        ('DELETE FROM src_change', ()),
        ('UPDATE src_change SET new=\'x\'', ()),
        ('DELETE FROM src_zdict', ()),
        ('DELETE FROM wh_run', ()),
    ]
    for sql, args in attempts:
        with pytest.raises(sqlite3.DatabaseError):
            with wh.db() as c:
                c.execute(sql, args)
    with wh.db() as c:
        assert c.execute('SELECT count(*) FROM src_record').fetchone()[0] == 2
        assert c.execute('SELECT count(*) FROM wh_run').fetchone()[0] == 2


def test_dwh_input_archive_is_exactly_the_data_that_was_used(tmp_path):
    from gsi.warehouse.framecodec import decode_frame
    wh = Warehouse(tmp_path / 'wh.sqlite')
    df = pd.DataFrame({'KEY_MATERIAL': ['M1', 'M2'], 'QTY': ['1', '2']})
    with wh.run({'kind': 'test'}):
        wh.frame(df, 'standardized', 'oracle/main')
        # مقداری پس از بایگانی، در همان شیء و بی‌تغییر شکل، عوض می‌شود
        df.loc[0, 'QTY'] = '9'
        sha = wh.keep_frames('dwh_input', [('oracle/main', df)])['oracle/main']
        again = wh.keep_frames('dwh_input', [('oracle/main', df.copy())])['oracle/main']
    pd.testing.assert_frame_equal(decode_frame(wh.objects.get(sha, 'parquet')), df)
    assert again == sha, 'محتوای یکسان همان اثرانگشت را می‌گیرد'
    with wh.db() as c:
        assert c.execute("SELECT count(*) FROM wh_object WHERE sha=?", (sha,)).fetchone()[0] == 1
        assert c.execute("SELECT count(DISTINCT object_sha) FROM wh_frame WHERE name='oracle/main'").fetchone()[0] == 2


def _oracle(*items):
    return {'oracle': {'main': pd.DataFrame([{'KEY_MATERIAL': m, 'DESC': d, '_SOURCE_ROW': r} for m, d, r in items])}}


def _build(wh, sources):
    from gsi.warehouse.business_dwh import build
    with wh.run({'kind': 'test'}) as rid:
        counts = build(wh, sources, rid)
    wh.publish(rid)
    return rid, wh.run_seq(rid), counts


def test_business_rows_version_by_content_and_keep_their_first_seen_run(tmp_path):
    from gsi.warehouse.snapshots import as_of_sql
    wh = Warehouse(tmp_path / 'wh.sqlite')
    r1, s1, _ = _build(wh, _oracle(('M1', 'پیچ', 2), ('M2', 'مهره', 3)))

    # فقط جای ردیف‌ها در فایل عوض شد: نه نسخه تازه، نه ساخت دوباره
    _, s2, c2 = _build(wh, _oracle(('M2', 'مهره', 2), ('M1', 'پیچ', 3)))
    assert c2['versions'].get('dwh_fact_oracle_material') is None
    assert 'dwh_entity' not in c2['versions']

    # شرح M1 عوض شد و M2 رفت
    _, s3, c3 = _build(wh, _oracle(('M1', 'پیچ M8', 2)))
    assert c3['versions']['dwh_fact_oracle_material'] == {'unchanged': 0, 'changed': 1, 'new': 0, 'gone': 1}

    # M2 برمی‌گردد: «اولین بار دیده‌شده» همان اجرای اول می‌ماند
    r4, s4, _ = _build(wh, _oracle(('M1', 'پیچ M8', 2), ('M2', 'مهره', 3)))
    with wh.db() as c:
        dim = dict(c.execute('SELECT material_key,first_seen_run FROM dwh_dim_material WHERE to_seq IS NULL'))
        assert dim == {'M1': r1, 'M2': r1}

        def payloads(seq, rid):
            rows = c.execute(as_of_sql('dwh_fact_oracle_material', seq, rid, c)).fetchall()
            return {r[0]: json.loads(r[1])['DESC'] for r in rows}
        assert payloads(s1, r1) == {'M1': 'پیچ', 'M2': 'مهره'}
        assert payloads(s3, 'r3') == {'M1': 'پیچ M8'}
        assert payloads(s4, r4) == {'M1': 'پیچ M8', 'M2': 'مهره'}
        # نسخه‌ها فقط بسته شده‌اند: ۲ نسخه اول + نسخه تازه M1 + بازگشت M2
        assert c.execute('SELECT count(*) FROM dwh_fact_oracle_material').fetchone()[0] == 4
    with pytest.raises(sqlite3.DatabaseError):
        with wh.db() as c:
            c.execute('DELETE FROM dwh_fact_oracle_material')


def test_unchanged_inputs_skip_the_business_build(tmp_path):
    wh = Warehouse(tmp_path / 'wh.sqlite')
    sources = _oracle(('M1', 'پیچ', 2))
    _build(wh, sources)
    _, _, counts = _build(wh, {'oracle': {'main': sources['oracle']['main'].copy()}})
    assert 'evidence' in counts['unchanged'] and 'dwh_fact_oracle_material' in counts['unchanged']
    assert counts['versions'] == {}

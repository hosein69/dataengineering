import os
import sqlite3
import tempfile
import pandas as pd
import pytest

from gsi.warehouse.reliability import validate_frame, blocking, Check, BLOCK
from gsi.warehouse.store import Warehouse


def test_order_material_grain_duplicate_blocks():
    df=pd.DataFrame({'KEY_ORDER':['O1','O1'],'KEY_MATERIAL':['M1','M1'],'Q':[1,2]})
    checks=validate_frame('moghavemat/inventory',df)
    assert any(c.code=='GRAIN_UNIQUENESS' and not c.passed for c in checks)
    assert blocking(checks)


def test_order_material_distinct_material_is_valid():
    df=pd.DataFrame({'KEY_ORDER':['O1','O1'],'KEY_MATERIAL':['M1','M2']})
    checks=validate_frame('moghavemat/inventory',df)
    assert not blocking(checks)


def test_missing_key_column_blocks():
    df=pd.DataFrame({'KEY_ORDER':['O1']})
    checks=validate_frame('moghavemat/inventory',df)
    assert any(c.code=='REQUIRED_COLUMNS' and not c.passed for c in checks)


def test_atomic_publish_does_not_move_on_failed_gate(tmp_path):
    wh=Warehouse(tmp_path/'w.sqlite')
    with wh.run({'n':1}) as good:
        wh.record_quality(good,[Check('x','OK',BLOCK,True,{})])
    wh.publish(good,slots=('report','dwh'))
    with wh.run({'n':2}) as bad:
        wh.record_quality(bad,[Check('x','BROKEN',BLOCK,False,{})])
    with pytest.raises(ValueError):
        wh.publish(bad,slots=('report','dwh'))
    with wh.db() as c:
        rows=dict(c.execute('SELECT slot,run_id FROM wh_current').fetchall())
    assert rows=={'report':good,'dwh':good}


def test_publish_moves_both_slots_together(tmp_path):
    wh=Warehouse(tmp_path/'w.sqlite')
    with wh.run({'n':1}) as rid:
        wh.record_quality(rid,[Check('x','OK',BLOCK,True,{})])
    wh.publish(rid,slots=('report','dwh'))
    with wh.db() as c:
        rows=dict(c.execute('SELECT slot,run_id FROM wh_current').fetchall())
    assert rows['report']==rid and rows['dwh']==rid


def test_schema_drift_is_visible_and_baseline_is_stable(tmp_path):
    from gsi.warehouse.reliability import schema_drift_checks
    wh=Warehouse(tmp_path/'w.sqlite')
    first={'x':{'main':pd.DataFrame({'A':[1],'B':[2]})}}
    second={'x':{'main':pd.DataFrame({'A':[1],'C':[3]})}}
    with wh.run({'n':1}) as r1:
        c1=schema_drift_checks(wh,first,r1)
    assert any(x.code=='SCHEMA_BASELINE_CANDIDATE' for x in c1)
    wh.publish(r1)
    with wh.run({'n':2}) as r2:
        c2=schema_drift_checks(wh,second,r2)
    drift=[x for x in c2 if x.code=='SCHEMA_DRIFT'][0]
    assert not drift.passed
    assert drift.detail['added']==['C'] and drift.detail['removed']==['B']

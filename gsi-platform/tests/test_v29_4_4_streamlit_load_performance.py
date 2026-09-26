import os
from types import SimpleNamespace
import pandas as pd


def test_last_report_loads_only_df_main_and_keeps_extras_lazy(tmp_path, monkeypatch):
    db = tmp_path / 'warehouse.sqlite'
    monkeypatch.setenv('GSI_DWH_PATH', str(db))
    from gsi.warehouse.store import Warehouse
    from gsi.warehouse.service import last_report, LazyFrameExtras

    wh = Warehouse()
    with wh.run({'reference_date':'2026-09-21'}) as rid:
        wh.frame(pd.DataFrame({'A':[1,2]}), 'mart', 'df')
        wh.frame(pd.DataFrame({'A':[2]}), 'mart', 'main')
        wh.frame(pd.DataFrame({'X':range(100)}), 'mart', 'extras/eventlog')
        wh.frame(pd.DataFrame({'Z':range(100)}), 'mart', 'audit')
        wh.audit('report_metadata', {'report':'x.xlsx','counts':{},'extras':{'flag':True}})
    wh.publish(rid, slots=('report',))

    df, main, extras, report = last_report('2026-09-21')
    assert len(df) == 2 and len(main) == 1 and report == 'x.xlsx'
    assert isinstance(extras, LazyFrameExtras)
    assert extras.materialized_keys() == ('flag','warehouse_run_id','published_reference_date')
    assert len(extras['eventlog']) == 100
    assert 'eventlog' in extras.materialized_keys()
    # Non-returned mart frames such as audit must not even appear as extras.
    assert 'audit' not in extras


def test_persist_result_does_not_roundtrip_by_default(tmp_path, monkeypatch):
    db = tmp_path / 'warehouse.sqlite'
    monkeypatch.setenv('GSI_DWH_PATH', str(db))
    monkeypatch.delenv('GSI_DWH_VERIFY_ROUNDTRIP', raising=False)
    from gsi.warehouse.store import Warehouse
    from gsi.warehouse.bridge import persist_result

    wh = Warehouse()
    calls = {'read':0}
    orig = Warehouse.read_frame
    def counted(self, fid):
        calls['read'] += 1
        return orig(self, fid)
    monkeypatch.setattr(Warehouse, 'read_frame', counted)
    with wh.run({'reference_date':'2026-09-21'}):
        res = SimpleNamespace(
            df=pd.DataFrame({'A':[1]}), main=pd.DataFrame({'A':[1]}),
            to_resolve=pd.DataFrame(), excluded=pd.DataFrame(), audit=pd.DataFrame(),
            mogh_lines=pd.DataFrame(), extras={'eventlog':pd.DataFrame({'X':[1]})}
        )
        persist_result(res)
    assert calls['read'] == 0


def test_frame_cache_is_disposable_and_sqlite_remains_authoritative(tmp_path, monkeypatch):
    db = tmp_path / 'warehouse.sqlite'
    monkeypatch.setenv('GSI_DWH_PATH', str(db))
    from gsi.warehouse.store import Warehouse
    wh=Warehouse()
    src=pd.DataFrame({'A':[1,2], 'B':['x','y']})
    with wh.run({'reference_date':'2026-09-21'}):
        fid=wh.frame(src,'mart','df')
    cache=wh._frame_cache_path(fid)
    assert cache.exists()
    pd.testing.assert_frame_equal(wh.read_frame(fid), src)
    cache.unlink()
    rebuilt=wh.read_frame(fid)
    pd.testing.assert_frame_equal(rebuilt, src)
    assert cache.exists()

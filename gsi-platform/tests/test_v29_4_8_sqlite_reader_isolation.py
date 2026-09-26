import sqlite3
import pandas as pd


def test_lazy_extra_never_initializes_schema(tmp_path, monkeypatch):
    from gsi.warehouse.store import Warehouse
    from gsi.warehouse.service import LazyFrameExtras
    db=tmp_path/'w.sqlite'
    wh=Warehouse(db)
    with wh.run({'reference_date':'2026-09-21'}):
        fid=wh.frame(pd.DataFrame({'x':[1]}),'mart','extras/bottlenecks')
    called={'n':0}
    orig=Warehouse._ensure_schema
    def boom(self):
        called['n']+=1
        raise AssertionError('lazy reader attempted schema initialization')
    monkeypatch.setattr(Warehouse,'_ensure_schema',boom)
    extras=LazyFrameExtras(db,{}, {'bottlenecks':fid})
    assert int(extras.get('bottlenecks').iloc[0,0])==1
    assert called['n']==0
    monkeypatch.setattr(Warehouse,'_ensure_schema',orig)


def test_cached_frame_reads_while_sqlite_has_exclusive_lock(tmp_path):
    from gsi.warehouse.store import Warehouse
    db=tmp_path/'w.sqlite'
    wh=Warehouse(db)
    src=pd.DataFrame({'x':[1,2]})
    with wh.run({'reference_date':'2026-09-21'}):
        fid=wh.frame(src,'mart','extras/bottlenecks')
    lock=sqlite3.connect(db,timeout=1)
    try:
        lock.execute('BEGIN EXCLUSIVE')
        # Cache-first path must not touch SQLite at all.
        got=Warehouse(db,initialize=False).read_frame(fid)
        pd.testing.assert_frame_equal(got,src)
    finally:
        lock.rollback(); lock.close()


def test_locked_lazy_extra_degrades_without_crashing(tmp_path, monkeypatch):
    from gsi.warehouse.store import Warehouse
    from gsi.warehouse.service import LazyFrameExtras
    db=tmp_path/'w.sqlite'; Warehouse(db)
    def locked(self,fid):
        raise sqlite3.OperationalError('database is locked')
    monkeypatch.setattr(Warehouse,'read_frame',locked)
    extras=LazyFrameExtras(db,{}, {'bottlenecks':'frame-id'})
    assert extras.get('bottlenecks') is None
    assert extras.load_errors()['bottlenecks']['code']=='DWH_READ_BUSY'


def test_last_report_reader_does_not_initialize_schema(tmp_path, monkeypatch):
    from gsi.warehouse.store import Warehouse
    from gsi.warehouse.service import last_report
    db=tmp_path/'w.sqlite'; monkeypatch.setenv('GSI_DWH_PATH',str(db))
    wh=Warehouse(db)
    with wh.run({'reference_date':'2026-09-21'}) as rid:
        wh.frame(pd.DataFrame({'x':[1]}),'mart','df')
        wh.frame(pd.DataFrame({'x':[1]}),'mart','main')
        wh.audit('report_metadata',{'report':'r.xlsx','extras':{}})
    wh.publish(rid,('report',))
    orig=Warehouse._ensure_schema
    def boom(self): raise AssertionError('last_report attempted schema initialization')
    monkeypatch.setattr(Warehouse,'_ensure_schema',boom)
    try:
        assert last_report('2026-09-21') is not None
    finally:
        monkeypatch.setattr(Warehouse,'_ensure_schema',orig)

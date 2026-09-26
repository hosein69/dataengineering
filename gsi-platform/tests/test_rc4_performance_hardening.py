import pandas as pd


def test_capture_can_archive_without_retaining_physical_rows_and_reuses_exact_bytes(tmp_path, monkeypatch):
    db = tmp_path / 'warehouse.sqlite'
    monkeypatch.setenv('GSI_DWH_PATH', str(db))
    path = tmp_path / 'source.xlsx'
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({'A':['x','y'], 'B':[1,2]}).to_excel(writer, sheet_name='Data', index=False)
        pd.DataFrame({'C':['z']}).to_excel(writer, sheet_name='Other', index=False)

    from gsi.warehouse import excel
    from gsi.warehouse.store import Warehouse

    fid, blob, sheets = excel.capture(path, 'test_source', keep_sheets=False)
    assert blob == path.read_bytes()
    assert sheets == {}

    wh = Warehouse()
    with wh.db() as c:
        names = {r[0] for r in c.execute('SELECT name FROM wh_sheet WHERE file_id=?', (fid,))}
        stored = c.execute('SELECT count(*) FROM wh_raw_row WHERE file_id=?', (fid,)).fetchone()[0]
    assert names == {'Data', 'Other'}
    assert stored == 5  # 2 headers + 3 data rows

    # The exact same content hash is already a complete physical archive. A
    # repeated ingest must not parse worksheet XML again.
    def forbidden(*args, **kwargs):
        raise AssertionError('worksheet XML was reparsed for identical archived bytes')
    monkeypatch.setattr(excel, '_parse_sheet', forbidden)
    fid2, blob2, sheets2 = excel.capture(path, 'test_source', keep_sheets=False)
    assert fid2 == fid and blob2 == blob and sheets2 == {}


def test_capture_cached_native_rows_are_rehydratable(tmp_path, monkeypatch):
    monkeypatch.setenv('GSI_DWH_PATH', str(tmp_path / 'warehouse.sqlite'))
    path = tmp_path / 'native.xlsx'
    pd.DataFrame({'ثبت سفارش':['R1','R2'], 'سفارش':['O1','O2'], 'نام بانک':['B1','B2']}).to_excel(path, index=False)

    from gsi.warehouse import excel
    fid, _, first = excel.capture(path, 'fx_transaction', keep_sheets=True)
    assert first
    sheet = next(iter(first))
    first_rows = first[sheet]

    # Second call is served from the immutable raw-row archive, but the native
    # adapter receives the same physical representation.
    fid2, _, second = excel.capture(path, 'fx_transaction', keep_sheets=True)
    assert fid2 == fid
    assert second[sheet] == first_rows
    frame = excel.frame(second[sheet], 'fx_transaction', sheet, fid2)
    assert list(frame['ثبت سفارش']) == ['R1','R2']


def test_warehouse_frame_chunking_preserves_exact_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('GSI_DWH_PATH', str(tmp_path / 'warehouse.sqlite'))
    monkeypatch.setenv('GSI_WAREHOUSE_FRAME_CHUNK_ROWS', '2')
    from gsi.warehouse.store import Warehouse

    wh = Warehouse()
    src = pd.DataFrame({
        'INT': pd.Series([1,2,3,4,5], dtype='int64'),
        'TXT': pd.Series(['الف','ب','ج','د','ه'], dtype='object'),
        'FLOAT': pd.Series([1.5,2.5,3.5,4.5,5.5], dtype='float64'),
    }, index=pd.Index([10,20,30,40,50], name='RID'))
    # Series with default indexes above intentionally align to the custom index
    # as NaN; use direct values while preserving explicit dtypes.
    src = pd.DataFrame({
        'INT': pd.array([1,2,3,4,5], dtype='int64'),
        'TXT': pd.array(['الف','ب','ج','د','ه'], dtype='object'),
        'FLOAT': pd.array([1.5,2.5,3.5,4.5,5.5], dtype='float64'),
    }, index=pd.Index([10,20,30,40,50], name='RID'))
    src.attrs['evidence'] = {'source':'unit'}

    with wh.run({'test':'chunked-frame'}):
        fid = wh.frame(src, 'mart', 'sample')

    # Force SQLite rehydration instead of the disposable pickle cache.
    wh._frame_cache_path(fid).unlink()
    out = wh.read_frame(fid)
    pd.testing.assert_frame_equal(out, src)
    assert out.attrs == src.attrs
    with wh.db() as c:
        rows = c.execute('SELECT row_no FROM wh_frame_row WHERE frame_id=? ORDER BY row_no', (fid,)).fetchall()
    assert [r[0] for r in rows] == list(range(len(src)))

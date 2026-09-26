import json, threading, time
from pathlib import Path


def test_busy_lock_has_precise_diagnostic(tmp_path):
    from gsi.warehouse.writer_lock import WriterLock, WarehouseBusyError
    p=tmp_path/'x.writer.lock'
    with WriterLock(p, timeout=.2, metadata={'operation':'pipeline'}) as held:
        held.update(run_id='RUN-123')
        try:
            with WriterLock(p, timeout=.1):
                pass
        except WarehouseBusyError as ex:
            d=ex.as_dict()
            assert d['code']=='WAREHOUSE_WRITER_BUSY'
            assert d['run_id']=='RUN-123'
            assert d['category']=='CONCURRENCY'
        else:
            raise AssertionError('second writer must be refused')


def test_runtime_classifier_does_not_prescribe_doctor_for_busy(tmp_path):
    from gsi.warehouse.writer_lock import WarehouseBusyError
    from app.runtime_errors import classify_pipeline_exception
    ex=WarehouseBusyError(tmp_path/'x.writer.lock', {'pid':999,'host':'other-host'})
    d=classify_pipeline_exception(ex)
    assert d['doctor'] is False
    assert 'doctor' in d['action']
    assert 'لازم نیست' in d['action']


def test_source_path_error_does_prescribe_doctor():
    from app.runtime_errors import classify_pipeline_exception
    d=classify_pipeline_exception(FileNotFoundError('source file not found'))
    assert d['doctor'] is True

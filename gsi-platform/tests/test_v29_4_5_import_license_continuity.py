import pandas as pd
import pytest

from gsi.warehouse.reliability import validate_frame, blocking
from gsi.warehouse.store import Warehouse, QualityGateBlockedError


def test_import_license_partial_blank_rows_warn_but_do_not_block():
    df = pd.DataFrame({
        'KEY_REG_FILE':['664000001','664000002',''],
        'KEY_REG':['10290001','', '10290003'],
    })
    checks = validate_frame('ntsw/import_license', df)
    p = [c for c in checks if c.code == 'PARTIAL_KEY_EVIDENCE'][0]
    usable = [c for c in checks if c.code == 'USABLE_KEY_EVIDENCE'][0]
    assert not p.passed and p.severity == 'WARN'
    assert usable.passed
    assert not blocking(checks)


def test_import_license_no_complete_bridge_blocks():
    df = pd.DataFrame({
        'KEY_REG_FILE':['664000001',''],
        'KEY_REG':['', '10290003'],
    })
    checks = validate_frame('ntsw/import_license', df)
    usable = [c for c in checks if c.code == 'USABLE_KEY_EVIDENCE'][0]
    assert not usable.passed
    assert blocking(checks)


def test_quality_gate_exception_is_typed_and_preserves_current(tmp_path):
    from gsi.warehouse.reliability import Check, BLOCK
    wh=Warehouse(tmp_path/'w.sqlite')
    with wh.run({'n':1}) as good:
        wh.record_quality(good,[Check('x','OK',BLOCK,True,{})])
    wh.publish(good,slots=('report','dwh'))
    with wh.run({'n':2}) as bad:
        wh.record_quality(bad,[Check('ntsw/import_license','BROKEN',BLOCK,False,{})])
    with pytest.raises(QualityGateBlockedError) as ei:
        wh.publish(bad,slots=('report','dwh'))
    assert ei.value.as_dict()['code']=='QUALITY_GATE_BLOCKED'
    assert wh.current_run('report') == good
    assert wh.current_run('dwh') == good


def test_runtime_classifier_quality_gate_does_not_prescribe_doctor():
    from app.runtime_errors import classify_pipeline_exception
    ex=QualityGateBlockedError('r1',[('ntsw/import_license','USABLE_KEY_EVIDENCE')])
    d=classify_pipeline_exception(ex)
    assert d['code']=='QUALITY_GATE_BLOCKED'
    assert d['doctor'] is False
    assert 'doctor' in d['action']

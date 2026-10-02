import io
import pandas as pd
import pytest
from gsi.process_intelligence.core import profile,build_bundle,publish_bundle

def events():
    return pd.DataFrame({'_CASE_KEY':['01']*4+['02']*2,'ACTIVITY_FA':['A','B','A','B','A','B'],'EVENTTIME':['2026-09-01','2026-09-02','2026-09-03','2026-09-04','2026-09-01','2026-09-02']})

def test_counts():
    f=profile(events());e=f['graph']['edges'][0]
    assert e['count']==2 and e['occurrences']==3
    assert sum(n['count'] for n in f['graph']['nodes'])==2
    assert f['kpis'][2]['value']==1

@pytest.mark.parametrize('column,value',[('_CASE_KEY',None),('ACTIVITY_FA',' '),('EVENTTIME','bad')])
def test_invalid(column,value):
    d=events();d.loc[0,column]=value
    with pytest.raises(ValueError):profile(d)

def test_ties():
    d=events();d.loc[1,'EVENTTIME']=d.loc[0,'EVENTTIME']
    with pytest.raises(ValueError):profile(d)
    d['_SORTING']=range(len(d));assert profile(d)

def test_export_and_guards(tmp_path,monkeypatch):
    from openpyxl import load_workbook
    d=events();d.loc[d.ACTIVITY_FA=='A','ACTIVITY_FA']='=1+1<script>alert(1)</script>'
    files=build_bundle(d,title='نمونه آزمایشی')
    h=files['report.html'].decode()
    assert 'data:font/woff2;base64,' not in h and '<script>' not in h and 'IRANSansWeb' in h
    assert '<svg' not in files['email-body.html'].decode() and 'process-analysis.json' in files
    wb=load_workbook(io.BytesIO(files['report.xlsx']))
    assert all(c.data_type!='f' for w in wb for row in w for c in row)
    out=publish_bundle(files,tmp_path)
    assert publish_bundle(build_bundle(d,title='نمونه آزمایشی'),tmp_path)==out
    (out/'report.html').write_text('tampered')
    with pytest.raises(ValueError):publish_bundle(files,tmp_path)
    (tmp_path/'.paused').touch()
    with pytest.raises(RuntimeError):publish_bundle(files,tmp_path)
    monkeypatch.setenv('GSI_AUTOMATION_DISABLED','1')
    with pytest.raises(RuntimeError):build_bundle(d)

def test_headers_and_lock(tmp_path):
    with pytest.raises(ValueError):build_bundle(events(),recipient='a\nBcc:b')
    files=build_bundle(events());(tmp_path/'.gsi-publish.lock').mkdir()
    with pytest.raises(FileExistsError):publish_bundle(files,tmp_path)

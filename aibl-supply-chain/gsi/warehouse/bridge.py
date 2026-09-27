"""Pipeline persistence boundary; calculations remain owned by business stages."""
from pathlib import Path
import pandas as pd
from .store import Warehouse

def run_pipeline(pipeline,build_report,version):
    wh=Warehouse()
    with wh.run({'reference_date':str(pipeline.today),'version':version}) as rid:
        from gsi.config.sources import _yaml_path
        configured=Path(_yaml_path())
        if configured.exists():wh.blob(configured.read_bytes(),configured.name,'configuration',str(configured))
        for root in ('config','rules'):
            for path in (Path(__file__).parents[1]/root).glob('*.yaml'):
                wh.blob(path.read_bytes(),path.name,'configuration',str(path))
        result=pipeline._run_warehouse(build_report)
        result.extras['warehouse_run_id']=rid
        wh.audit('report_run',{'rows':len(result.df),'report':result.dashboard_path})
    wh.publish(rid)
    return result

def persist_result(res):
    wh=Warehouse()
    for name in ('df','main','to_resolve','excluded','audit','mogh_lines'):
        setattr(res,name,wh.read_frame(wh.frame(getattr(res,name),'mart',name)))
    for name,value in list(res.extras.items()):
        if isinstance(value,pd.DataFrame):res.extras[name]=wh.read_frame(wh.frame(value,'mart','extras/'+name))

def report_metadata(res):
    Warehouse().audit('report_metadata',{'report':res.dashboard_path,'counts':res.counts,'extras':{k:v for k,v in res.extras.items() if not isinstance(v,pd.DataFrame)}})

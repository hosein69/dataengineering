import sys,os,tempfile,time,json,resource
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import pandas as pd
from gsi.adapters.a60_finance import SapAdapter
from gsi.resolve.process_evidence import build_process_inventory
from gsi.warehouse.store import Warehouse
from gsi.warehouse.business_dwh import build
from gsi.knowledge_desk.operational import operational_search
from gsi.warehouse.excel import capture
from gsi.dataio.logging_setup import log
log.disabled=True
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);os.environ['GSI_DWH_PATH']=str(d/'bench.sqlite');wh=Warehouse();timings={}
 data=pd.DataFrame([{'Purchase Requisition':str(6500000000+i),'Item of requisition':'10','Material':f'M{i%30}','Processing status':'In process','po.Purchasing Document':str(4500000000+i),'po.Item':'10'} for i in range(300)])
 data.to_excel(d/'sap.xlsx',index=False)
 start=time.perf_counter()
 with wh.run({'benchmark':True}) as rid:
  t=time.perf_counter();capture(d/'sap.xlsx','sap');raw=pd.read_excel(d/'sap.xlsx',dtype=str);timings['archive_and_excel_parse_s']=time.perf_counter()-t
  t=time.perf_counter();frames=SapAdapter().transform({'Data':raw});timings['adapter_s']=time.perf_counter()-t
  t=time.perf_counter();obs,cases,matrix=build_process_inventory({'sap':frames});timings['process_s']=time.perf_counter()-t
  t=time.perf_counter();counts=build(wh,{'sap':frames},rid);timings['dwh_build_s']=time.perf_counter()-t
 wh.publish(rid)
 t=time.perf_counter();hits=operational_search('PR 6500000001');timings['published_query_s']=time.perf_counter()-t
 timings['end_to_end_primitives_s']=time.perf_counter()-start
 with wh.read_db() as c:plan=[list(r) for r in c.execute("EXPLAIN QUERY PLAN SELECT * FROM dwh_fact_sap_pr_item WHERE pr_key='6500000001'")]
 result={'rows':300,'timings':timings,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'database_bytes':wh.path.stat().st_size,'query_plan':plan,'hits':len(hits),'counts':counts,'scope':'single synthetic local workload; no production throughput claim'}
 Path(sys.argv[2]).write_text(json.dumps(result,indent=2));print(json.dumps(result))

import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ['GSI_DWH_PATH']=str(Path(__file__).with_name('sample_audit.sqlite'))
import pandas as pd
from gsi.adapters.a60_finance import SapAdapter,FxTransactionAdapter,CreditAdapter,IlAppendAdapter
from gsi.adapters.a50_ntsw import NtswAdapter
from gsi.adapters.a40_oracle import OracleAdapter
from gsi.adapters.a10_abbasi import AbbasiAdapter
from gsi.adapters.a20_sata import SataAdapter
from gsi.adapters.a30_customs import ClearanceAdapter,CotageAdapter
from gsi.adapters.moghavemat import MoghavematAdapter
raw=Path(__file__).with_name('evidence.txt').read_text(encoding='utf-8-sig')
x=json.loads(raw[raw.index('{'):])
profiles=x['profiles']
def frame(i):
 p=profiles[i];d=pd.DataFrame(p['sample_rows']);d['_SOURCE_SHEET']=p['sheet'];return d
contracts=[(SapAdapter,list(range(5))),(MoghavematAdapter,[5]),(OracleAdapter,[6,7]),(NtswAdapter,list(range(8,16))),(IlAppendAdapter,[16]),(AbbasiAdapter,[18]),(SataAdapter,[27]),(FxTransactionAdapter,[30,31]),(ClearanceAdapter,[32,34,36]),(CotageAdapter,[38]),(CreditAdapter,[40])]
results={}
for klass,indexes in contracts:
 try:
  sheets={profiles[i]['sheet']:frame(i) for i in indexes}
  if klass==ClearanceAdapter:sheets={'main':pd.concat(sheets.values(),ignore_index=True)}
  out=klass().transform(sheets)
  results[klass.key]={'input_samples':sum(len(v) for v in sheets.values()),'frames':{k:len(v) for k,v in out.items()}}
  if klass in (SapAdapter,FxTransactionAdapter,CreditAdapter):
   results[klass.key]['key_coverage']={k:{c:int(v[c].fillna('').astype(str).ne('').sum()) for c in v if c.startswith('KEY_')} for k,v in out.items()}
 except Exception as e:
  results[klass.key]={'error':repr(e)}
Path(__file__).with_name('SAMPLE_ADAPTER_AUDIT.json').write_text(json.dumps(results,indent=2,ensure_ascii=False));print(json.dumps(results,indent=2,ensure_ascii=False))

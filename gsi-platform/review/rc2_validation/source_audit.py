from pathlib import Path
import ast,sys,json,importlib.util
import yaml
root=Path('final_src');config=yaml.safe_load((root/'gsi/config/sources.yaml').read_text())
adapters=[]
for p in sorted((root/'gsi/adapters').glob('*.py')):
 tree=ast.parse(p.read_text())
 for cls in (n for n in tree.body if isinstance(n,ast.ClassDef)):
  maps={}
  for n in cls.body:
   if isinstance(n,ast.Assign):
    for target in n.targets:
     if isinstance(target,ast.Name) and ('MAP' in target.id or target.id.endswith('HEADERS')):
      try:maps[target.id]=ast.literal_eval(n.value)
      except (ValueError,TypeError):pass
  if maps:adapters.append({'module':str(p.relative_to(root)),'class':cls.name,'declared_maps':maps})
profiler=Path('source_profiler_input/gsi_source_profiler/gsi_source_profiler.py')
spec=importlib.util.spec_from_file_location('profiler_probe',profiler);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
probes={x:sorted(m.classify_column(x)) for x in ['شماره پرونده ثبت سفارش','شماره ثبت سفارش','Order No. (Our Reference)','Reference Letter No.','po.Purchasing Document','تاریخ ثبت سفارش']}
import pandas as pd
try:
 d=pd.DataFrame([{'شماره پرونده ثبت سفارش':'900000001'}]);m.relation_examples(d,m.semantic_columns(d));error=None
except Exception as e:error=f'{type(e).__name__}: {e}'
out={'source_registry':config['sources'],'source_count':len(config['sources']),'enabled_source_count':sum(v.get('enabled',True) for v in config['sources'].values()),'adapter_column_maps':adapters,'profiler_role_probes':probes,'profiler_same_column_relation_probe':error,'actual_corporate_source_workbooks_supplied':False,'new_attachment_contains':['README_FA.md','MODEL_REVIEW_PROMPT.md','gsi_sources.yaml','gsi_source_profiler.py'],'scope':'code/header contracts and included samples; no production source completeness attestation'}
Path('final_evidence/SOURCE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x: sorted(x) if isinstance(x,set) else str(x)))
print(json.dumps({k:out[k] for k in ['source_count','enabled_source_count','profiler_role_probes','profiler_same_column_relation_probe']},ensure_ascii=False))

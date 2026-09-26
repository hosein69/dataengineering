from pathlib import Path
import zipfile,json,hashlib,difflib,shutil,ast
root=Path('/workspace/scratch/58b6b78e0919');src=root/'src';out=root/'deliverables';out.mkdir(exist_ok=True)
validation=src/'review/validation';validation.mkdir(exist_ok=True)
for p in (root/'evidence').iterdir():
 if p.suffix in {'.log','.json','.txt','.py'} and '.writer.lock.' not in p.name:
  shutil.copy2(p,validation/p.name)
z=zipfile.ZipFile(root/'upload/GSI_V29_7_6_SAP_SEMANTIC_DWH_SMART_CHATBOT.zip')
original={n.removeprefix('gsi_2976/'):z.read(n) for n in z.namelist() if not n.endswith('/')}
changes=[];diff=[]
for p in sorted(src.rglob('*')):
 if not p.is_file() or any(x in p.parts for x in ['__pycache__','.pytest_cache']):continue
 rel=p.relative_to(src).as_posix()
 if rel.startswith('review/') or rel=='CHANGES.patch':continue
 b=p.read_bytes();old=original.get(rel)
 if b==old:continue
 changes.append({'file':rel,'change':'added' if old is None else 'modified','before_sha256':hashlib.sha256(old).hexdigest() if old is not None else None,'after_sha256':hashlib.sha256(b).hexdigest()})
 if p.suffix in {'.py','.yaml','.yml','.txt'}:
  try:diff.extend(difflib.unified_diff((old or b'').decode().splitlines(True),b.decode().splitlines(True),fromfile='original/'+rel,tofile='rc/'+rel))
  except UnicodeDecodeError:pass
(validation/'changes.patch').write_text(''.join(diff))
(validation/'changed_files.json').write_text(json.dumps(changes,indent=2,ensure_ascii=False))
# Hash list is prepared after all release documents have been written.
print(json.dumps({'changed_files':len(changes),'python_suites':len(list((src/'tests').glob('test_*.py')))}))

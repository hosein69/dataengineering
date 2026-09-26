import os,sys,subprocess,sqlite3,json
from pathlib import Path
root=Path('/workspace/scratch/58b6b78e0919')
p=root/'evidence/repeated_architecture.sqlite'
assert not p.exists(), 'Use a fresh database; preserve prior evidence'
results=[]
for i in range(3):
 with (root/f'evidence/repeated_architecture_{i+1}.log').open('w') as log:
  r=subprocess.run([sys.executable,'tests/test_architecture.py'],cwd=root/'src',env=dict(os.environ,GSI_DWH_PATH=str(p)),stdout=log,stderr=subprocess.STDOUT,timeout=180)
 with sqlite3.connect(p) as c:
  integrity=c.execute('pragma integrity_check').fetchall()
 results.append({'iteration':i+1,'exit_code':r.returncode,'integrity':integrity})
 (root/'evidence/repeated_architecture_results.json').write_text(json.dumps(results,indent=2))
 if r.returncode or integrity != [('ok',)]:break
print(json.dumps(results))

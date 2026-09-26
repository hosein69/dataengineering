from __future__ import annotations
import ast, tempfile, argparse, hashlib, json, os, platform, shutil, subprocess, sys, time, traceback, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent

def say(msg=''):
    print(msg, flush=True)

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def run_cmd(cmd,cwd,env,timeout,log_path):
    """Run a child visibly without flooding the console.

    Child stdout/stderr is written to a UTF-8 log while the parent emits a
    heartbeat every 10 seconds. This is intentionally Windows-console safe and
    makes long pytest/process-probe steps visibly alive when launched by double-click.
    """
    t=time.perf_counter(); timed=False
    log_path.parent.mkdir(parents=True,exist_ok=True)
    label=log_path.parent.name+'/'+log_path.name
    say(f"[START] {label}")
    say('        ' + ' '.join(str(x) for x in cmd[:6]) + (' ...' if len(cmd)>6 else ''))
    with log_path.open('w',encoding='utf-8',errors='replace') as log:
        try:
            p=subprocess.Popen(cmd,cwd=str(cwd),env=env,stdout=log,stderr=subprocess.STDOUT,text=True)
        except Exception as ex:
            log.write(f"[LAUNCH_ERROR] {type(ex).__name__}: {ex}\n")
            say(f"[ERROR] cannot launch {label}: {type(ex).__name__}: {ex}")
            return {'command':cmd,'exit_code':127,'seconds':round(time.perf_counter()-t,3),'timeout':False,'log':str(log_path.name),'launch_error':str(ex)}
        next_beat=10.0
        while True:
            code=p.poll()
            elapsed=time.perf_counter()-t
            if code is not None:
                break
            if elapsed >= timeout:
                timed=True
                try: p.kill()
                except Exception: pass
                try: p.wait(timeout=5)
                except Exception: pass
                log.write('\n[TIMEOUT]\n')
                code=124
                break
            if elapsed >= next_beat:
                say(f"[RUNNING] {label}  {int(elapsed)}s elapsed")
                next_beat += 10.0
            time.sleep(1.0)
    seconds=round(time.perf_counter()-t,3)
    say(f"[DONE]  {label}  exit={code}  {seconds}s" + ('  TIMEOUT' if timed else ''))
    return {'command':cmd,'exit_code':code,'seconds':seconds,'timeout':timed,'log':str(log_path.name)}

def verify_manifest():
    p=ROOT/'PACKAGE_SHA256.json'
    if not p.exists(): return {'status':'MISSING'}
    m=json.loads(p.read_text(encoding='utf-8')); mismatch=[]; missing=[]
    for rel,expected in m.items():
        q=ROOT/rel
        if not q.exists(): missing.append(rel); continue
        if sha256_file(q)!=expected: mismatch.append(rel)
    return {'status':'PASS' if not missing and not mismatch else 'FAIL','entries':len(m),'missing':missing,'mismatch':mismatch}

def knowledge_check():
    try:
        kb=ROOT/'offline_knowledge'; m=json.loads((kb/'knowledge_manifest.json').read_text(encoding='utf-8'))
        bad=[]
        for rel,expected in m['files'].items():
            p=kb/rel
            if not p.exists() or sha256_file(p)!=expected: bad.append(rel)
        return {'status':'PASS' if not bad else 'FAIL','files':len(m['files']),'bad':bad}
    except Exception as ex: return {'status':'ERROR','error':f'{type(ex).__name__}: {ex}'}

def parse_pytest_json(path:Path):
    if not path.exists(): return []
    try: return json.loads(path.read_text(encoding='utf-8')).get('tests',[])
    except Exception: return []

def map_findings(test_results):
    try: findings=json.loads((HERE/'baseline/FINDINGS_REGISTER.json').read_text(encoding='utf-8'))
    except Exception: findings=[]
    idx={t:f['id'] for f in findings for t in f.get('failed_tests',[])}
    counts={}; unknown=[]
    for t in test_results:
        if t.get('outcome')!='failed': continue
        node=t.get('id',''); canonical=node[node.find('tests/'):] if 'tests/' in node else node; fid=idx.get(canonical)
        if fid: counts[fid]=counts.get(fid,0)+1
        else: unknown.append(node)
    return {'known_findings':counts,'unmapped_failures':unknown}

def run_independent(out,env,timeout):
    res=out/'independent'; res.mkdir()
    env=dict(env,GSI_AUDIT_TARGET=str(ROOT),GSI_AUDIT_RESULTS=str(res))
    conftest=HERE/'frozen_audit/tests/conftest.py'
    tests=HERE/'frozen_audit/tests'
    cmd=[sys.executable,'-B','-m','pytest','-q','--confcutdir',str(tests),str(tests)]
    step=run_cmd(cmd,out,env,timeout,res/'execution.log')
    results=parse_pytest_json(res/'test_results.json')
    passed=sum(t.get('outcome')=='passed' for t in results); failed=sum(t.get('outcome')=='failed' for t in results)
    step.update({'passed':passed,'failed':failed,'total_results':len(results),'finding_map':map_findings(results)})
    return step

def run_extended(out,env,timeout):
    res=out/'extended'; res.mkdir()
    cmd=[sys.executable,'-B','-m','pytest','-q','--junitxml',str(res/'junit.xml'),str(HERE/'tests')]
    
    e=dict(env,GSI_DIAGNOSTIC_TARGET=str(ROOT),GSI_DIAGNOSTIC_RESULTS=str(res))
    step=run_cmd(cmd,out,e,timeout,res/'execution.log')
    results=parse_pytest_json(res/'test_results.json')
    step.update({'passed':sum(t.get('outcome')=='passed' for t in results),'failed':sum(t.get('outcome')=='failed' for t in results),'total_results':len(results),'failed_tests':[t.get('id') for t in results if t.get('outcome')=='failed']})
    return step

def internal_command(path, basetemp):
    # Same entrypoint contract as run_all_tests.py; scripts must actually run.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    standalone = any(isinstance(n, ast.If) and "__name__" in ast.unparse(n.test)
                     and "__main__" in ast.unparse(n.test) for n in tree.body)
    if standalone:
        return [sys.executable, "-B", str(path)]
    return [sys.executable, "-B", "-m", "pytest", "-q", "--basetemp", str(basetemp), str(path)]


def run_internal_per_file(out,env,per_file_timeout,limit=0):
    res=out/'internal'; res.mkdir(); rows=[]
    files=sorted((ROOT/'tests').glob('test_*.py'))+sorted((ROOT/'tests').glob('legacy_test_*.py'))
    if limit: files=files[:limit]
    for i,f in enumerate(files,1):
        log=res/(f.stem+'.log')
        basetemp=res/'pytest_tmp'/f.stem
        cmd=internal_command(f,basetemp)
        with tempfile.TemporaryDirectory(prefix="gsi-diagnostic-suite-") as isolated:
            suite_env=dict(env,GSI_DWH_PATH=str(Path(isolated)/"warehouse.sqlite"),
                           PYTHONPATH=str(ROOT)+os.pathsep+env.get("PYTHONPATH",""))
            r=run_cmd(cmd,ROOT,suite_env,per_file_timeout,log)
        r['file']=str(f.relative_to(ROOT))
        r['classification']='PASS' if r['exit_code']==0 else ('NO_TESTS' if r['exit_code']==5 else ('TIMEOUT' if r['exit_code']==124 else 'FAIL'))
        rows.append(r)
    (res/'per_file_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'files':len(rows),'passed_files':sum(r['classification']=='PASS' for r in rows),
            'no_test_files':sum(r['classification']=='NO_TESTS' for r in rows),
            'failed_files':sum(r['classification']=='FAIL' for r in rows),
            'timed_out_files':sum(r['classification']=='TIMEOUT' for r in rows),'results':'per_file_results.json'}


def run_internal_order_smoke(out,env,timeout):
    res=out/'internal_order'; res.mkdir(exist_ok=True)
    files=sorted((ROOT/'tests').glob('test_*.py'))+sorted((ROOT/'tests').glob('legacy_test_*.py'))
    rel=[str(f) for f in files]
    normal=run_cmd([sys.executable,'-B','-m','pytest','-q','--basetemp',str(res/'pytest_tmp_normal'),*rel],ROOT,env,timeout,res/'normal_order.log') if rel else {'exit_code':0,'seconds':0,'timeout':False}
    reverse=run_cmd([sys.executable,'-B','-m','pytest','-q','--basetemp',str(res/'pytest_tmp_reverse'),*reversed(rel)],ROOT,env,timeout,res/'reverse_order.log') if rel else {'exit_code':0,'seconds':0,'timeout':False}
    return {'normal':normal,'reverse':reverse,'file_count':len(rel)}

def dependency_check():
    """Validate installed distributions against the shipped runtime contract."""
    import importlib.metadata as md
    try:
        from packaging.requirements import Requirement
        problems=[]; versions={}
        for line in (ROOT/'requirements.txt').read_text(encoding='utf-8').splitlines():
            line=line.split('#',1)[0].strip()
            if not line: continue
            req=Requirement(line)
            if req.marker and not req.marker.evaluate(): continue
            try: version=md.version(req.name)
            except md.PackageNotFoundError:
                problems.append({'package':req.name,'reason':'MISSING'});continue
            versions[req.name]=version
            if version not in req.specifier:
                problems.append({'package':req.name,'installed':version,'required':str(req.specifier)})
        return {'status':'FAIL' if problems else 'PASS','problems':problems,'versions':versions}
    except Exception as ex:
        return {'status':'ERROR','error':str(ex)}

def summarize(out,steps,source_inventory,ntsw_probe):
    summary={'run_id':out.name,'generated_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'package_root':str(ROOT),
      'package_info':json.loads((ROOT/'PACKAGE_INFO.json').read_text(encoding='utf-8')) if (ROOT/'PACKAGE_INFO.json').exists() else {},
      'manifest':verify_manifest(),'knowledge':knowledge_check(),'steps':steps,'source_inventory_summary':{},'ntsw_probe':ntsw_probe}
    if source_inventory:
        sts={}
        for s in source_inventory.get('sources',[]): sts[s.get('status','?')]=sts.get(s.get('status','?'),0)+1
        summary['source_inventory_summary']=sts
    summary['dependencies']=dependency_check()
    blockers=[]
    if summary['dependencies']['status']!='PASS': blockers.append('DEPENDENCY_CONTRACT')
    if summary['manifest']['status']!='PASS': blockers.append('PACKAGE_MANIFEST')
    if summary['knowledge']['status']!='PASS': blockers.append('KNOWLEDGE_MANIFEST')
    ind=steps.get('independent',{})
    if ind.get('failed',0) or ind.get('exit_code') != 0 or ind.get('total_results',0) != 173: blockers.append('INDEPENDENT_SEMANTIC_FAILURES')
    if steps.get('extended',{}).get('failed',0) or steps.get('extended',{}).get('exit_code') != 0 or steps.get('extended',{}).get('total_results',0) != 77: blockers.append('EXTENDED_DIAGNOSTIC_FAILURES')
    internal=steps.get('internal',{})
    if internal.get('error') or internal.get('skipped') or not internal.get('files'):
        blockers.append('INTERNAL_VALIDATION_INCOMPLETE')
    if internal.get('no_test_files',0): blockers.append('INTERNAL_NO_TESTS')
    if steps.get('internal',{}).get('failed_files',0): blockers.append('INTERNAL_REGRESSION_FAILURES')
    if steps.get('internal',{}).get('timed_out_files',0): blockers.append('INTERNAL_TEST_TIMEOUTS')
    order=steps.get('internal_order',{})
    if order:
        for label in ('normal','reverse'):
            r=order.get(label,{})
            if r.get('timeout'): blockers.append('INTERNAL_ORDER_'+label.upper()+'_TIMEOUT')
            elif r.get('exit_code') not in (0,None): blockers.append('INTERNAL_ORDER_'+label.upper()+'_FAIL')
    if not source_inventory or not source_inventory.get('sources'): blockers.append('SOURCE_INVENTORY_INCOMPLETE')
    if source_inventory.get('status') in {'ERROR','TIMEOUT'}: blockers.append('SOURCE_INVENTORY_'+source_inventory.get('status'))
    if source_inventory and any(x.get('status')=='MISSING_REQUIRED' for x in source_inventory.get('sources',[])): blockers.append('REQUIRED_SOURCE_MISSING')
    if ntsw_probe.get('status') in {'ERROR','TIMEOUT'}: blockers.append('NTSW_REAL_DATA_PROBE_'+ntsw_probe.get('status'))
    if ntsw_probe.get('status') != 'OK': blockers.append('NTSW_ACCEPTANCE_INCOMPLETE')
    summary['release_gate']='PASS' if not blockers else 'HOLD'
    summary['blockers']=blockers
    return summary

def feedback_md(s):
    ind=s['steps'].get('independent',{}); internal=s['steps'].get('internal',{})
    lines=['# GSI Offline Diagnostic Feedback','',f"Run: `{s['run_id']}`",f"Release gate: **{s['release_gate']}**",'']
    lines+=['## خلاصه',f"- Manifest: {s['manifest']['status']}",f"- Knowledge bundle: {s['knowledge']['status']}",f"- Independent semantic suite: {ind.get('passed',0)} pass / {ind.get('failed',0)} fail",f"- Extended diagnostic suite: {s['steps'].get('extended',{}).get('passed',0)} pass / {s['steps'].get('extended',{}).get('failed',0)} fail",f"- Internal test files: {internal.get('passed_files',0)} pass / {internal.get('failed_files',0)} fail / {internal.get('timed_out_files',0)} timeout",f"- Blockers: {', '.join(s['blockers']) or 'none'}",'']
    fm=ind.get('finding_map',{}).get('known_findings',{})
    if fm:
        lines+=['## یافته‌های باز شناخته‌شده']+[f"- {k}: {v} failure" for k,v in sorted(fm.items())]+['']
    lines+=['## چیزی که برای اصلاح باید ارسال شود','فقط فایل ZIP خروجی این runner را ارسال کنید؛ داده خام سازمانی داخل feedback کپی نمی‌شود.','']
    return '\n'.join(lines)

def zip_dir(src:Path,dest:Path):
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in src.rglob('*'):
            if p.is_file() and p.resolve()!=dest.resolve(): z.write(p,p.relative_to(src))



def _has_dist(name,md):
    try: md.version(name); return True
    except Exception: return False

def main():
    ap=argparse.ArgumentParser(description='GSI comprehensive offline diagnostic; no network access used.')
    ap.add_argument('--output',default='')
    ap.add_argument('--data-dir',default=os.environ.get('GSI_OFFLINE_DATA_DIR',''))
    ap.add_argument('--skip-internal',action='store_true')
    ap.add_argument('--per-file-timeout',type=int,default=600)
    ap.add_argument('--suite-timeout',type=int,default=600)
    ap.add_argument('--skip-order-smoke',action='store_true')
    a=ap.parse_args()
    # If the user keeps source files beside the extracted package, this is the
    # safest offline default. Explicit --data-dir still wins.
    if not a.data_dir:
        a.data_dir=str(ROOT)
    ts=time.strftime('%Y%m%d_%H%M%S'); base=Path(a.output).resolve() if a.output else ROOT/'offline_feedback'
    out=base/f'GSI_FEEDBACK_{ts}'; out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',GSI_DWH_PATH=str(out/'diagnostic.sqlite'))
    # Corporate proxy settings must never intercept the native offline service.
    # urllib honors NO_PROXY/no_proxy, so explicitly protect loopback on Windows/Linux.
    for _key in ('NO_PROXY','no_proxy'):
        _cur=env.get(_key,'')
        _parts=[x.strip() for x in _cur.split(',') if x.strip()]
        for _host in ('127.0.0.1','localhost','::1'):
            if _host not in _parts: _parts.append(_host)
        env[_key]=','.join(_parts)
    try:
        import importlib.metadata as md
        deps={n:(md.version(n) if True else '') for n in ['pandas','numpy','openpyxl','PyYAML','pytest','streamlit','plotly','streamlit-sortables','cryptography','matplotlib'] if _has_dist(n,md)}
    except Exception:
        deps={}
    (out/'environment.json').write_text(json.dumps({'python':sys.version,'platform':platform.platform(),'executable':sys.executable,'cwd':os.getcwd(),'dependencies':deps,'env_keys_present':[k for k in os.environ if k.startswith('GSI_') or k.endswith('_DIR')]},ensure_ascii=False,indent=2),encoding='utf-8')
    say('=== GSI OFFLINE DIAGNOSTIC ===')
    say(f'Package: {ROOT}')
    say(f'Data dir: {a.data_dir}')
    say(f'Python: {sys.executable}')
    say(f'Feedback work dir: {out}')
    say('Network access is NOT required.')
    say('Long steps print a heartbeat every 10 seconds. Detailed output is saved in logs.')
    say('')
    steps={}
    say('[1/5] Independent frozen semantic audit (173 cases)')
    try:
        steps['independent']=run_independent(out,env,a.suite_timeout)
    except Exception as ex:
        steps['independent']={'error':f'{type(ex).__name__}: {ex}','traceback':traceback.format_exc()}
    say('[2/5] Extended diagnostic / knowledge-contract suite (77 cases)')
    try:
        steps['extended']=run_extended(out,env,a.suite_timeout)
    except Exception as ex:
        steps['extended']={'error':f'{type(ex).__name__}: {ex}','traceback':traceback.format_exc()}
    say('[3/5] Internal regression files + order-coupling smoke')
    try:
        if not a.skip_internal:
            steps['internal']=run_internal_per_file(out,env,a.per_file_timeout)
            if not a.skip_order_smoke:
                steps['internal_order']=run_internal_order_smoke(out,env,a.suite_timeout)
        else: steps['internal']={'skipped':True}
    except Exception as ex:
        steps['internal']={'error':f'{type(ex).__name__}: {ex}','traceback':traceback.format_exc()}
    say('[4/5] Offline source inventory / schema probe')
    source_inventory={}; ntsw_probe={'status':'NOT_RUN'}
    try:
        inv_path=out/'source_inventory.json'
        inv_cmd=[sys.executable,'-B',str(HERE/'source_inventory_child.py'),str(ROOT),str(a.data_dir or ''),str(inv_path)]
        inv_step=run_cmd(inv_cmd,out,env,min(a.suite_timeout,60),out/'source_inventory_probe.log')
        steps['source_inventory_step']=inv_step
        if inv_path.exists():
            source_inventory=json.loads(inv_path.read_text(encoding='utf-8'))
        else:
            source_inventory={'sources':[],'status':'TIMEOUT' if inv_step.get('timeout') else 'ERROR'}
        probe_out=out/'ntsw_semantic_probe.json'
        cmd=[sys.executable,'-B',str(HERE/'ntsw_probe_child.py'),str(ROOT),str(inv_path),str(probe_out)]
        probe_step=run_cmd(cmd,out,env,min(a.suite_timeout,90),out/'ntsw_probe.log') if inv_path.exists() else {'exit_code':3,'timeout':False,'log':'ntsw_probe.log','error':'source inventory unavailable'}
        steps['ntsw_probe_step']=probe_step
        if probe_out.exists():
            ntsw_probe=json.loads(probe_out.read_text(encoding='utf-8'))
        elif probe_step.get('timeout'):
            ntsw_probe={'status':'TIMEOUT','reason':'NTSW semantic probe exceeded bounded timeout; schema inventory may still be available.'}
        else:
            ntsw_probe={'status':'NOT_RUN' if not inv_path.exists() else 'ERROR','reason':'NTSW semantic probe did not produce output.'}
    except Exception as ex:
        (out/'source_probe_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        ntsw_probe={'status':'ERROR','reason':f'{type(ex).__name__}: {ex}'}
    say('[5/5] Build standardized feedback bundle')
    s=summarize(out,steps,source_inventory,ntsw_probe)
    (out/'feedback_summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'feedback_summary_FA.md').write_text(feedback_md(s),encoding='utf-8')
    # hashes of feedback files to detect truncated/corrupted handoff
    hashes={str(p.relative_to(out)).replace('\\','/'):sha256_file(p) for p in out.rglob('*') if p.is_file() and p.name!='FEEDBACK_SHA256.json'}
    (out/'FEEDBACK_SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    dest=base/(out.name+'.zip'); zip_dir(out,dest)
    say('')
    say('=== GSI OFFLINE DIAGNOSTIC COMPLETE ===')
    say('GATE: '+str(s['release_gate']))
    say('FEEDBACK ZIP: '+str(dest))
    say('SHA256: '+sha256_file(dest))
    return 0 if s['release_gate']=='PASS' else 2

if __name__=='__main__':
    raise SystemExit(main())

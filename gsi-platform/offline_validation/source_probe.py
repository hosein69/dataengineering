from __future__ import annotations
import hashlib, json, os, re, time
from pathlib import Path
from typing import Any

DATA_SUFFIXES={".xlsx",".xlsm",".xls",".csv",".tsv",".parquet",".json",".sqlite",".db"}


def sha256_file(path: Path, max_bytes: int = 50*1024*1024) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        h=hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024), b''):
                h.update(b)
        return h.hexdigest()
    except Exception:
        return None


def _expand(s: str) -> str:
    return os.path.expandvars(str(s or ''))


def _limited_matches(base: Path, pattern: str, max_depth: int = 2):
    """Bounded search for offline data roots; avoids unbounded recursive scans."""
    if not base.exists() or not pattern:
        return []
    out=[]
    try:
        out.extend(base.glob(pattern))
    except Exception:
        pass
    if max_depth >= 1:
        try:
            for d in base.iterdir():
                if d.is_dir():
                    try: out.extend(d.glob(pattern))
                    except Exception: pass
        except Exception:
            pass
    if max_depth >= 2:
        try:
            for d in base.iterdir():
                if not d.is_dir(): continue
                try:
                    for d2 in d.iterdir():
                        if d2.is_dir():
                            try: out.extend(d2.glob(pattern))
                            except Exception: pass
                except Exception:
                    pass
        except Exception:
            pass
    return out


def workbook_schema(path: Path) -> dict[str, Any]:
    out={'path':str(path),'sheets':[],'error':None}
    try:
        from openpyxl import load_workbook
        wb=load_workbook(path, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                header=[]; header_row=None
                for i,row in enumerate(ws.iter_rows(min_row=1,max_row=min(ws.max_row or 1,15),values_only=True),1):
                    vals=['' if v is None else str(v).strip() for v in row]
                    non=[v for v in vals if v]
                    if len(non)>=2:
                        header=[v for v in vals if v]
                        header_row=i; break
                out['sheets'].append({'name':ws.title,'max_row':ws.max_row,'max_column':ws.max_column,
                                      'header_row':header_row,'headers':header[:250]})
        finally:
            wb.close()
    except Exception as ex:
        out['error']=f'{type(ex).__name__}: {ex}'
    return out


def probe_sources(root: Path, data_dir: str = '') -> dict[str, Any]:
    import yaml
    cfg=yaml.safe_load((root/'gsi/config/sources.yaml').read_text(encoding='utf-8'))
    result={'generated_at':time.strftime('%Y-%m-%dT%H:%M:%S'), 'sources':[], 'data_dir':data_dir or None}
    extra=Path(data_dir).expanduser() if data_dir else None
    for key,s in (cfg.get('sources') or {}).items():
        if not s.get('enabled',True):
            result['sources'].append({'source':key,'enabled':False,'status':'DISABLED'}); continue
        folder=Path(_expand(s.get('folder',''))) if s.get('folder') else None
        candidates=[]
        if folder and str(folder) and folder.exists():
            for name in s.get('file_names') or []:
                p=folder/name
                if p.exists(): candidates.append(p)
            pat=s.get('pattern')
            if pat:
                try: candidates.extend(folder.glob(pat))
                except Exception: pass
        if extra and extra.exists():
            patterns=[]
            if s.get('pattern'): patterns.append(s['pattern'])
            patterns.extend(s.get('file_names') or [])
            for pat in patterns:
                try: candidates.extend(_limited_matches(extra, pat, max_depth=2))
                except Exception: pass
            if key=='ntsw':
                for n in ('NTSW-IKCO.xlsx','NTSW.xlsx'):
                    p=extra/n
                    if p.exists(): candidates.append(p)
        uniq=[]; seen=set()
        expected_sheets=set(s.get('sheets') or [])
        for p in candidates:
            # Source inventory is a data-file probe, not a repository text/code
            # search. Broad filename patterns must never promote .py/.md files
            # into business sources. Sources with declared sheets must be actual
            # Excel workbooks containing at least one declared sheet.
            if p.suffix.lower() not in DATA_SUFFIXES:
                continue
            if expected_sheets:
                if p.suffix.lower() not in {'.xlsx','.xlsm','.xls'}:
                    continue
                if p.suffix.lower() in {'.xlsx','.xlsm'}:
                    schema=workbook_schema(p)
                    names={x.get('name') for x in schema.get('sheets',[])}
                    if not names.intersection(expected_sheets):
                        continue
            try: rp=p.resolve()
            except Exception: rp=p
            if rp not in seen and p.is_file(): seen.add(rp); uniq.append(p)
        files=[]
        for p in uniq[:10]:
            try:
                st=p.stat(); item={'path':str(p),'size_bytes':st.st_size,'mtime':st.st_mtime,
                    'sha256':sha256_file(p),'schema':workbook_schema(p) if p.suffix.lower() in {'.xlsx','.xlsm'} else None}
            except Exception as ex:
                item={'path':str(p),'error':f'{type(ex).__name__}: {ex}'}
            files.append(item)
        status='FOUND' if files else ('MISSING_REQUIRED' if s.get('required') else 'MISSING_OPTIONAL')
        result['sources'].append({'source':key,'role':s.get('role'),'required':bool(s.get('required')),
            'join_on':s.get('join_on'),'expected_sheets':s.get('sheets'),'configured_folder':str(folder) if folder else '',
            'status':status,'files':files})
    return result


def probe_ntsw_semantics(root: Path, source_inventory: dict[str,Any]) -> dict[str,Any]:
    out={'status':'NOT_RUN','reason':'NTSW_FILE_NOT_FOUND'}
    ntsw=next((x for x in source_inventory.get('sources',[]) if x.get('source')=='ntsw'),None)
    if not ntsw or not ntsw.get('files'): return out
    path=Path(ntsw['files'][0]['path'])
    try:
        import pandas as pd
        from gsi.adapters.a50_ntsw import NtswAdapter
        with pd.ExcelFile(path) as xl:
            wanted=[s for s in ('Import License','Import Licence','Allocation','Release Commitment','Custom Declaration') if s in xl.sheet_names]
            sheets={s:pd.read_excel(xl,sheet_name=s,dtype=object) for s in wanted}
        if not wanted:
            return {'status':'ERROR','reason':'NTSW_REQUIRED_SHEETS_NOT_FOUND','file':str(path)}
        transformed=NtswAdapter().transform(sheets)
        stats={'file':str(path),'sheet_rows':{k:int(len(v)) for k,v in sheets.items()},'frames':{k:int(len(v)) for k,v in transformed.items()}}
        lic=transformed.get('import_license')
        if lic is not None:
            def nn(col):
                if col not in lic: return 0
                return int(lic[col].astype(str).str.strip().replace({'nan':'','None':'','<NA>':''}).ne('').sum())
            stats['import_license']={'rows':int(len(lic)),'reg_file_nonempty':nn('KEY_REG_FILE'),'reg_nonempty':nn('KEY_REG'),'order_nonempty':nn('KEY_ORDER')}
            pairs=lic[['KEY_REG_FILE','KEY_REG']].copy() if {'KEY_REG_FILE','KEY_REG'}.issubset(lic.columns) else None
            if pairs is not None:
                pairs=pairs[(pairs.KEY_REG_FILE.astype(str).str.strip()!='')&(pairs.KEY_REG.astype(str).str.strip()!='')]
                stats['import_license']['reg_file_reg_pairs']=int(len(pairs.drop_duplicates()))
                stats['import_license']['regfile_multi_reg']=int((pairs.groupby('KEY_REG_FILE').KEY_REG.nunique()>1).sum()) if len(pairs) else 0
                stats['import_license']['reg_multi_regfile']=int((pairs.groupby('KEY_REG').KEY_REG_FILE.nunique()>1).sum()) if len(pairs) else 0
        out={'status':'OK','stats':stats}
    except Exception as ex:
        out={'status':'ERROR','reason':f'{type(ex).__name__}: {ex}','file':str(path)}
    return out

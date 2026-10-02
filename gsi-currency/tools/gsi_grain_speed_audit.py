"""Read-only GSI source/grain/speed audit; writes one Excel workbook locally.

Run where source directories are accessible:
  python -m tools.gsi_grain_speed_audit --output GSI_DIAGNOSTIC.xlsx
Optional: --warehouse D:\\GSI_DATA\\warehouse.sqlite
Never writes to the production warehouse.
"""
from __future__ import annotations
import argparse
import hashlib
import sqlite3
import time
import zipfile
from pathlib import Path

import pandas as pd
from gsi.config.sources import get_source
from gsi.dataio.reader import find_files
from gsi.adapters.a10_abbasi import AbbasiAdapter
from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.warehouse.reliability import validate_frame


def inspect(path, source, role, records, timings, frames, conflicts):
    start=time.perf_counter()
    try:
        before=path.stat(); blob=path.read_bytes(); after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise RuntimeError('FILE_CHANGED_DURING_READ')
        timings.append([source,role,path.name,'network_read',round(time.perf_counter()-start,3),len(blob)])
        t=time.perf_counter(); digest=hashlib.sha256(blob).hexdigest()
        timings.append([source,role,path.name,'sha256',round(time.perf_counter()-t,3),len(blob)])
        t=time.perf_counter()
        with zipfile.ZipFile(path) as z:
            members=[x for x in z.infolist() if x.filename.startswith('xl/worksheets/') and x.filename.endswith('.xml')]
            total_xml=sum(x.file_size for x in members)
            xml_max=max((x.file_size for x in members),default=0)
        timings.append([source,role,path.name,'zip_metadata',round(time.perf_counter()-t,3),len(members)])
        t=time.perf_counter()
        with pd.ExcelFile(path) as book:
            sheets=list(book.sheet_names); expected=list(get_source(source).sheets)
            wanted={x.strip().casefold() for x in expected}
            chosen=next((s for s in sheets if s.strip().casefold() in wanted),None)
            if chosen is None:
                if role=='BASE':
                    records.append([source,role,path.name,after.st_size,digest,','.join(sheets),'',0,
                                    len(members),total_xml,xml_max,'NO_CONTRACTED_SHEET',''])
                    return
                chosen=sheets[0] if sheets else None
                if chosen is None:
                    records.append([source,role,path.name,after.st_size,digest,'','',0,
                                    len(members),total_xml,xml_max,'NO_SHEET',''])
                    return
            frame=book.parse(chosen,dtype=str)
        timings.append([source,role,path.name,'pandas_parse_contracted',round(time.perf_counter()-t,3),len(frame)])
        records.append([source,role,path.name,after.st_size,digest,','.join(sheets),chosen,len(frame),
                        len(members),total_xml,xml_max,
                        'OK' if chosen.strip().casefold() in wanted else 'REVIEW_ONLY_NONCONTRACTED_SHEET',
                        ' | '.join(str(c) for c in frame.columns)[:30000]])
        if role!='BASE':return
        t=time.perf_counter()
        try:
            result=(AbbasiAdapter() if source=='abbasi' else MoghavematAdapter()).transform({chosen:frame})
            timings.append([source,role,path.name,'adapter_transform',round(time.perf_counter()-t,3),
                            sum(len(v) for v in result.values())])
            for name,df in result.items():
                checks=validate_frame(source+'/'+name,df)
                frames.append([source,name,len(df),len(df.columns),
                               ','.join(c.code for c in checks if not c.passed),
                               ','.join(c.code for c in checks if not c.passed and c.severity in ('BLOCK','CRITICAL','FATAL'))])
                if source=='moghavemat' and name=='main' and {'KEY_ORDER','KEY_MATERIAL'}<=set(df):
                    keyed=df[df.KEY_ORDER.fillna('').astype(str).ne('') & df.KEY_MATERIAL.fillna('').astype(str).ne('')]
                    dup=keyed[keyed.duplicated(['KEY_ORDER','KEY_MATERIAL'],keep=False)]
                    for order,material in dup[['KEY_ORDER','KEY_MATERIAL']].drop_duplicates().head(100).itertuples(index=False,name=None):
                        conflicts.append([source,name,'DUPLICATE_ORDER_MATERIAL',order,material,''])
        except Exception as exc:
            timings.append([source,role,path.name,'adapter_transform_ERROR',round(time.perf_counter()-t,3),0])
            conflicts.append([source,'adapter',type(exc).__name__,'','',str(exc)[:500]])
    except Exception as exc:
        timings.append([source,role,path.name,'ERROR',round(time.perf_counter()-start,3),0])
        records.append([source,role,path.name,0,'','','',0,0,0,0,f'{type(exc).__name__}: {exc}'[:500],''])


def warehouse_events(path, events):
    if path is None:return
    uri='file:'+Path(path).resolve().as_posix()+'?mode=ro'
    with sqlite3.connect(uri,uri=True,timeout=5) as conn:
        conn.execute('PRAGMA query_only=ON')
        for row in conn.execute('SELECT r.seq,r.id,r.started,r.finished,r.status,c.slot '
                                'FROM wh_run r LEFT JOIN wh_current c ON c.run_id=r.id ORDER BY r.seq DESC LIMIT 10'):
            events.append(['run',*row])
        try:
            for row in conn.execute('SELECT source,mode,round(seconds,3),run_id FROM wh_source_load '
                                    "WHERE source IN ('abbasi','moghavemat') ORDER BY rowid DESC LIMIT 20"):
                events.append(['load',*row,''])
        except sqlite3.OperationalError:pass


def clearance_inventory(rows):
    """Explain why a discovered clearance workbook did or did not enter main."""
    from gsi.dataio.reader import clearance_header, source_targets
    spec,paths=source_targets('clearance',quiet=True)
    skip={str(x).strip().casefold() for x in (spec.opt('skip_sheets') or [])}
    for file in paths:
        try:
            with pd.ExcelFile(file) as book:
                for sheet in book.sheet_names:
                    if sheet.strip().casefold() in skip:
                        rows.append([Path(file).name,sheet,'SKIP_HELPER',''])
                        continue
                    found=clearance_header(book,sheet)
                    contracted=found['header_row'] is not None
                    state=('EXPORT_REVIEW_ONLY' if 'export' in Path(file).name.casefold()
                           else 'IMPORT_MAIN') if contracted else 'SCHEMA_NOT_MATCHED'
                    if not contracted and found['missing']:
                        state+=' (missing: '+', '.join(found['missing'])+')'
                    rows.append([Path(file).name,sheet,state,' | '.join(map(str,found['headers']))[:30000]])
        except Exception as exc:
            rows.append([Path(file).name,'','READ_ERROR',f'{type(exc).__name__}: {exc}'[:500]])


def run(output, warehouse=None):
    records=[];timings=[];frames=[];conflicts=[];events=[];clearance=[]
    for source in ('abbasi','moghavemat'):
        spec=get_source(source);base_names={n.casefold() for n in spec.opt('file_names',[])}
        selected={Path(p).resolve() for p in find_files(spec,quiet=True)}
        candidates=[]
        for p in Path(spec.folder).glob('*.xls*') if Path(spec.folder).is_dir() else []:
            if p.name.startswith('~$'):continue
            low=p.name.casefold()
            if source=='abbasi' and 'tracking' in low and 'bls' in low:candidates.append(p)
            if source=='moghavemat' and 'commercial expert data' in low:candidates.append(p)
        for path in sorted(candidates,key=lambda p:p.stat().st_mtime_ns,reverse=True):
            role='BASE' if path.name.casefold() in base_names and path.resolve() in selected else 'VARIANT_REVIEW_ONLY'
            inspect(path,source,role,records,timings,frames,conflicts)
        if not any(r[0]==source and r[1]=='BASE' and r[11]=='OK' for r in records):
            conflicts.append([source,'source','BASE_MISSING_OR_INVALID','','',','.join(spec.opt('file_names',[]))])
    try:warehouse_events(warehouse,events)
    except Exception as exc:events.append(['warehouse_error',str(exc),'','','','',''])
    clearance_inventory(clearance)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with pd.ExcelWriter(output,engine='openpyxl') as writer:
        for sheet,rows,columns in [
            ('Files',records,['source','role','file','bytes','sha256','sheets','contract_sheet','rows','xml_sheets','xml_uncompressed_bytes','largest_xml_bytes','status','headers']),
            ('Timings',timings,['source','role','file','stage','seconds','count_or_bytes']),
            ('Frames',frames,['source','frame','rows','columns','failed_checks','blocking_checks']),
            ('Conflicts',conflicts,['source','frame','code','key_order','key_material','detail']),
            ('ClearanceFiles',clearance,['file','sheet','disposition','headers']),
            ('WarehouseRuns',events,['type','a','b','c','d','e','f'])]:
            pd.DataFrame(rows,columns=columns).to_excel(writer,sheet_name=sheet,index=False)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--warehouse')
    args=parser.parse_args()
    print(run(args.output,args.warehouse))

if __name__=='__main__':main()

"""Read OOXML directly: preserve physical cells, hidden rows, formula/cache and source bytes.
No row filtering based on Excel display state. No forward-fill of transaction amounts.

Performance invariants
----------------------
* Original source bytes are still hashed and archived on every ingest attempt.
* Physical-cell audit is content-addressed by the archived file SHA-256. If the
  exact same workbook bytes were already captured completely, repeated runs do
  not parse every worksheet XML again.
* Callers that only need the immutable archive can opt out of retaining the full
  Python ``sheets`` object. This prevents a second in-memory copy of large source
  workbooks while keeping every physical row in SQLite.
"""
from io import BytesIO
import os
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from .store import Warehouse, dumps, loads

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def colno(ref):
    n=0
    for c in ref:
        if c.isdigit():break
        n=n*26+ord(c.upper())-64
    return n


def _workbook_sheets(z):
    """Return ``[(sheet_xml_element, member_path), ...]`` without parsing sheets."""
    rels={r.attrib['Id']:r.attrib['Target']
          for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    items=[]
    for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
        target=rels[sh.attrib[R]]
        member=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        items.append((sh,member))
    return items


def _shared_strings(z):
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    root=ET.fromstring(z.read('xl/sharedStrings.xml'))
    return [''.join(t.text or '' for t in e.findall('.//s:t',NS))
            for e in root.findall('s:si',NS)]


def _parse_sheet(z, sh, member, strings):
    """Parse one worksheet into the exact physical-row audit representation."""
    tree=ET.fromstring(z.read(member)); rows=[]; issues=[]
    for row in tree.findall('s:sheetData/s:row',NS):
        cells=[]
        for cell in row.findall('s:c',NS):
            value=cell.find('s:v',NS);formula=cell.find('s:f',NS);typ=cell.get('t','n')
            raw=value.text if value is not None else None
            val=raw
            if typ=='s' and raw is not None: val=strings[int(raw)]
            if typ=='inlineStr':val=''.join(t.text or '' for t in cell.findall('.//s:t',NS))
            if raw is None and val is None and formula is None:continue
            cells.append({'address':cell.get('r'),'type':typ,'style':cell.get('s'),
                          'raw':raw,'value':val,
                          'formula':formula.text if formula is not None else None})
            if typ=='e' or (formula is not None and raw is None):
                issues.append((int(row.get('r')),cell.get('r'),
                               'CELL_ERROR' if typ=='e' else 'FORMULA_NO_CACHE'))
        if cells:
            rows.append({'row':int(row.get('r')),'hidden':row.get('hidden')=='1','cells':cells})
    meta={'state':sh.get('state','visible'),'nonempty_rows':len(rows),
          'hidden_rows':sum(r['hidden'] for r in rows),
          'merges':[e.get('ref') for e in tree.findall('s:mergeCells/s:mergeCell',NS)],
          'columns':[e.attrib for e in tree.findall('s:cols/s:col',NS)]}
    return rows,issues,meta


def _archived_sheet_names(wh, fid):
    with wh.db() as c:
        return {r[0] for r in c.execute('SELECT name FROM wh_sheet WHERE file_id=?',(fid,))}


def _load_archived_rows(wh, fid, name):
    with wh.db() as c:
        return [loads(r[0]) for r in c.execute(
            'SELECT payload FROM wh_raw_row WHERE file_id=? AND sheet=? ORDER BY row_no',
            (fid,name))]


def _store_sheet(wh, fid, name, meta, rows):
    try:
        chunk=max(1,int(os.environ.get('GSI_WAREHOUSE_RAW_CHUNK_ROWS','1000')))
    except (TypeError,ValueError):
        chunk=1000
    with wh.db() as c:
        c.execute('INSERT INTO wh_sheet VALUES(?,?,?)',(fid,name,dumps(meta)))
        batch=[]
        for r in rows:
            batch.append((fid,name,r['row'],dumps(r)))
            if len(batch)>=chunk:
                c.executemany('INSERT INTO wh_raw_row VALUES(?,?,?,?)',batch)
                batch.clear()
        if batch:
            c.executemany('INSERT INTO wh_raw_row VALUES(?,?,?,?)',batch)


def capture(path,source,keep_sheets=True):
    """Archive exact source bytes and physical-cell evidence.

    ``keep_sheets=False`` is intended for legacy readers that will parse the
    archived workbook with pandas afterwards. The physical audit is still fully
    persisted; only the redundant Python copy is omitted from the return value.
    """
    path=Path(path); before=path.stat(); content=path.read_bytes(); after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise RuntimeError('فایل هنگام خواندن تغییر کرد؛ دوباره اجرا کنید.')
    wh=Warehouse();fid=wh.blob(content,path.name,source,str(path))
    if path.suffix.lower() not in ('.xlsx','.xlsm'):
        wh.issue('LEGACY_FORMAT','Original bytes retained; convert to XLSX for physical-cell audit',fid)
        return fid,content,{}

    sheets={} if keep_sheets else None
    with zipfile.ZipFile(BytesIO(content)) as z:
        workbook=_workbook_sheets(z)
        workbook_names=[sh.attrib['name'] for sh,_ in workbook]
        archived=_archived_sheet_names(wh,fid)
        missing=[(sh,member) for sh,member in workbook if sh.attrib['name'] not in archived]

        # Exact bytes + all workbook sheet names already archived means the
        # physical-cell representation is immutable and can be reused safely.
        # Legacy readers do not need it in Python at all.
        if not missing:
            if keep_sheets:
                for name in workbook_names:
                    sheets[name]=_load_archived_rows(wh,fid,name)
            return fid,content,sheets or {}

        # Shared strings can dominate memory; only build them if at least one
        # worksheet actually needs first-time physical parsing.
        strings=_shared_strings(z)
        missing_names={sh.attrib['name'] for sh,_ in missing}
        for sh,member in workbook:
            name=sh.attrib['name']
            if name not in missing_names:
                if keep_sheets:
                    sheets[name]=_load_archived_rows(wh,fid,name)
                continue
            rows,issues,meta=_parse_sheet(z,sh,member,strings)
            _store_sheet(wh,fid,name,meta,rows)
            if keep_sheets:
                sheets[name]=rows
            for row,address,code in issues:
                wh.issue(code,{'cell':address},fid,name,row)
    return fid,content,sheets or {}


def header_normal(value):
    return ' '.join(str(value or '').translate(str.maketrans('يك','یک')).replace('\u200c',' ').split()).strip()


def frame(rows,source,sheet,fid):
    if not rows:return pd.DataFrame()
    # Operational sheets have a header signature; titles are never guessed as data.
    signatures={'oracle':{'شماره فنی'},'fx_transaction':{'ثبت سفارش','سفارش','نام بانک'},'ntsw':set()}
    wanted=signatures.get(source,set())
    candidates=[]
    for r in rows[:20]:
        vals={header_normal(c['value']) for c in r['cells']}
        score=len(vals & wanted)
        if not wanted or score:candidates.append((score,-r['row'],r))
    if not candidates:return pd.DataFrame()
    hdr=max(candidates,key=lambda x:(x[0],x[1]))[2] if wanted else rows[0]
    if source=='fx_transaction' and max(x[0] for x in candidates)<2:return pd.DataFrame()
    width=max(colno(c['address']) for r in rows for c in r['cells']); names=['']*width
    for c in hdr['cells']:names[colno(c['address'])-1]=header_normal(c['value'])
    seen={};headers=[]
    for i,name in enumerate(names):
        name=name or f'__unnamed_{i+1}';seen[name]=seen.get(name,0)+1
        headers.append(name if seen[name]==1 else f'{name}__{seen[name]}')
    data=[];indexes=[]
    for r in rows:
        if r['row']<=hdr['row']:continue
        values=[None]*width
        for c in r['cells']:values[colno(c['address'])-1]=None if c['type']=='e' else c['value']
        data.append(values);indexes.append(r['row'])
    out=pd.DataFrame(data,columns=headers,index=indexes)
    out['_SOURCE_ROW']=indexes;out['_SOURCE_SHEET']=sheet;out['_SOURCE_FILE_ID']=fid
    return out

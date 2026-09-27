"""Read OOXML directly: preserve physical cells, hidden rows, formula/cache and source bytes.
No row filtering based on Excel display state. No forward-fill of transaction amounts.
"""
from io import BytesIO
from pathlib import Path, PurePosixPath
import posixpath
import xml.etree.ElementTree as ET
import zipfile
import pandas as pd
from .store import Warehouse,dumps
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
def colno(ref):
    n=0
    for c in ref:
        if c.isdigit():break
        n=n*26+ord(c.upper())-64
    return n

def capture(path,source):
    path=Path(path); before=path.stat(); content=path.read_bytes(); after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise RuntimeError('فایل هنگام خواندن تغییر کرد؛ دوباره اجرا کنید.')
    wh=Warehouse();fid=wh.blob(content,path.name,source,str(path))
    if path.suffix.lower() not in ('.xlsx','.xlsm'):
        wh.issue('LEGACY_FORMAT','Original bytes retained; convert to XLSX for physical-cell audit',fid)
        return fid,content,{}
    sheets={}
    with zipfile.ZipFile(BytesIO(content)) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(t.text or '' for t in e.findall('.//s:t',NS)) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            name=sh.attrib['name']; target=rels[sh.attrib[R]]
            member=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
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
                    cells.append({'address':cell.get('r'),'type':typ,'style':cell.get('s'),'raw':raw,'value':val,'formula':formula.text if formula is not None else None})
                    if typ=='e' or (formula is not None and raw is None): issues.append((int(row.get('r')),cell.get('r'),'CELL_ERROR' if typ=='e' else 'FORMULA_NO_CACHE'))
                if cells: rows.append({'row':int(row.get('r')),'hidden':row.get('hidden')=='1','cells':cells})
            meta={'state':sh.get('state','visible'),'nonempty_rows':len(rows),'hidden_rows':sum(r['hidden'] for r in rows),'merges':[e.get('ref') for e in tree.findall('s:mergeCells/s:mergeCell',NS)],'columns':[e.attrib for e in tree.findall('s:cols/s:col',NS)]}
            sheets[name]=rows
            with wh.db() as c:
                sheet_seen=c.execute('SELECT 1 FROM wh_sheet WHERE file_id=? AND name=?',(fid,name)).fetchone()
            if not sheet_seen:
                with wh.db() as c:
                    c.execute('INSERT INTO wh_sheet VALUES(?,?,?)',(fid,name,dumps(meta)))
                    c.executemany('INSERT INTO wh_raw_row VALUES(?,?,?,?)',[(fid,name,r['row'],dumps(r)) for r in rows])
                for row,address,code in issues:wh.issue(code,{'cell':address},fid,name,row)
    return fid,content,sheets

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
        if not wanted or score: candidates.append((score,-r['row'],r))
    if not candidates:return pd.DataFrame()
    hdr=max(candidates,key=lambda x:(x[0],x[1]))[2] if wanted else rows[0]
    if source=='fx_transaction' and max(x[0] for x in candidates)<2:return pd.DataFrame()
    width=max(colno(c['address']) for r in rows for c in r['cells']); names=['']*width
    for c in hdr['cells']: names[colno(c['address'])-1]=header_normal(c['value'])
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

"""Read OOXML directly: preserve physical cells, hidden rows, formula/cache and source bytes.
No row filtering based on Excel display state. No forward-fill of transaction amounts.

Performance invariants
----------------------
* Original source bytes are hashed on every ingest attempt and stored once per
  distinct content in the object store next to the SQLite file.
* Physical-cell audit is content-addressed by the archived file SHA-256: one
  compressed JSON Lines object per worksheet, parsed only the first time the
  exact workbook bytes are seen.
* Callers that only need the immutable archive can opt out of retaining the full
  Python ``sheets`` object.
"""
from io import BytesIO
import gzip
import json
import os
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
import zipfile
import time

import pandas as pd

from .store import Warehouse, dumps
from ..dataio.logging_setup import log

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


def _archived_sheets(wh, fid):
    """{sheet name: object sha} of the physical-cell archive already stored for this file."""
    with wh.db() as c:
        return {r[0]: r[1] for r in c.execute('SELECT name,object_sha FROM wh_sheet WHERE file_id=?',(fid,))}


def _load_archived_rows(wh, fid, name, sha=None):
    if sha is None:
        sha = _archived_sheets(wh, fid).get(name)
    if not sha:
        return []
    raw = gzip.decompress(wh.objects.get(sha, 'jsonl.gz'))
    return [json.loads(line) for line in raw.decode('utf-8').splitlines() if line]


def _pack_rows(rows):
    """Physical rows ← JSON Lines فشرده و قطعی (mtime=0)، بدون ساختن یک رشته عظیم."""
    buf = BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=6, mtime=0) as gz:
        for r in rows:
            gz.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            gz.write(b'\n')
    return buf.getvalue()


def _store_sheet(wh, fid, name, meta, rows):
    data = _pack_rows(rows)
    meta = dict(meta, stored_rows=len(rows), archive_bytes=len(data))
    with wh.db() as c:
        sha = wh.put_object(c, data, 'jsonl.gz', 'sheet')
        c.execute('INSERT OR IGNORE INTO wh_sheet(file_id,name,metadata,object_sha) VALUES(?,?,?,?)',
                  (fid, name, dumps(meta), sha))
    return sha


#: بایت‌هایی که بررسی «فایل عوض شده؟» همین حالا خوانده؛ capture همان را دوباره از دیسک نمی‌خواند
_PREREAD: dict = {}


def remember_bytes(path, stat, content):
    _PREREAD[str(Path(path))] = ((stat.st_size, stat.st_mtime_ns), content)


def forget_bytes(path=None):
    if path is None:
        _PREREAD.clear()
    else:
        _PREREAD.pop(str(Path(path)), None)


def _read_stable(path):
    before = path.stat()
    held = _PREREAD.get(str(path))
    if held is not None and held[0] == (before.st_size, before.st_mtime_ns):
        return held[1]
    content = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError('فایل هنگام خواندن تغییر کرد؛ دوباره اجرا کنید.')
    return content


def capture(path,source,keep_sheets=True,archive_sheets=None):
    """Archive exact source bytes and physical-cell evidence.

    The bytes go to the content-addressed object store once per distinct content;
    each worksheet's physical rows become one compressed JSON Lines object, parsed
    only the first time that exact workbook is seen. ``keep_sheets=False`` is for
    legacy readers that parse the archived bytes with pandas afterwards.
    ``archive_sheets`` limits the optional physical-cell index to contracted
    sheets. Exact original bytes remain archived, so skipped sheets can be
    indexed later without losing evidence. Never use with ``keep_sheets=True``.
    """
    if archive_sheets is not None and keep_sheets:
        raise ValueError('archive_sheets requires keep_sheets=False')
    start=time.perf_counter()
    path=Path(path); content=_read_stable(path)
    read_elapsed=time.perf_counter()-start
    store_start=time.perf_counter()
    wh=Warehouse();fid=wh.blob(content,path.name,source,str(path))
    store_elapsed=time.perf_counter()-store_start
    if path.suffix.lower() not in ('.xlsx','.xlsm'):
        wh.issue('LEGACY_FORMAT','Original bytes retained; convert to XLSX for physical-cell audit',fid)
        return fid,content,{}

    sheets={} if keep_sheets else None
    with zipfile.ZipFile(BytesIO(content)) as z:
        workbook=_workbook_sheets(z)
        workbook_names=[sh.attrib['name'] for sh,_ in workbook]
        archived=_archived_sheets(wh,fid)
        wanted = None if archive_sheets is None else {str(name).strip().casefold() for name in archive_sheets}
        missing=[(sh,member) for sh,member in workbook
                 if sh.attrib['name'] not in archived
                 and (wanted is None or sh.attrib['name'].strip().casefold() in wanted)]

        # Exact bytes + all workbook sheet names already archived means the
        # physical-cell representation is immutable and can be reused safely.
        if not missing:
            if keep_sheets:
                for name in workbook_names:
                    sheets[name]=_load_archived_rows(wh,fid,name,archived.get(name))
            log.info('[source-timing] %s %s capture_read=%.3fs object_store=%.3fs physical_index=0s cached=1',
                     source,path.name,read_elapsed,store_elapsed)
            return fid,content,sheets or {}

        # Shared strings can dominate memory; only build them if at least one
        # worksheet actually needs first-time physical parsing.
        strings=_shared_strings(z)
        missing_names={sh.attrib['name'] for sh,_ in missing}
        for sh,member in workbook:
            name=sh.attrib['name']
            if name not in missing_names:
                if keep_sheets:
                    sheets[name]=_load_archived_rows(wh,fid,name,archived.get(name))
                continue
            sheet_start=time.perf_counter()
            rows,issues,meta=_parse_sheet(z,sh,member,strings)
            _store_sheet(wh,fid,name,meta,rows)
            log.info('[source-timing] %s %s sheet=%s physical_parse_store=%.3fs rows=%d',
                     source,path.name,name,time.perf_counter()-sheet_start,len(rows))
            if keep_sheets:
                sheets[name]=rows
            for row,address,code in issues:
                wh.issue(code,{'cell':address},fid,name,row)
    log.info('[source-timing] %s %s capture_read=%.3fs object_store=%.3fs physical_index=%.3fs sheets=%d',
             source,path.name,read_elapsed,store_elapsed,time.perf_counter()-store_start-store_elapsed,len(missing))
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

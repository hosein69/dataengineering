from .store import Warehouse,RUN,dumps,loads
from .excel import capture,frame
from .numeric import decimal_text

def ingest_file(path,source):
    wh=Warehouse()
    with wh.run({'operation':'ingest','source':source}) as rid:
        fid,blob,sheets=capture(path,source)
        result={}
        for name,rows in sheets.items():
            df=frame(rows,source,name,fid)
            # Raw bytes/cells retain the original evidence; prohibited Oracle values
            # are excluded from every analytical/staging frame.
            if source=='oracle':
                forbidden={'وضعیت','قطعه بحرانی','شماره نامه','تاریخ ثبت','توضیحات','شماره پرسنلی','کارشناس خرید خارجی','ریسک پذیری','Column18'}
                df=df.drop(columns=[c for c in df if c in forbidden],errors='ignore')
            if not df.empty:
                from .marts import stage
                stage(df,source,name,fid)
                result[name]=df
                wh.frame(df,'staging',source+'/'+name)
        if source in ('oracle','fx_transaction','ntsw'):
            from ..adapters import discover as discover_adapters
            adapter=discover_adapters()[source]()
            outputs=adapter.transform(result)
            for name,df in outputs.items():wh.frame(df,'standardized',source+'/'+name)
        wh.audit('ingest_complete',{'file_id':fid,'source':source,'sheets':len(sheets)})
    return rid,fid

def last_report(ref_date):
    wh=Warehouse()
    with wh.db() as c:
        row=c.execute("SELECT r.id,r.context FROM wh_current v JOIN wh_run r ON r.id=v.run_id WHERE v.slot='report' AND r.status='completed'").fetchone()
        if not row or loads(row[1]).get('reference_date')!=ref_date:return None
        frames=c.execute("SELECT name,id FROM wh_frame WHERE run_id=? AND layer='mart' ORDER BY created",(row[0],)).fetchall()
        metadata=c.execute("SELECT payload FROM wh_audit WHERE run_id=? AND kind='report_metadata' ORDER BY id DESC LIMIT 1",(row[0],)).fetchone()
    data={name:wh.read_frame(fid) for name,fid in frames}
    meta=loads(metadata[0]) if metadata else {}
    extras=meta.get('extras',{})
    extras.update({k[7:]:v for k,v in data.items() if k.startswith('extras/')})
    extras['warehouse_run_id']=row[0]
    return data['df'],data['main'],extras,meta.get('report','')

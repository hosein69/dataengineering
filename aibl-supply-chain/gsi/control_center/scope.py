"""Operator-managed explicit recipient scope; directory role is never authorization."""
from gsi.warehouse.store import Warehouse,loads
from gsi.core.text import clean_employee_code

def warehouse_context(employee_code,membership):
    wh=Warehouse()
    with wh.db() as c:
        row=c.execute("SELECT r.id,r.context FROM wh_current t JOIN wh_run r ON t.run_id=r.id WHERE t.slot='report' AND r.status='completed'").fetchone()
        if not row:return None
        frame=c.execute("SELECT id FROM wh_frame WHERE run_id=? AND layer='mart' AND name='main' ORDER BY created DESC LIMIT 1",(row[0],)).fetchone()
    if not frame:return None
    df=wh.read_frame(frame[0])
    if 'KEY_EMP' not in df:raise ValueError('کلید پرسنلی در خروجی وجود ندارد؛ دامنه مخاطب قابل اثبات نیست.')
    codes={clean_employee_code(employee_code)}
    explicit=str(membership.get('scope_employee_codes','') or '')
    if explicit:codes.update(clean_employee_code(x.strip()) for x in explicit.split(','))
    allowed=df[df['KEY_EMP'].map(clean_employee_code).isin(codes)]
    from gsi.personalization.publisher import frame_payload
    payload=frame_payload(allowed,fields=list(allowed.columns),max_rows=max(1,len(allowed)),ref_date=loads(row[1])['reference_date'])
    payload['warehouse_run_id']=row[0]
    wh.audit('recipient_scope',{'recipient':employee_code,'cluster':membership['cluster_id'],'source_run':row[0],'rows':len(allowed),'scope_employee_codes':sorted(codes)})
    return payload

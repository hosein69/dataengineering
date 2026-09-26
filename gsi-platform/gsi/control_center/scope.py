"""Operator-managed recipient scope; cluster membership is explicit authorization."""
from gsi.warehouse.store import Warehouse,loads
from gsi.core.text import clean_employee_code


def resolve_scope_codes(cfg, employee_code, membership):
    """Return the explicit employee-code universe authorized for one recipient.

    Expert: self only. Manager: self + active expert members in the same cluster.
    Executive: all active members in the same cluster. Explicit
    ``scope_employee_codes`` always augments that set.  Organisation titles from
    HR are deliberately *not* authorization.
    """
    self_code=clean_employee_code(employee_code)
    codes={self_code}
    level=str(membership.get('level') or 'expert')
    cid=str(membership.get('cluster_id') or '')
    if cfg and level in {'manager','executive'} and cid:
        for m in cfg.get('memberships',[]):
            if not m.get('active') or str(m.get('cluster_id') or '')!=cid:
                continue
            ml=str(m.get('level') or 'expert')
            if level=='manager' and ml!='expert':
                continue
            try: codes.add(clean_employee_code(m.get('employee_code','')))
            except Exception: pass
    explicit=str(membership.get('scope_employee_codes','') or '')
    if explicit:
        for raw in explicit.split(','):
            raw=raw.strip()
            if raw: codes.add(clean_employee_code(raw))
    return {c for c in codes if c}


def warehouse_context(employee_code,membership,cfg=None):
    wh=Warehouse()
    with wh.db() as c:
        row=c.execute("SELECT r.id,r.context FROM wh_current t JOIN wh_run r ON t.run_id=r.id WHERE t.slot='report' AND r.status='completed'").fetchone()
        if not row:return None
        frame=c.execute("SELECT id FROM wh_frame WHERE run_id=? AND layer='mart' AND name='main' ORDER BY created DESC LIMIT 1",(row[0],)).fetchone()
    if not frame:return None
    df=wh.read_frame(frame[0])
    if 'KEY_EMP' not in df:raise ValueError('کلید پرسنلی در خروجی وجود ندارد؛ دامنه مخاطب قابل اثبات نیست.')
    codes=resolve_scope_codes(cfg,employee_code,membership)
    allowed=df[df['KEY_EMP'].map(clean_employee_code).isin(codes)]
    from gsi.personalization.publisher import frame_payload
    payload=frame_payload(allowed,fields=list(allowed.columns),max_rows=max(1,len(allowed)),ref_date=loads(row[1])['reference_date'])
    payload['warehouse_run_id']=row[0]
    wh.audit('recipient_scope',{'recipient':employee_code,'cluster':membership['cluster_id'],'level':membership.get('level','expert'),'source_run':row[0],'rows':len(allowed),'scope_employee_codes':sorted(codes),'scope_basis':'cluster_membership+explicit_override'})
    return payload

"""Explicit organization fields and conservative, reviewable Excel header suggestions."""
from gsi.warehouse.excel import header_normal
LABELS={'employee_code':'کد پرسنلی','name':'نام و نام خانوادگی','first_name':'نام','last_name':'نام خانوادگی','email':'ایمیل','management':'مدیریت','department':'اداره','position':'جایگاه سازمانی','level':'سطح گزارش','cluster_id':'شناسه کلاستر','active':'فعال'}
ALIASES={
 'employee_code':['کد پرسنلی','شماره پرسنلی','employee code','employee_code'],
 'name':['نام و نام خانوادگی','نام کامل','full name','name'],
 'first_name':['نام','نام شخص','first name','first_name'],
 'last_name':['نام خانوادگی','last name','last_name'],
 'email':['email','ایمیل','پست الکترونیک','پست الکترونیکی','آدرس ایمیل'],
 'management':['مدیریت','نام مدیریت','management'],
 'department':['اداره','نام اداره','department'],
 'position':['جایگاه','جایگاه سازمانی','سمت','شرح پست','position'],
 'level':['سطح','سطح گزارش','level'],
 'cluster_id':['شناسه کلاستر','cluster_id'],
 'active':['فعال','active']}
def suggest(columns):
    cols={header_normal(c).lower():c for c in columns};out={}
    for field,aliases in ALIASES.items():
        hit=next((cols[header_normal(a).lower()] for a in aliases if header_normal(a).lower() in cols),None)
        if hit:out[field]=hit
    return out

def level(value,default='expert'):
    v=header_normal(value).lower()
    exact={'expert':'expert','کارشناس':'expert','کارشناس ارشد':'expert',
           'manager':'manager','مدیر':'manager','مدیر میانی':'manager','رئیس':'manager','سرپرست':'manager',
           'executive':'executive','مدیر ارشد':'executive','معاون':'executive','مدیرعامل':'executive'}
    if not v:return default
    return exact.get(v,default)

def required_mapping(kind,mapping):
    if kind!='contacts':return True
    return ('employee_code' in mapping and 'email' in mapping and
            ('name' in mapping or ('first_name' in mapping and 'last_name' in mapping)))

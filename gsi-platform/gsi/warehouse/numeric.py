import math
from decimal import Decimal,InvalidOperation
DIGITS=str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')
def decimal_text(value):
    if value is None:return None
    s=str(value).strip().translate(DIGITS).replace('\u200e','').replace('\u200f','').replace('\u00a0','').replace('٬',',').replace('٫','.')
    if s.lower() in ('','nan','none','<na>','-'):return None
    negative=s.startswith('(') and s.endswith(')')
    if negative:s=s[1:-1]
    if ',' in s:
        import re
        if not re.fullmatch(r'[+-]?\d{1,3}(,\d{3})+(\.\d+)?',s):return None
        s=s.replace(',','')
    try:
        n=Decimal(s)
        if not n.is_finite():return None
        return format(-n if negative else n,'f')
    except InvalidOperation:return None

def number(value):
    val=decimal_text(value)
    return float(val) if val is not None else float('nan')

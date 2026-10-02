"""Strict numeric parsing for warehouse facts (Unknown stays Unknown).

Thin compatibility layer over :mod:`gsi.core.numeric_parse`; see that module for the
accepted notations.  ``decimal_text`` returns an exact plain-decimal string or
``None``; ``number`` returns ``float`` or ``nan`` — never ``0.0`` for Unknown.
"""
from ..core.numeric_parse import parse_decimal

DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def decimal_text(value):
    n = parse_decimal(value, strict=True)
    return format(n, 'f') if n is not None else None


def number(value):
    val = decimal_text(value)
    return float(val) if val is not None else float('nan')

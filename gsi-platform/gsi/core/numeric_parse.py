# -*- coding: utf-8 -*-
"""Canonical numeric parsing for source evidence.

GSI had three independent number parsers (``core.text.num_safe``,
``warehouse.numeric.number`` and ``cashflow.engine.number``).  Each one handled a
different subset of what real Iranian ERP/Excel exports contain, and two of
them silently produced wrong magnitudes:

* ``num_safe(1e-05)`` returned ``105.0`` and ``num_safe(1.5e16)`` returned
  ``1.516`` because ``str(float)`` switches to scientific notation and the
  exponent marker was stripped as "noise";
* ``num_safe("1٫5")`` returned ``15.0`` because the Persian decimal separator
  (U+066B) was deleted instead of being read as a decimal point;
* SAP trailing-minus amounts (``"1,234.56-"``) and the Unicode minus sign
  (U+2212) were read as positive numbers.

This module is the single implementation.  It never guesses: ``strict=True``
(the default) accepts only unambiguous notations and returns ``None`` for
anything else, so callers keep *Unknown* distinct from *Zero*.  ``strict=False``
additionally accepts the legacy heuristics that ``num_safe`` has always
accepted (``1.234.567``, ``12,34``), so its public contract does not change for
values that were already parsed correctly.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

__contract__ = 1

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

#: Invisible characters that Excel/web copy-paste leaves inside cells.  They are
#: formatting, never part of a number or identifier.
INVISIBLE = ("​", "‌", "‍", "‎", "‏", "‪", "‫",
             "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩",
             "﻿", "ـ")
_INVISIBLE_RE = re.compile("[" + "".join(INVISIBLE) + "]")

#: Characters used as digit-group separators that are *spaces*.
_SPACE_GROUP = (" ", " ", " ", " ", " ")
_MINUS = ("-", "−", "‒", "–", "—", "﹣", "－")
_EMPTY = {"", "nan", "none", "nat", "null", "<na>", "-", "--", "n/a", "na", "#n/a"}

_PLAIN = re.compile(r"\d+(?:\.\d+)?|\.\d+")
_SCI = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)[eE][+-]?\d+")
_COMMA_GROUPED = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_SPACE_GROUPED = re.compile(r"\d{1,3}(?: \d{3})+(?:\.\d+)?")


def strip_invisible(value: str) -> str:
    """Remove bidi/zero-width/tatweel marks (never meaningful in data)."""
    return _INVISIBLE_RE.sub("", value)


def _native(value: Any) -> Optional[Decimal]:
    """Fast path for values that already are numbers (not text)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, int):
        return Decimal(value)
    try:
        import numpy as np  # local: keep module import cheap
        if isinstance(value, np.bool_):
            return None
        if isinstance(value, np.integer):
            return Decimal(int(value))
        if isinstance(value, np.floating):
            value = float(value)
    except Exception:  # pragma: no cover - numpy is a hard dependency
        pass
    if isinstance(value, float):
        # repr() is the shortest round-trip form; Decimal reads 1e-05 exactly.
        return Decimal(repr(value)) if math.isfinite(value) else None
    return None


def _lenient(body: str) -> Optional[str]:
    """Legacy ``num_safe`` heuristics for separators that are ambiguous."""
    s = re.sub(r"[^\d.,]", "", body)
    if not s or s in (".", ","):
        return None
    if "," in s and "." in s:
        # the right-most separator is the decimal point
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif s.count(",") >= 1:
        parts = s.split(",")
        s = "".join(parts[:-1]) + ("." + parts[-1] if len(parts[-1]) < 3 else parts[-1])
    return s if _PLAIN.fullmatch(s) else None


def parse_decimal(value: Any, *, strict: bool = True) -> Optional[Decimal]:
    """Parse *value* into a finite ``Decimal`` or return ``None`` (Unknown).

    Accepted everywhere: native numbers, Persian/Arabic digits, the Persian
    decimal (``٫``) and group (``٬``) separators, comma/space digit grouping in
    groups of three, scientific notation, a leading ``+``/minus sign (ASCII or
    Unicode), a trailing minus sign (SAP) and accounting parentheses.

    ``strict=False`` additionally accepts the historical ``num_safe``
    heuristics (``1.234.567``, ``12,34``, currency text around the number).
    """
    if value is None:
        return None
    native = _native(value)
    if native is not None:
        return native
    if isinstance(value, (bool, float, int)):
        return None
    try:
        if value != value:  # NaN / NaT / pd.NA-like
            return None
    except Exception:
        pass
    s = strip_invisible(str(value)).translate(_DIGITS).strip()
    if s.lower() in _EMPTY:
        return None
    s = s.replace("٫", ".").replace("٬", ",").replace("،", ",")
    for ch in _SPACE_GROUP[:-1]:
        s = s.replace(ch, " ")
    s = s.strip()

    negative = False
    if len(s) > 2 and s[0] == "(" and s[-1] == ")":
        negative, s = True, s[1:-1].strip()
    if s[:1] == "+":
        s = s[1:].strip()
    elif s[:1] in _MINUS:
        negative, s = not negative, s[1:].strip()
    elif s[-1:] in _MINUS and len(s) > 1:
        negative, s = not negative, s[:-1].strip()
    if not s:
        return None

    text: Optional[str]
    if _PLAIN.fullmatch(s) or _SCI.fullmatch(s):
        text = s
    elif _COMMA_GROUPED.fullmatch(s):
        text = s.replace(",", "")
    elif _SPACE_GROUPED.fullmatch(s):
        text = s.replace(" ", "")
    elif not strict:
        text = _lenient(s)
    else:
        text = None
    if text is None:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    return -number if negative else number


def parse_float(value: Any, *, strict: bool = True) -> float:
    """``parse_decimal`` as ``float``; Unknown is ``nan`` (never ``0.0``)."""
    number = parse_decimal(value, strict=strict)
    return float(number) if number is not None else float("nan")


__all__ = ["INVISIBLE", "parse_decimal", "parse_float", "strip_invisible"]

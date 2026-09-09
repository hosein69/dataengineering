# -*- coding: utf-8 -*-
"""تحلیل سبک و قابل استناد روی داده موجود.

سه ماژول: ``evidence`` (نرخ و بازه اطمینان)، ``drivers`` (پیامد و محرک،
با کنترل مخدوش‌کننده)، ``cycle`` (زمان کجا می‌رود).
"""
from __future__ import annotations

__contract__ = 1

__all__ = ["evidence", "drivers", "cycle", "report"]

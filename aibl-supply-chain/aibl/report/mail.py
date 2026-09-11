# -*- coding: utf-8 -*-
"""تمِ ایمیل — همان البرز، ترجمه‌شده به زبانی که موتور Word می‌فهمد.

## چرا این فایل جدا است

بدنهٔ ایمیل با بقیهٔ خروجی‌ها یک فرق بنیادی دارد: اتلوکِ کلاسیک آن را
با موتورِ **Word** رندر می‌کند. یعنی نه ``flex``، نه ``grid``، نه
``background-clip:text``، نه گرادیانِ CSS، نه ``mix-blend-mode``، و نه
حتی ``data:`` روی تصویر. هرچه از نظام طراحی در ایمیل می‌آید باید از این
صافی رد شود.

پیش از این، ایمیل پالتِ نسلِ قبل را داشت: زمینهٔ نعنایی ``#E1F2E9``،
سربرگِ ``#005349`` و عنوانِ طلاییِ ``#F5D3A3``. یعنی گیرنده یک جنس
می‌دید و در گزارش جنسی دیگر. این ماژول همان توکن‌های البرز را می‌دهد،
فقط با نام‌هایی که ایمیل لازم دارد.

## سه لایهٔ نشست

۱. ``bgcolor`` — تخت، همیشه کار می‌کند، حتی وقتی کل CSS نادیده گرفته شود.
۲. VML — برای اتلوک: طیفِ سربرگ به‌صورت ``<v:rect>`` با ``fill``.
۳. CSS — برای بقیه: همان طیفِ چهارتوقفیِ قالب.

هر لایه بدونِ لایه‌های بعدی هم درست دیده می‌شود. این «بهسازی تدریجی»
است، نه سه نسخهٔ موازی.

## چه چیزی عمداً نمی‌آید

* **نشان و خودرو.** تصویرِ ``data:`` را اتلوک و جی‌میل حذف می‌کنند و
  بیشتر کلاینت‌ها تصویر را پیش‌فرض نمی‌کشند. یک قابِ خالی بدتر از
  نبودنش است. سربرگِ ایمیل با تایپوگرافی ساخته می‌شود، نه با تصویر.
* **حکِ عنوان.** ``background-clip:text`` روی Word کار نمی‌کند و متن را
  نامرئی می‌کند. عنوان سفیدِ ضخیم می‌ماند — روی تیره‌ترین توقفِ طیف
  کنتراستش ۱۵٫۰۳:۱ است.
"""
from __future__ import annotations

import html as _h
from typing import Dict

from . import alborz as _AL

#: پالت ایمیل — هر کلید از البرز می‌آید، هیچ رنگی اینجا تعریف نمی‌شود.
#:
#: کنتراست‌ها اندازه‌گیری شده‌اند، نه ادعا (روی ``surface``/``raised``):
#:
#:     متن روی کارت                    ۱۴٫۴۲:۱
#:     متن ثانویه روی کارت              ۵٫۷۲:۱
#:     متن سوم روی زمینه                ۴٫۶۸:۱
#:     سفید روی سربرگ                  ۱۳٫۳۹:۱
#:     سفید روی روشن‌ترین توقفِ طیف       ۷٫۶۸:۱
#:     متن ثانویه روی روشن‌ترین توقف     ۵٫۹۸:۱
#:     سفید روی دکمه                    ۶٫۰۹:۱
PALETTE: Dict[str, str] = {
    "surface": _AL.PAGE,
    "raised": _AL.CARD,
    "band": _AL.BAND,
    "border-soft": _AL.HAIRLINE,
    "border": _AL.RULE,
    "text": _AL.INK,
    "text-2": _AL.INK_2,
    "text-3": _AL.INK_3,
    "header": _AL.HEADER_MID,
    "header-deep": _AL.HEADER_DEEP,
    "header-edge": _AL.HEADER_EDGE,
    "on-header": _AL.ON_TEAL,
    "on-header-2": _AL.ON_TEAL_2,
    "on-header-title": _AL.TITLE_TOP,
    "rule": _AL.DUST,
    "accent": _AL.GOLD,
    "cta": _AL.TEAL_INK,
    "on-cta": _AL.ON_TEAL,
    "brand": _AL.TEAL,
    "on-brand": _AL.ON_TEAL,
    "highlight": _AL.BLIND_BG,
    "chip": _AL.PILL,
    #: نوارِ فرورفته — پسِ‌زمینهٔ بخش‌های جداکننده در ایمیل.
    "sunken": _AL.BAND_ALT,
}

#: فونت ایمیل. ایران‌سنس روی دستگاهِ گیرنده معمولاً نیست و ایمیل هم
#: ``@font-face`` را نمی‌آورد؛ پس زنجیره‌ای می‌دهیم که همه‌جا هست.
FONT = "Tahoma,'Segoe UI',Arial,sans-serif"


def _stops_css() -> str:
    body = ", ".join(f"{c} {int(p * 100)}%" for p, c in _AL.HEADER_STOPS)
    return f"linear-gradient(135deg, {body})"


def header_band(title: str, sub: str = "", kicker: str = "",
                width: int = 820) -> str:
    """نوارِ سربرگِ ایمیل — همان ترتیبِ قالب، با ابزارِ ایمیل.

    ترتیب عوض نمی‌شود: سرسطرِ سازمان (با فاصلهٔ حروف)، خطِ نازک، عنوان،
    زیرعنوان. همان چیزی که در پوستر و گزارش می‌بینند.
    """
    P = PALETTE
    kick = ""
    if kicker:
        kick = (f'<div style="font-family:{FONT};font-size:10px;'
                f'letter-spacing:2px;color:{P["on-header-2"]};'
                f'mso-line-height-rule:exactly;line-height:14px;'
                f'padding-bottom:10px">{_h.escape(kicker)}</div>')
    rule = (f'<table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0"><tr>'
            f'<td height="1" bgcolor="{P["rule"]}" '
            f'style="height:1px;line-height:1px;font-size:0">&nbsp;</td>'
            f"</tr></table>")
    subline = ""
    if sub:
        subline = (f'<div style="font-family:{FONT};font-size:12px;'
                   f'color:{P["on-header-2"]};padding-top:6px;'
                   f'mso-line-height-rule:exactly;line-height:18px">'
                   f"{_h.escape(sub)}</div>")
    inner = (f'{kick}{rule}'
             f'<div style="font-family:{FONT};font-size:22px;font-weight:bold;'
             f'color:{P["on-header"]};padding-top:14px;'
             f'mso-line-height-rule:exactly;line-height:30px">'
             f'{_h.escape(title)}</div>{subline}')
    # VML برای اتلوک، CSS برای بقیه، bgcolor برای وقتی هیچ‌کدام نبود.
    return f"""
<tr><td bgcolor="{PALETTE['header']}" class="pad hero"
    style="padding:0;border-radius:12px 12px 0 0;background:{PALETTE['header']};
    background-image:{_stops_css()}">
<!--[if gte mso 9]>
<v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false"
        style="width:{width}px;height:150px">
<v:fill type="gradient" angle="135"
        color="{PALETTE['header-deep']}" color2="{PALETTE['header-edge']}"/>
<v:textbox inset="24px,20px,24px,20px"><![endif]-->
<div class="pad" style="padding:20px 24px">{inner}</div>
<!--[if gte mso 9]></v:textbox></v:rect><![endif]-->
</td></tr>"""

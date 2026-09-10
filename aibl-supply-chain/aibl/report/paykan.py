# -*- coding: utf-8 -*-
"""پیکان — نقش‌مایهٔ برداریِ «البرز».

نسخهٔ یکسانِ پکیج دیگر. عمداً کپی شده، مثل ``alborz.py``.

## چرا این فایل هست

سفارش‌دهنده گفت «از پیکان استفاده کن، **بدون نوشته‌هایش**». پس اینجا
هیچ آرم، هیچ نشان و هیچ حروفی نیست: فقط سیلوئتِ نمای جانبی، رسم‌شده از
روی تناسب‌های واقعیِ خودرو، نه از روی حافظه:

    قطر چرخ ۶۳۰ · فاصلهٔ محور ۲۵۰۰ · طول ۴۳۰۰ · ارتفاع ۱۴۲۰ (میلی‌متر)

همان نسبت‌ها در واحد نقشه ضرب شده‌اند؛ به همین دلیل کاپوت و صندوق
تقریباً هم‌اندازه‌اند و اتاق بین دو محور می‌نشیند. اگر این نسبت‌ها را
دستکاری کنید، شکل به «یک خودروی جعبه‌ای» تنزل می‌کند و دیگر پیکان
نیست.

## چرا SVG، نه تصویر

تصویر در اندازهٔ پوستر می‌شکند و رنگش با پالت جابه‌جا نمی‌شود. این
تابع رنگ‌ها را از ``alborz`` می‌گیرد، پس اگر پالت عوض شود، خودرو هم
عوض می‌شود — بدون اینکه کسی فایلی را دوباره صادر کند.
"""
from __future__ import annotations

from typing import Optional

from . import alborz as _AL

#: نسبت ابعاد نقشهٔ پایه. هر مصرف‌کننده عرض می‌دهد، ارتفاع از این می‌آید.
VIEW_W = 440
VIEW_H = 236
ASPECT = VIEW_H / VIEW_W

#: کادرِ چسبیده به خودِ خودرو. نقشهٔ پایه بالای سقف هوا دارد (جا برای
#: سایه و تنفس)؛ در سربرگ همان هوا به فاصلهٔ مردهٔ ۹۰ پیکسلی تبدیل می‌شد.
CROP = (0, 84, VIEW_W, 148)
CROP_ASPECT = CROP[3] / CROP[2]

#: مسیر بستهٔ بدنه — یک شکل بسته. قوس گلگیرها با منحنی درجه‌سه‌اند تا
#: تاج قوس صاف بنشیند؛ با منحنی درجه‌دو نوکِ تیز می‌داد و قوس چرخ به
#: «V» تبدیل می‌شد.
BODY = ("M 22 126 L 146 122 L 168 84 L 268 84 L 292 122 L 400 126 L 408 137 "
        "L 408 184 L 344 194 C 344 133 284 133 284 194 L 128 194 "
        "C 128 133 58 133 58 194 L 24 186 Z")


def svg(width: int = 440, *, body: Optional[str] = None,
        glass: Optional[str] = None, shade: Optional[str] = None,
        chrome: Optional[str] = None, tyre: Optional[str] = None,
        ground: bool = True, crop: bool = False, inline: bool = False,
        uid: str = "pk") -> str:
    """پیکان، به‌صورت ``<svg>`` مستقل و آمادهٔ درج در HTML.

    ``uid`` باید در هر صفحه یکتا باشد: ``clipPath`` و ``defs`` با
    شناسه کار می‌کنند و دو پیکان با یک شناسه، همدیگر را خراب می‌کنند.

    ``inline=True`` صفت ``xmlns`` را برنمی‌دارد. داخل HTML لازم نیست —
    تجزیه‌گر خودش ``<svg>`` را در فضای‌نام SVG می‌گذارد — و بودنش یک
    نشانی ``http://`` وارد سند می‌کند که تستِ «بدون وابستگی بیرونی» را
    می‌ترساند، بی‌آنکه واقعاً چیزی از شبکه گرفته شود.
    """
    body = body or _AL.TEAL
    glass = glass or _AL.ON_TEAL_2
    shade = shade or _AL.TEAL_EDGE
    chrome = chrome or _AL.MIST
    tyre = tyre or _AL.TEAL_DEEP
    box = CROP if crop else (0, 0, VIEW_W, VIEW_H)
    h = round(width * (CROP_ASPECT if crop else ASPECT))
    vb = " ".join(str(v) for v in box)
    g = f'<ellipse cx="215" cy="213" rx="196" ry="7" fill="{chrome}" opacity=".45"/>' if ground else ""
    ns = "" if inline else ' xmlns="http://www.w3.org/2000/svg"'
    return f'''<svg{ns} viewBox="{vb}" \
width="{width}" height="{h}" role="img" aria-label="پیکان">
<defs><path id="{uid}-b" d="{BODY}"/>
<clipPath id="{uid}-c"><use href="#{uid}-b"/></clipPath></defs>
<g transform="translate(8,8)">{g}
<use href="#{uid}-b" fill="{body}"/>
<rect x="0" y="172" width="440" height="40" fill="{shade}" opacity=".45" clip-path="url(#{uid}-c)"/>
<path fill="{shade}" d="M 168 84 L 268 84 L 270 90 L 171 90 Z"/>
<path fill="{glass}" d="M 177 91 L 224 90 L 224 118 L 156 118 Z"/>
<path fill="{glass}" d="M 232 90 L 267 90 L 283 118 L 232 118 Z"/>
<path fill="{_AL.TEAL_MID}" d="M 156 118 L 177 91 L 185 91 L 170 118 Z"/>
<path stroke="{glass}" stroke-width="2.2" fill="none" opacity=".9" d="M 146 124 L 398 128"/>
<path stroke="{_AL.TEAL_MID}" stroke-width="1.5" fill="none" opacity=".8" \
d="M 152 125 L 152 182 M 228 124 L 228 188 M 292 126 L 292 182"/>
<rect x="186" y="134" width="16" height="4" rx="2" fill="{glass}"/>
<rect x="248" y="135" width="16" height="4" rx="2" fill="{glass}"/>
<path fill="{tyre}" d="M 23 131 L 52 130 L 52 152 L 23 153 Z"/>
<circle cx="33" cy="141" r="6.5" fill="{glass}"/>
<rect x="393" y="132" width="14" height="12" rx="2" fill="{glass}"/>
<rect x="17" y="159" width="52" height="8" rx="4" fill="{chrome}"/>
<rect x="356" y="159" width="52" height="8" rx="4" fill="{chrome}"/>
<g><circle cx="93" cy="184" r="28" fill="{tyre}"/><circle cx="93" cy="184" r="14.5" fill="{chrome}"/>\
<circle cx="93" cy="184" r="5" fill="{glass}"/></g>
<g><circle cx="314" cy="184" r="28" fill="{tyre}"/><circle cx="314" cy="184" r="14.5" fill="{chrome}"/>\
<circle cx="314" cy="184" r="5" fill="{glass}"/></g>
</g></svg>'''


def mark(width: int = 96, color: Optional[str] = None) -> str:
    """سیلوئتِ تک‌رنگ — برای سربرگ، پاصفحه و گوشهٔ گزارش.

    اینجا عمداً هیچ جزئیاتی نیست: در عرض کمتر از صد پیکسل، شیشه و
    دستگیره به لکه تبدیل می‌شوند و شکل را کثیف می‌کنند.

    همیشه درون‌خطی است، پس ``xmlns`` ندارد.
    """
    color = color or _AL.TEAL_INK
    h = round(width * ASPECT)
    return (f'<svg viewBox="0 0 {VIEW_W} {VIEW_H}" '
            f'width="{width}" height="{h}" role="img" aria-label="پیکان">'
            f'<g transform="translate(8,8)"><path fill="{color}" d="{BODY}"/>'
            f'<circle cx="93" cy="184" r="26" fill="{color}"/>'
            f'<circle cx="314" cy="184" r="26" fill="{color}"/></g></svg>')


def data_uri(width: int = 440, **kw) -> str:
    """همان SVG، به‌صورت ``data:`` — برای جایی که فقط ``src`` می‌پذیرد."""
    import base64
    kw.pop("inline", None)   # پروندهٔ مستقل، حتماً فضای‌نام لازم دارد
    raw = svg(width, **kw).encode("utf-8")
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")

# -*- coding: utf-8 -*-
"""R10: سربرگ برند GSI با پالت موشن‌گرافیک در گزارش‌های HTML، ایمیل و Studio (داده ساختگی)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from gsi.design import brand, tokens as T
from gsi.design import components as C


def test_band_css_survives_streamlit_sanitiser_and_uses_motion_palette():
    css = brand.band_css()
    assert "<" not in css                     # DOMPurify در Streamlit استایل دارای «<» را حذف می‌کند
    for c in (T.BAND_DEEP, T.BAND_DARK, T.BAND_MINT, T.BAND_GOLD):
        assert c in css or c.lower() in css.lower() or c in brand.texture_uri()
    assert brand.MARK_PATH.exists() and brand.mark_data_uri().startswith("data:image/png;base64,")


def test_report_header_is_the_brand_band_with_title_and_status_stats():
    html = C.app_bar("عنوان آزمایشی <b>", eyebrow="GSI · X", subtitle="زیرعنوان",
                     stats=[("توقف خط", "3"), ("بحرانی", "5")])
    assert 'class="gsi-band"' in html and brand.wordmark_html() in html and "Global Sourcing" in html
    assert "عنوان آزمایشی &lt;b&gt;" in html and "GSI · X" not in html
    assert 'data-tone="stockout"' in html and 'data-tone="critical"' in html
    assert ".gsi-band" in __import__("gsi.design.css", fromlist=["stylesheet"]).stylesheet()


def test_email_header_is_an_inline_image_with_live_title():
    rows = brand.email_header_html("عنوان ایمیل", "زیرعنوان")
    assert f"cid:{brand.EMAIL_HEADER_CID}" in rows and "عنوان ایمیل" in rows and T.BAND_DEEP in rows
    assert brand.EMAIL_HEADER_PATH.exists() and brand.EMAIL_HEADER_PATH.stat().st_size > 1000

    class Acc:
        props = {}
        def SetProperty(self, k, v):
            self.props[k] = v

    class Att:
        PropertyAccessor = Acc()

    class Atts:
        added = []
        def Add(self, *a):
            self.added.append(a)
            return Att()

    class Mail:
        Attachments = Atts()

    assert brand.attach_email_header(Mail())
    assert Att.PropertyAccessor.props["http://schemas.microsoft.com/mapi/proptag/0x3712001F"] == brand.EMAIL_HEADER_CID
    assert brand.attach_email_header(object()) is False   # پیام بدون پیوست (آزمون یا جایگزین) نمی‌شکند


def test_daily_email_and_case_action_use_the_brand_header(tmp_path):
    from gsi.integrations.daily_email import build_case_action_html, build_email_html
    df = pd.DataFrame({"KEY_ORDER": ["O1"], "KEY_MATERIAL": ["M1"]})
    body = build_email_html(date(2026, 8, 31), df, [], Path(tmp_path) / "r.xlsx")
    assert f"cid:{brand.EMAIL_HEADER_CID}" in body and 'cellspacing="0"' in body
    assert f"cid:{brand.EMAIL_HEADER_CID}" in build_case_action_html({"KEY_REG": "R1"})


def test_art_page_is_three_to_one_by_default():
    page = brand.art_html()
    assert "width:1536px;height:512px" in page and brand.wordmark_html() in page and brand.TAGLINE_FA in page


def test_wordmark_is_gsi_with_small_i_and_faint_barcode_tail():
    """مالک: «GSi» (i کوچک و ریزتر) و ادامه Intelligence خیلی کم‌رنگ و بارکدی، همه‌جا."""
    wm = brand.wordmark_html()
    assert ">GS</b>" in wm and ">i</b>" in wm and ">ntelligence<" in wm and "GSI" not in wm
    css = brand.wordmark_css(".gw", 30)
    assert "<" not in css and ".gw-i{" in css and "font-size:.8em" in css
    assert "repeating-linear-gradient(90deg" in css and "rgba(167,224,212,.16)" in css
    assert brand.wordmark_html() in brand.band_raw("t")
    foot = brand.email_footer_html()
    assert ">GS</span>" in foot and ">ntelligence<" in foot

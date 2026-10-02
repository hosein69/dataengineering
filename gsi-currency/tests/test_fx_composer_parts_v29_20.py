# -*- coding: utf-8 -*-
"""29.20 — هر بخش چرخه ارز یک Block جدای گزارش‌ساز HTML است.

مالک پروژه خواست المان‌های گزارش HTML را آزادانه اضافه، حذف و جابه‌جا کند. تا این نسخه
«چرخه ارز و گزارش مالی» یک Block یکجا بود و بارنامه ↔ ثبت سفارش، صف تخصیص، ترخیص و
اقلام بحرانی فقط در گزارش مستقل با چیدمان ثابت بودند. هر آزمون یکی از این قول‌ها را قفل می‌کند:
  * هر بخش گزارش مستقل یک Block جدا در فهرست گزارش‌ساز Studio است و Block یکجا برای
    چیدمان‌های ذخیره‌شده می‌ماند؛
  * هر Block فقط بخش خودش را دارد، به ترتیب Composer می‌آید، حذفش بقیه را جابه‌جا نمی‌کند
    و اندازه‌اش به شبکه HTML می‌رسد؛
  * ویرایشگر چیدمان داخل HTML ارسالی هم هر بخش را جدا جابه‌جا، پنهان و اندازه‌بندی می‌کند
    و نامش را درست نشان می‌دهد؛
  * مدل چرخه ارز یک بار برای کل گزارش ساخته می‌شود و دو تب، مسیر مراحل مشترک ندارند.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from gsi.i18n import columns as C
from gsi.report import fx_html as H
from gsi.report import fx_insight as X
from gsi.studio_core import composer
from gsi.studio_core.html_export import build_dynamic_html
from test_fx_insight_html_excel_v29_18 import PERSIAN, REF, _build

ROOT = Path(__file__).resolve().parents[1]

# نشانه محتوای هر Block: متنی که فقط همان بخش دارد
SIGNATURE = {
    "fx_kpi": "ثبت سفارش در جریان",
    "fx_stages": "فقط ثبت سفارش‌های دارای متریال بحرانی",     # مسیر اقلام بحرانی این صافی را ندارد
    "fx_money": "ریز جریان پول هر ثبت سفارش",
    "fx_bl_link": "هر بارنامه با ارزش فاکتور و ارز خودش به ثبت سفارشش وصل است",
    "fx_queue": "مرتب‌سازی: اول بحرانی‌ترین متریال سفارش",
    "fx_clearance": "بیشترین رسوب (روز)",
    "fx_critical": "تابلوی متریال‌ها و بارنامه‌های بحرانی",
    "fx_downloads": f'download="GSI_FX_STAGES_{REF}.xlsx"',
}


@pytest.fixture(scope="module")
def built():
    return _build()


def _page(built, blocks, sizes=None, tabs=None):
    out, extras = built
    tabs = tabs or [{"id": "fx", "title": "چرخه ارز", "blocks": blocks, "block_sizes": sizes or {}}]
    return build_dynamic_html(out, REF, tabs=tabs, process_extras=extras)


class _Blocks(HTMLParser):
    """هر Block گزارش‌ساز: عنصر پدرش، نشانه‌گذاری‌اش و نخستین عنوانش (همان که ویرایشگر چیدمان نام می‌برد)."""

    VOID = {"input", "br", "img", "meta", "link", "hr", "col", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.blocks, self._open = [], {}, []

    def _emit(self, text):
        for name, _ in self._open:
            self.blocks[name]["html"].append(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section" and "data-composer-block" in a:
            name = a["data-composer-block"]
            parent = self.stack[-1][1] if self.stack else {}
            self.blocks[name] = {"parent": parent, "size": a.get("data-gsi-size"), "html": [], "heading": None}
            self._open.append((name, len(self.stack)))
        self._emit(self.get_starttag_text())
        if tag not in self.VOID:
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        self._emit(f"</{tag}>")
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break
        self._open = [(n, d) for n, d in self._open if d < len(self.stack)]

    def handle_data(self, data):
        self._emit(data)
        for name, _ in self._open:
            b = self.blocks[name]
            if b["heading"] is None and self.stack and self.stack[-1][0] in ("h2", "h3", "h4") and data.strip():
                b["heading"] = data.strip()


def _blocks(page):
    p = _Blocks()
    p.feed(page)
    return {k: dict(v, text="".join(v["html"])) for k, v in p.blocks.items()}


# ═══════════════════════════ فهرست Blockها ═══════════════════════════
def test_every_fx_section_is_its_own_composer_block_and_the_combined_block_stays():
    assert set(composer.FX_BLOCKS) == set(H.PARTS)
    assert all(k in composer.BLOCKS for k in composer.FX_BLOCKS)
    assert "fx_lifecycle" in composer.BLOCKS                 # چیدمان‌های ذخیره‌شده
    assert composer.normalize_blocks(["fx_lifecycle", "fx_queue"]) == ["fx_lifecycle", "fx_queue"]
    for persona, blocks in composer.DEFAULT_BLOCKS.items():
        # تب تازه همان محتوای Block یکجا را دارد، ولی هر بخش جدا جابه‌جا و حذف می‌شود
        assert "fx_lifecycle" not in blocks, persona
        i = blocks.index("fx_kpi")
        assert blocks[i:i + len(composer.FX_LIFECYCLE_PARTS)] == composer.FX_LIFECYCLE_PARTS, persona


def test_studio_composer_lists_every_block_from_the_catalog():
    src = (ROOT / "app" / "studio.py").read_text(encoding="utf-8")
    # فهرست، کشیدن و اندازه همه از BLOCKS خوانده می‌شوند؛ Block تازه بی‌کار اضافه در Studio هست
    assert '"Blockهای این تب", list(BLOCKS)' in src
    assert '{"id": k, "label": BLOCKS[block_type(k)], "badge": "Block"}' in src
    assert 'f"{BLOCKS[block_type(bk)]}", list(SIZES)' in src


# ═══════════════════════════ HTML ارسالی ═══════════════════════════
def test_each_block_renders_only_its_own_section(built):
    page = _page(built, list(composer.FX_BLOCKS))
    blocks = _blocks(page)
    assert set(composer.FX_BLOCKS) <= set(blocks)
    assert "داده چرخه ارز برای این گزارش در دسترس نیست" not in page
    for name, sig in SIGNATURE.items():
        body = blocks[name]["text"]
        assert sig in body, name
        assert not [o for o, s in SIGNATURE.items() if o != name and s in body], name
    assert blocks["fx_stages"]["text"].count('<details class="gx-reg') == 4
    assert page.count(".gx-x{container-type:inline-size}") == 1   # CSS اجزا یک بار در صفحه


def test_blocks_follow_the_composer_order(built):
    order = ["fx_critical", "fx_queue", "fx_kpi", "fx_bl_link"]
    for blocks in (order, list(reversed(order))):
        page = _page(built, blocks)
        pos = [page.index(f'data-composer-block="{b}"') for b in blocks]
        assert pos == sorted(pos), blocks


def test_removing_a_block_removes_only_that_section(built):
    page = _page(built, ["fx_queue", "fx_clearance"])
    assert 'data-composer-block="fx_queue"' in page and 'data-composer-block="fx_clearance"' in page
    for gone in set(composer.FX_BLOCKS) - {"fx_queue", "fx_clearance"}:
        assert f'data-composer-block="{gone}"' not in page, gone
    assert "ثبت سفارش در جریان" not in page and "ریز جریان پول هر ثبت سفارش" not in page


def test_block_sizes_reach_the_html_grid(built):
    sizes = {"fx_kpi": "full", "fx_queue": "half", "fx_clearance": "half", "fx_downloads": "quarter"}
    blocks = _blocks(_page(built, list(sizes), sizes))
    assert {k: blocks[k]["size"] for k in sizes} == sizes


def test_layout_editor_in_the_sent_html_sees_each_fx_block(built):
    blocks = _blocks(_page(built, list(composer.FX_BLOCKS)))
    for name, (_, title) in H.PARTS.items():
        # ویرایشگر فقط فرزندان مستقیم .pane را جابه‌جا/پنهان می‌کند و نام را از نخستین عنوان می‌خواند
        assert "pane" in (blocks[name]["parent"].get("class") or "").split(), name   # فرزند مستقیم
        assert blocks[name]["heading"] == title, name


def test_one_fx_model_per_report_and_separate_stage_rails_per_tab(built, monkeypatch):
    calls = []
    real = X.load

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(X, "load", counting)
    tabs = [{"id": "a", "title": "الف", "blocks": ["fx_kpi", "fx_stages", "fx_queue"]},
            {"id": "b", "title": "ب", "blocks": ["fx_stages", "fx_critical", "fx_money"]}]
    page = _page(built, None, tabs=tabs)
    assert len(calls) == 1
    groups = set(re.findall(r'<input type="radio" class="gx-r gx-r\d+" name="(g[0-9a-f]+)"', page))
    assert len(groups) == 3          # مراحل تب الف، مراحل تب ب، مسیر اقلام بحرانی تب ب


# ═══════════════════════════ خود Blockها ═══════════════════════════
def test_part_without_fx_data_shows_an_empty_state_with_its_title():
    empty = X.load(None, {}, REF)
    for name, (_, title) in H.PARTS.items():
        part = H.composer_part(name, None, fx=empty)
        assert title in part and "جدول چرخه ارز در Snapshot نیست" in part, name
    with pytest.raises(KeyError):
        H.composer_part("fx_unknown", None, fx=empty)


def test_download_block_does_not_embed_workbooks_for_a_large_report(built):
    out, extras = built
    small = H.composer_part("fx_downloads", out, extras, REF)
    assert small.count("data:application/vnd.openxmlformats") == 3
    big = H.composer_part("fx_downloads", out, extras, REF, max_embedded_regs=2)
    assert "data:application" not in big and "Studio" in big
    off = H.composer_part("fx_downloads", out, extras, REF, embed_excel=False)
    assert "data:application" not in off and "جاسازی Excel خاموش است" in off


def test_english_parts_translate_program_text(built):
    out, extras = built
    fx = X.load(out, extras, REF)
    for name in H.PARTS:
        part = H.composer_part(name, out, extras, REF, lang=C.EN, fx=fx, embed_excel=False)
        body = re.sub(r"<style>.*?</style>", "", part, flags=re.S)
        left = {t.strip() for t in re.split(r"<[^>]+>", body) if PERSIAN.search(t)}
        assert left <= {f"شرح M{i}" for i in range(1, 6)}, (name, sorted(left))

# -*- coding: utf-8 -*-
"""29.21 — دکمه‌های دانلود نمای چرخه ارز روی Streamlit قدیمی‌تر از 1.52 هم کار کنند.

خطای واقعی کاربر (Streamlit 1.51 روی Python 3.13)::

    StreamlitAPIException: Invalid binary data format: <class 'functools.partial'>

از ``fx_lifecycle_view._dl``؛ صفحه «چرخه ارز» از همان دکمه اول می‌ایستاد، چون فقط
Streamlit 1.52 به بعد ``data`` را callable می‌پذیرد و ``requirements.txt`` از 1.49 را
مجاز می‌داند. هر آزمون یکی از این‌ها را قفل می‌کند:

  * روی نسخه قدیمی هرگز callable به ``download_button`` نرسد؛
  * فایل فقط با کلیک ساخته شود، نه در هر بازاجرای صفحه؛
  * با عوض شدن ورودی (مرحله، زبان، سطوح، Snapshot) فایل کهنه دانلود نشود؛
  * خود صفحه روی هر دو مسیر بدون خطا اجرا شود.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import streamlit as st

from app import lazy_download as LD

ROOT = Path(__file__).resolve().parents[1]
FX_KEYS = ("fxl_dl_stage", "fxl_dl_reg", "fxl_dl_html", "fxl_dl_one", "fxl_dl_money_all", "fxl_dl_crit",
           "fxl_dl_crit_html")
NATIVE = LD.version_tuple(st.__version__) >= LD.CALLABLE_SINCE


# ═══════════════════════════ ظرف ساختگی ═══════════════════════════
class _Box:
    """به‌جای ستون Streamlit: هر فراخوانی را ثبت می‌کند."""

    def __init__(self, log, clicks=()):
        self.log, self.clicks = log, set(clicks)

    def empty(self):
        return self

    def button(self, label, key=None, **kw):
        self.log.append(("button", label, key, kw))
        return key in self.clicks

    def download_button(self, label, data=None, **kw):
        self.log.append(("download", label, data, kw))
        return False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _St:
    def __init__(self):
        self.session_state = {}

    def spinner(self, _text):
        return _Box([])


@pytest.fixture
def old(monkeypatch):
    """Streamlit قدیمی: callable پذیرفته نمی‌شود."""
    fake = _St()
    monkeypatch.setattr(LD, "CALLABLE_DATA", False)
    monkeypatch.setattr(LD, "st", fake)
    return fake


def _maker(calls, payload=b"PK-xlsx"):
    def make():
        calls.append(1)
        return payload
    return make


# ═══════════════════════════ آزمون‌ها ═══════════════════════════
def test_version_gate_matches_the_first_streamlit_that_accepts_callables():
    assert LD.version_tuple("1.51.0") == (1, 51)          # نسخه کاربر
    assert LD.version_tuple("1.52.0.dev20251201") == (1, 52)
    assert LD.version_tuple("2.0") == (2, 0)
    assert LD.version_tuple("") == (0, 0)                  # نامعلوم ← مسیر امن دو قدمی
    assert LD.CALLABLE_SINCE == (1, 52)
    assert LD.CALLABLE_DATA == NATIVE


def test_new_streamlit_gets_the_callable_and_nothing_is_built_up_front(monkeypatch):
    monkeypatch.setattr(LD, "CALLABLE_DATA", True)
    log, calls = [], []
    LD.download(_Box(log), "Excel", _maker(calls), file_name="a.xlsx", mime="x", key="k")
    assert calls == []
    (kind, label, data, kw), = log
    assert kind == "download" and callable(data) and kw["key"] == "k"


def test_old_streamlit_builds_only_on_click_and_never_receives_a_callable(old):
    log, calls = [], []
    make = _maker(calls)
    LD.download(_Box(log), "Excel", make, file_name="a.xlsx", mime="x", key="k", sig=("fa",))
    assert calls == [] and [e[0] for e in log] == ["button"]          # فقط «آماده‌سازی»
    assert log[0][1] == "آماده‌سازی Excel" and log[0][2] == "k__build"

    log.clear()
    LD.download(_Box(log, clicks={"k__build"}), "Excel", make, file_name="a.xlsx", mime="x", key="k", sig=("fa",))
    assert calls == [1]
    kind, label, data, kw = log[-1]
    assert kind == "download" and data == b"PK-xlsx" and not callable(data)
    assert kw["on_click"] == "ignore" and kw["key"] == "k"

    log.clear()                                                      # بازاجرای بعدی: بی‌ساخت دوباره
    LD.download(_Box(log), "Excel", make, file_name="a.xlsx", mime="x", key="k", sig=("fa",))
    assert calls == [1] and [e[0] for e in log] == ["download"] and log[0][2] == b"PK-xlsx"


@pytest.mark.parametrize("change", [{"sig": ("en",)}, {"file_name": "b.xlsx"}])
def test_changed_inputs_never_serve_the_previously_built_file(old, change):
    calls = []
    args = dict(file_name="a.xlsx", mime="x", key="k", sig=("fa",))
    LD.download(_Box([], clicks={"k__build"}), "Excel", _maker(calls), **args)
    log = []
    LD.download(_Box(log), "Excel", _maker(calls), **dict(args, **change))
    assert [e[0] for e in log] == ["button"], "فایل ورودی قبلی نباید دانلود شود"
    assert calls == [1]


def test_fx_view_passes_no_callable_to_streamlit_directly():
    """همه دکمه‌های نمای چرخه ارز از ``lazy_download`` می‌گذرند."""
    tree = ast.parse((ROOT / "app/fx_lifecycle_view.py").read_text(encoding="utf-8"))
    direct = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "download_button"]
    assert direct == []


def test_no_download_button_in_the_app_is_handed_a_partial_or_lambda():
    """فقط ``app/lazy_download.py`` حق دارد callable به ``download_button`` بدهد."""
    bad = []
    for path in list((ROOT / "app").glob("*.py")) + list((ROOT / "gsi").rglob("*.py")):
        if path.name == "lazy_download.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "download_button"):
                continue
            data = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "data"), None)
            if isinstance(data, ast.Lambda) or (isinstance(data, ast.Call) and "partial" in ast.unparse(data.func)):
                bad.append(f"{path.relative_to(ROOT)}:{n.lineno}")
    assert bad == []


# ═══════════════════════ خود صفحه در AppTest ═══════════════════════
_PAGE = f"""
import importlib.util, sys
sys.path.insert(0, {str(ROOT)!r})
spec = importlib.util.spec_from_file_location("_fx_fixture_v29_21", {str(ROOT / "tests/test_fx_insight_html_excel_v29_18.py")!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
out, extras = mod._build()
from app import fx_lifecycle_view as V
V.run(out, extras, mod.REF)
"""


def _page():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_string(_PAGE, default_timeout=120)


def test_fx_page_on_old_streamlit_prepares_then_downloads(monkeypatch):
    monkeypatch.setattr(LD, "CALLABLE_DATA", False)
    app = _page().run()
    assert not app.exception, [e.message for e in app.exception]
    builds = {b.key for b in app.button}
    assert {k + "__build" for k in FX_KEYS} <= builds
    assert not [d for d in app.get("download_button") if d.proto.id.endswith("fxl_dl_stage")]

    app.button(key="fxl_dl_stage__build").click().run()
    assert not app.exception, [e.message for e in app.exception]
    token, data = app.session_state[LD.STORE]["fxl_dl_stage"]
    assert isinstance(data, bytes) and data[:2] == b"PK"            # یک xlsx واقعی
    assert "fxl_dl_stage__build" not in {b.key for b in app.button}

    app.run()                                                        # بازاجرای بعدی
    assert not app.exception
    assert app.session_state[LD.STORE]["fxl_dl_stage"][0] == token
    assert "fxl_dl_stage__build" not in {b.key for b in app.button}


@pytest.mark.skipif(not NATIVE, reason="این Streamlit callable را نمی‌پذیرد؛ مسیر قدیمی بالا آزموده شد")
def test_fx_page_on_new_streamlit_has_seven_direct_downloads(monkeypatch):
    monkeypatch.setattr(LD, "CALLABLE_DATA", True)
    app = _page().run()
    assert not app.exception, [e.message for e in app.exception]
    assert not [b for b in app.button if b.key and b.key.endswith("__build")]
    assert len(app.get("download_button")) >= len(FX_KEYS)

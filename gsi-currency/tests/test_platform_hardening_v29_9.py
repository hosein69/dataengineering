# -*- coding: utf-8 -*-
"""V29.9 — full-stack / UI platform contracts found in the package review."""
import ast
import os
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("gsi", "app", "OPS", "tools", "process-mining-ui-kit", "tests", "offline_validation")


def _py_files():
    for d in SOURCE_DIRS:
        yield from (ROOT / d).rglob("*.py")
    yield from ROOT.glob("*.py")


def test_every_source_file_compiles_on_the_running_interpreter():
    # 29.8.2 shipped app/process_cockpit.py with a Python-3.12-only f-string;
    # the declared minimum is 3.11, where the whole dashboard failed to import.
    bad = []
    for path in _py_files():
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as ex:
            bad.append(f"{path.relative_to(ROOT)}:{ex.lineno}: {ex.msg}")
    assert not bad, bad


def test_streamlit_config_is_offline_local_and_on_brand():
    from gsi.design import tokens as T
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["server"]["address"] == "127.0.0.1"
    assert cfg["client"]["toolbarMode"] == "viewer"
    theme = cfg["theme"]
    assert theme["primaryColor"].lower() == T.BRAND_TEAL.lower()
    assert theme["textColor"].lower() == T.TEXT.lower()
    assert theme["backgroundColor"].lower() == T.SURFACE_PAGE.lower()
    assert theme["secondaryBackgroundColor"].lower() == T.SURFACE_SUNKEN.lower()


def test_batch_launchers_are_crlf_ascii_and_bind_localhost():
    for path in ROOT.rglob("*.cmd"):
        if "review" in path.parts:
            continue
        raw = path.read_bytes()
        assert raw.isascii(), f"{path.name}: cmd.exe reads batch files in the OEM code page"
        lines = raw.split(b"\n")[:-1]
        assert lines and all(l.endswith(b"\r") for l in lines), f"{path.name}: LF-only breaks goto/call :label"
        text = raw.decode("ascii").lower()
        if "streamlit run" in text:
            assert ".venv\\scripts\\python.exe" in text and "--server.address=127.0.0.1" in text, path.name
            assert 'cd /d "%~dp0' in text, path.name


def test_material_icons_are_excluded_from_the_global_font_override():
    from app.styles import css
    style = css()
    assert '[data-testid="stIconMaterial"]' in style and "Material Symbols Rounded" in style


def test_kpi_card_never_prints_a_sentence_as_a_number():
    from app.styles import kpi_card
    card = kpi_card("جمع مانده تعهد", "کلید یا ارز ناقص؛ جمع قابل اتکا نیست", "Native", "#000")
    assert '<div class="val">—</div>' in card and "جمع قابل اتکا نیست" in card
    multi = kpi_card("جمع", "1,000.00 EUR | 20.00 USD · 2 ردیف خارج از جمع", "Native", "#000")
    assert multi.count('class="amt"') == 2 and "2 ردیف خارج از جمع" in multi.split('class="sub"')[1]


def test_reference_dates_are_shown_in_jalali_and_bidi_isolated():
    from gsi.core.jalali import date_label
    label = date_label("2026-08-31")
    assert "1405/06/09" in label and "⁦" in label and "⁩" in label
    assert date_label("") == "" and date_label("not-a-date") == "not-a-date"


def test_published_reference_date_is_read_without_loading_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("GSI_DWH_PATH", str(tmp_path / "none.sqlite"))
    from gsi.warehouse.service import published_reference_date
    assert published_reference_date() is None


def test_studio_sidebar_does_not_leak_server_paths():
    text = (ROOT / "app" / "studio.py").read_text(encoding="utf-8")
    assert 'caption(f"Runtime: {Path(__file__)' not in text


def test_windows_default_data_root_is_not_created_as_a_relative_folder(monkeypatch):
    from gsi.warehouse.store import default_data_root
    monkeypatch.delenv("GSI_DATA_ROOT", raising=False)
    root = default_data_root()
    if os.name != "nt":
        assert root.is_absolute() and "D:" not in str(root)
    monkeypatch.setenv("GSI_DATA_ROOT", "/srv/gsi")
    assert str(default_data_root()) == "/srv/gsi"


def test_bundled_ui_kit_cannot_shadow_the_gsi_app_package():
    # process-mining-ui-kit ships a top-level app.py. With app/ as a namespace
    # package, rendering the cash-flow explorer (which puts the kit on sys.path)
    # made every later ``import app.theme`` fail in the same process.
    import subprocess, sys as _sys
    code = ("import sys; sys.path.insert(0, r'%s'); sys.path.append(r'%s'); "
            "import app.theme, app; print(app.__file__)") % (ROOT, ROOT / "process-mining-ui-kit")
    out = subprocess.run([_sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT / "tests"))
    assert out.returncode == 0, out.stderr
    assert Path(out.stdout.strip()).parent == ROOT / "app"

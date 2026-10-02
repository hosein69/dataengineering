# -*- coding: utf-8 -*-
"""دور ۱۰: توقف انتشار روی PARTIAL_CLEARANCE_SCHEMA_LOSS (داده ساختگی).

فایل ترخیصی که بالای هدرش عنوان دارد یا ستون بارنامه‌اش «شماره بارنامه» است همان قرارداد را دارد و خوانده
می‌شود. فایلی که واقعاً ستون قراردادی ندارد هنوز انتشار را می‌بندد، ولی پیام خودش فایل، شیت و ستون غایب را می‌گوید.
"""
from __future__ import annotations

import sys

import openpyxl
import pytest

from gsi import health
from gsi.adapters.a30_customs import ClearanceAdapter
from gsi.config.sources import SourceSpec
from gsi.dataio.reader import _read_targets

SPEC = SourceSpec(key="clearance", folder=".", pattern="*", sheets=[None],
                  extra={"sheet_strategy": "all_data_sheets", "skip_sheets": ["Data"]})


def _book(path, sheet, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for r, row in enumerate(rows, 1):
        for c, v in enumerate(row, 1):
            if v is not None:
                ws.cell(r, c, v)
    wb.save(path)
    return str(path)


def test_title_rows_above_the_header_and_bl_alias_are_read(tmp_path):
    f = _book(tmp_path / "Border Clearance.xlsx", "Land Clearance",
              [["گزارش ترخیص مرزی"], [None], ["شماره بارنامه", "پرونده ترخیص", "کوتاژ"],
               ["AAAU1111111", "F1", "11"], ["BBBU2222222", "F2", None]])
    main = _read_targets(SPEC, [f])["main"]
    assert list(main["پرونده ترخیص"]) == ["F1", "F2"]
    out = ClearanceAdapter().transform({"main": main})["main"]
    assert list(out["CL_FILE_NO"]) == ["F1", "F2"] and list(out["KEY_BL"]) == ["AAAU1111111", "BBBU2222222"]


def test_file_without_contract_names_the_sheet_and_missing_column(tmp_path, caplog):
    good = _book(tmp_path / "Sea Clearance.xlsx", "Sea Clearance",
                 [["بارنامه", "پرونده ترخیص"], ["AAAU1111111", "F1"]])
    bad = _book(tmp_path / "Other Clearance.xlsx", "Land Clearance",
                [["بارنامه", "شماره پرونده"], ["TR-9", "X"]])
    rec = health.current().source("clearance")
    rec.schema_gaps.clear()
    out = _read_targets(SPEC, [good, bad])
    assert len(out["main"]) == 1
    gaps = [g for g in health.current().sources["clearance"].schema_gaps if "Other Clearance.xlsx" in g]
    assert gaps and "Land Clearance" in gaps[0] and "پرونده ترخیص" in gaps[0] and "شماره پرونده" in gaps[0]


def test_blocked_publish_ends_with_a_message_not_a_traceback(monkeypatch, capsys):
    import gsi.__main__ as entry
    from gsi.warehouse.store import QualityGateBlockedError

    def boom():
        raise QualityGateBlockedError("r1", [("source/clearance", "PARTIAL_CLEARANCE_SCHEMA_LOSS")])
    monkeypatch.setattr(entry, "main", boom)
    assert entry._entry() == 3
    text = capsys.readouterr().out
    assert "PARTIAL_CLEARANCE_SCHEMA_LOSS" in text and "Snapshot قبلی" in text

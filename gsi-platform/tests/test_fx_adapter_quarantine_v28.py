import os
import tempfile
from pathlib import Path
import pandas as pd


def _adapter():
    from gsi.adapters.a60_finance import FxTransactionAdapter
    return object.__new__(FxTransactionAdapter)


def test_fx_invalid_amount_is_quarantined_not_fatal(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv('GSI_DWH_PATH', str(Path(td) / 'wh.sqlite'))
        df = pd.DataFrame({
            'ثبت سفارش': ['12345678','12345679','12345680'],
            'سفارش': ['PO1','PO2','PO3'],
            'ارز خریداری شده': ['1,250.50','نامعتبر',None],
            'نوع ارز خریداری شده': ['EUR','USD','EUR'],
            'نرخ ارز خریداری شده': ['600000','610000','620000'],
            'معادل یورویی خرید ارز': ['1250.5','100','200'],
            'مبلغ ریالی': ['750300000','61000000','124000000'],
            'تاریخ خرید': ['1405/06/01','1405/06/02','1405/06/03'],
        })
        out = _adapter().transform({'Sheet1': df})
        assert len(out['main']) == 1
        assert float(out['main'].iloc[0]['FX_AMOUNT']) == 1250.5
        assert len(out['quarantine']) == 2
        assert set(out['quarantine']['_QUARANTINE_REASON']) == {'INVALID_PURCHASE_AMOUNT'}
        assert '_RAW_FX_AMOUNT' in out['quarantine'].columns


def test_fx_orphan_and_invalid_reasons_both_preserved(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv('GSI_DWH_PATH', str(Path(td) / 'wh.sqlite'))
        df = pd.DataFrame({
            'ثبت سفارش': ['', '12345678'],
            'سفارش': ['', 'PO1'],
            'ارز خریداری شده': ['100', 'x'],
            'نوع ارز خریداری شده': ['EUR','EUR'],
            'نرخ ارز خریداری شده': ['600000','600000'],
            'معادل یورویی خرید ارز': ['100','100'],
            'مبلغ ریالی': ['60000000','60000000'],
        })
        out = _adapter().transform({'Sheet1': df})
        assert out['main'].empty
        assert set(out['quarantine']['_QUARANTINE_REASON']) == {'NO_ORDER_OR_REG','INVALID_PURCHASE_AMOUNT'}

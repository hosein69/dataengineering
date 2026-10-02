import pandas as pd

from gsi.adapters.a50_ntsw import NtswAdapter
from gsi.adapters.a60_finance import IlAppendAdapter
from gsi.adapters.base import KEY_ORDER, KEY_REG, KEY_REG_FILE
from gsi.adapters.moghavemat import MoghavematAdapter


def test_ntsw_registration_number_and_code_are_one_reg_identity():
    reg = "12345678"
    by_number = pd.DataFrame([{"شماره ثبت سفارش": reg}])
    by_code = pd.DataFrame([{"کد ثبت سفارش": reg}])
    assert NtswAdapter._reg(by_number).iloc[0] == reg
    assert NtswAdapter._reg(by_code).iloc[0] == reg


def test_registration_file_is_distinct_from_registration_identity():
    frames = {"Import License": pd.DataFrame([{
        "شماره پرونده": "123456789",
        "شماره ثبت سفارش": "12345678",
        "وضعیت": "ثبت سفارش",
    }])}
    out = NtswAdapter().transform(frames)["import_license"]
    assert out.loc[out.index[0], KEY_REG_FILE] == "123456789"
    assert out.loc[out.index[0], KEY_REG] == "12345678"
    assert out.loc[out.index[0], KEY_REG_FILE] != out.loc[out.index[0], KEY_REG]


def test_order_number_and_our_reference_are_one_order_identity():
    order = "603128A"
    il = pd.DataFrame([{"شماره سفارش": order, "شماره ثبت سفارش": "12345678",
                        "شماره پرونده ثبت سفارش": "123456789"}])
    il_out = IlAppendAdapter().transform({"Append": il})["main"]

    expert = pd.DataFrame([{"Our Reference": order}])
    expert_out = MoghavematAdapter().transform({"Expert Data": expert})["lines"]

    assert il_out.loc[il_out.index[0], KEY_ORDER] == order
    assert expert_out.loc[expert_out.index[0], KEY_ORDER] == order

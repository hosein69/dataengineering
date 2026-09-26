# -*- coding: utf-8 -*-
from gsi.control_center.scope import resolve_scope_codes


def _cfg():
    return {"memberships": [
        {"employee_code":"10000001","cluster_id":"purchase","level":"expert","active":True},
        {"employee_code":"10000002","cluster_id":"purchase","level":"expert","active":True},
        {"employee_code":"10000003","cluster_id":"purchase","level":"manager","active":True},
        {"employee_code":"10000004","cluster_id":"purchase","level":"executive","active":True},
        {"employee_code":"10000005","cluster_id":"finance","level":"expert","active":True},
        {"employee_code":"10000006","cluster_id":"purchase","level":"expert","active":False},
    ]}


def test_expert_cluster_scope_is_self_only():
    m={"employee_code":"10000001","cluster_id":"purchase","level":"expert","active":True}
    assert resolve_scope_codes(_cfg(),"10000001",m)=={"10000001"}


def test_manager_cluster_scope_is_active_experts_plus_self():
    m={"employee_code":"10000003","cluster_id":"purchase","level":"manager","active":True}
    assert resolve_scope_codes(_cfg(),"10000003",m)=={"10000001","10000002","10000003"}


def test_executive_cluster_scope_is_all_active_cluster_members():
    m={"employee_code":"10000004","cluster_id":"purchase","level":"executive","active":True}
    assert resolve_scope_codes(_cfg(),"10000004",m)=={"10000001","10000002","10000003","10000004"}


def test_explicit_scope_augments_cluster_scope():
    m={"employee_code":"10000003","cluster_id":"purchase","level":"manager","active":True,
       "scope_employee_codes":"10000005"}
    assert "10000005" in resolve_scope_codes(_cfg(),"10000003",m)

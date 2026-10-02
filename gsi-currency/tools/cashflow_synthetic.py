# -*- coding: utf-8 -*-
"""Deterministic synthetic cash-flow inputs for equivalence tests and benchmarks.

Contains no organisational data. Every engine branch is exercised: cash and
non-cash events, reversals, FX conversion pairs, money/obligation links,
snapshots (including conflicting ones), approved rates and verified rules.
"""
from __future__ import annotations

import random

import pandas as pd

CURRENCIES = ["EUR", "CNY", "AED", "USD"]


def synthetic_inputs(cases: int = 60, seed: int = 7):
    rnd = random.Random(seed)
    events, links, measurements = [], [], []
    rates, rules = [], []

    def ev(eid, case, kind, amount, cur, day, **kw):
        row = dict(event_id=eid, case_id=case, kind=kind, amount=str(amount), currency=cur,
                   date=f"2026-01-{day:02d}", document="DOC-" + eid, source="bank",
                   status="POSTED", from_account="EXTERNAL:bank", to_account="OWN:bank")
        if kind in {"PAYMENT", "FEE", "FX_SELL"}:
            row.update(from_account="OWN:bank", to_account="EXTERNAL:supplier")
        if kind not in {"OPENING", "FUNDING", "REFUND", "FX_BUY", "PAYMENT", "FEE", "FX_SELL",
                        "TRANSFER", "REVERSAL"}:
            row.update(from_account="", to_account="")
        row.update(kw)
        events.append(row)
        return row

    for c in range(cases):
        case = f"R{c:05d}"
        cur = CURRENCIES[c % len(CURRENCIES)]
        base = rnd.randint(1, 9)
        ev(f"{case}-o", case, "OPENING", "0", cur, base)
        ev(f"{case}-f", case, "FUNDING", 1000 + c, cur, base + 1)
        pay = ev(f"{case}-p", case, "PAYMENT", 400 + c % 50, cur, base + 2,
                 order_id=f"O{c}", bl_id=f"BL{c}")
        ev(f"{case}-fee", case, "FEE", "5.25", cur, base + 3)
        ev(f"{case}-reg", case, "REGISTRATION", 5000, cur, base)
        ev(f"{case}-q", case, "QUEUE", 900, cur, base + 1)
        ev(f"{case}-a", case, "ALLOCATION", 900, cur, base + 2)
        ev(f"{case}-au", case, "ALLOCATION_USE", 300, cur, base + 5)
        com = ev(f"{case}-c", case, "COMMITMENT", 900, cur, base + 2,
                 due_date="2026-03-01", rule_id="RULE-1")
        st = ev(f"{case}-s", case, "SETTLEMENT", 250 + c % 7, cur, base + 8)
        ev(f"{case}-sh", case, "SHIPMENT", 400 + c % 50, cur, base + 4,
           order_id=f"O{c}", bl_id=f"BL{c}")
        ev(f"{case}-cu", case, "CUSTOMS", 390, cur, base + 6, order_id=f"O{c}", bl_id=f"BL{c}")
        ev(f"{case}-cl", case, "CLEARANCE", "", "", base + 7)
        ev(f"{case}-bd", case, "BANK_DOCS", "", "", base + 9)
        if c % 5 == 0:
            ev(f"{case}-rv", case, "REVERSAL", "5.25", cur, base + 10, reversal_of=f"{case}-fee",
               from_account="EXTERNAL:supplier", to_account="OWN:bank")
        if c % 7 == 0:  # FX conversion pair
            other = "EUR" if cur != "EUR" else "CNY"
            ev(f"{case}-xs", case, "FX_SELL", 100, cur, base + 3, group_id=f"G{c}",
               from_account="OWN:bank", to_account="EXTERNAL:exchange")
            ev(f"{case}-xb", case, "FX_BUY", 110, other, base + 3, group_id=f"G{c}",
               from_account="EXTERNAL:exchange", to_account="OWN:fx")
        if c % 11 == 0:  # broken pair
            ev(f"{case}-xbad", case, "FX_SELL", 10, cur, base + 3, group_id=f"GB{c}",
               from_account="OWN:bank", to_account="EXTERNAL:exchange")
        if c % 13 == 0:  # duplicate + conflicting id
            events.append(dict(events[-1]))
            bad = dict(events[-1]); bad["amount"] = "999"; bad["event_id"] = f"{case}-dup"
            events.append(bad); b2 = dict(bad); b2["amount"] = "998"; events.append(b2)
        links.append(dict(link_id=f"L{c}-fp", from_event=f"{case}-f", to_event=pay["event_id"],
                          from_amount=str(300), to_amount=str(300), document="LNK"))
        links.append(dict(link_id=f"L{c}-ps", from_event=pay["event_id"], to_event=f"{case}-sh",
                          from_amount=str(200), to_amount=str(200), document="LNK"))
        links.append(dict(link_id=f"L{c}-cs", from_event=com["event_id"], to_event=st["event_id"],
                          from_amount=str(200), to_amount=str(200), document="LNK",
                          relation_type="OBLIGATION_SETTLEMENT"))
        if c % 9 == 0:  # over-allocation
            links.append(dict(link_id=f"L{c}-over", from_event=f"{case}-f", to_event=pay["event_id"],
                              from_amount=str(5000), to_amount=str(5000), document="LNK"))
        for k, day in enumerate((20, 31)):
            measurements.append(dict(measurement_id=f"M{c}-{k}", case_id=case, metric="COMMITMENT_BALANCE",
                                     observed_at=f"2026-01-{day}", amount=str(700 - k),
                                     currency=cur, source="NTSW", document="screen"))
        if c % 17 == 0:
            measurements.append(dict(measurement_id=f"M{c}-x", case_id=case, metric="COMMITMENT_BALANCE",
                                     observed_at="2026-01-31", amount="1", currency=cur,
                                     source="NTSW", document="screen"))
    for i, cur in enumerate(CURRENCIES):
        for day in (1, 10, 20):
            for purpose in ("accounting", "customs", "settlement"):
                rates.append(dict(rate_id=f"{cur}-{day}-{purpose}", date=f"2026-01-{day:02d}",
                                  base=cur, quote="IRR", rate=str(500000 + i * 1000 + day),
                                  purpose=purpose, approved="true", source="CBI",
                                  max_age_days="40", regime="", source_document="doc",
                                  source_hash="a" * 64, approved_by="x", approved_at="2026-01-01"))
    rates.append(dict(rate_id="EUR-CNY", date="2026-01-01", base="EUR", quote="CNY", rate="7.9",
                      purpose="accounting", approved="true", source="CBI", max_age_days="40", regime=""))
    rules.append(dict(rule_id="RULE-1", kind="COMMITMENT", jurisdiction="IR", authority="CBI",
                      source="CBI", source_url="https://example.invalid", source_hash="b" * 64,
                      approved="true", approved_by="x", approved_at="2026-01-01",
                      effective_from="2025-01-01", effective_to="2027-01-01"))
    return (pd.DataFrame(events), pd.DataFrame(links), pd.DataFrame(rates),
            pd.DataFrame(rules), pd.DataFrame(measurements))

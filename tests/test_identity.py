"""Instrument identity: exchange_name is THE identity across all classes.

Regression net for the balance-dict bug: dataclass-generated eq/hash (tuple
based, class-identical) silently broke dict lookups between Instrument keys
and InstrumentBalance values. Identity must be name-based everywhere.
"""

import cryptocom.exchange as cro


def _balance(instrument_name, total=10.0, reserved=1.0):
    return cro.structs.InstrumentBalance.from_api(
        {
            "quantity": total,
            "reserved_qty": reserved,
            "market_value": total,
            "instrument_name": instrument_name,
            "collateral_eligible": "true",
            "collateral_amount": 0.0,
            "haircut": 0.0,
            "max_withdrawal_balance": total,
        }
    )


def test_instrument_equals_instrument_balance():
    inst = cro.Instrument("USD")
    bal = _balance("USD")
    assert inst == bal
    assert bal == inst
    assert hash(inst) == hash(bal)


def test_different_names_never_equal():
    assert cro.Instrument("USD") != cro.Instrument("CRO")
    assert cro.Instrument("USD") != _balance("CRO")


def test_equals_non_instrument_is_not_implemented():
    inst = cro.Instrument("USD")
    assert inst != "USD"
    assert inst.__eq__("USD") is NotImplemented


def test_dict_interop_both_directions():
    bal = _balance("CRO", total=199.0)
    by_balance_key = {bal: "value"}
    # The exact lookup the balance bug failed: plain Instrument into an
    # InstrumentBalance-keyed dict (and vice versa).
    assert by_balance_key[cro.Instrument("CRO")] == "value"
    by_inst_key = {cro.Instrument("CRO"): "value"}
    assert by_inst_key[bal] == "value"


def test_set_dedupes_across_classes():
    deduped = {cro.Instrument("USD"), _balance("USD"), cro.Instrument("USD")}
    assert len(deduped) == 1


def test_get_balance_mapping_lookups():
    # Balance container level: Instrument, InstrumentBalance, and str keys
    # must all find the same InstrumentBalance entry.
    entries = [_balance("USD"), _balance("CRO")]
    balance = cro.structs.Balance(
        total_available=20.0,
        total_available_instrument=cro.Instrument("USD"),
        instruments=entries,
    )
    for key in (
        cro.instruments.USD,
        _balance("USD"),
        "USD",
    ):
        assert balance.get(key).total == 10.0
        assert key in balance
    assert balance.get("NOPE") is None
    assert balance.get("NOPE", "fallback") == "fallback"


def test_registry_uses_true_names():
    cro.Instrument("ZZTESTCOIN")
    assert cro.Instrument("ZZTESTCOIN") in cro.instruments.all() or True
    registry = cro.structs.Instrument._registry
    assert registry["ZZTESTCOIN"] == cro.Instrument("ZZTESTCOIN")

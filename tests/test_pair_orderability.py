"""Pair orderability: grid alignment, minimum quantity, minimum notional.

Pure unit tests over real instrument data (exch.pairs) - no API involved.
Guards the math that lets a bot decide placeable vs stranded remainders:
CRO_USD has whole-unit quantity (tick 1.0) and a $1 min notional, so a
1 CRO remainder at $0.05 is NOT placeable and must never be re-quoted.
"""

import cryptocom.exchange as exch
import pytest

CRO = exch.pairs.CRO_USD


def test_cro_usd_step_is_whole_units() -> None:
    assert CRO.quantity_tick_size == 1.0


def test_floor_quantity_snaps_down_to_grid() -> None:
    assert CRO.floor_quantity(199.9) == 199.0
    assert CRO.floor_quantity(199.0) == 199.0
    assert CRO.floor_quantity(0.5) == 0.0
    assert CRO.floor_quantity(-3.0) == -3.0  # floors, does not clamp


def test_min_order_quantity_at_price_uses_notional() -> None:
    # $1 min notional at $0.05 -> need 20 units minimum
    assert CRO.min_order_quantity_at(0.05) == 20.0
    # at $1000 one unit clears the notional already
    assert CRO.min_order_quantity_at(1000.0) == 1.0
    # price guards
    assert CRO.min_order_quantity_at(0.0) == 0.0
    assert CRO.min_order_quantity_at(-1.0) == 0.0


def test_is_orderable_grid_min_quantity_and_notional() -> None:
    assert CRO.is_orderable(20, 0.05)  # exactly at the derived minimum
    assert CRO.is_orderable(199, 0.05)
    assert not CRO.is_orderable(19, 0.05)  # $0.95 notional - below minimum
    assert not CRO.is_orderable(1, 0.05)  # $0.05 - the stranded-remainder case
    assert not CRO.is_orderable(0, 0.05)
    assert not CRO.is_orderable(100, 0)
    assert not CRO.is_orderable(100.5, 0.05)  # off the whole-unit grid


def test_precision_grid_when_tick_absent() -> None:
    pair = exch.Pair(
        exchange_name="TST_USD",
        price_precision=2,
        quantity_precision=2,
        inst_type=exch.InstrumentType.SPOT,
        quantity_tick_size=0.0,
        min_order_notional_usd=1.0,
    )
    assert pair.quantity_tick_size == pytest.approx(0.01)
    assert pair.floor_quantity(3.456) == pytest.approx(3.45)
    # $1 at $2 -> 0.5 units -> ceil to grid = 0.50 exactly
    assert pair.min_order_quantity_at(2.0) == pytest.approx(0.5)
    assert pair.is_orderable(0.5, 2.0)
    assert not pair.is_orderable(0.49, 2.0)  # $0.98 notional


def test_minimum_quantity_field_is_honoured() -> None:
    pair = exch.Pair(
        exchange_name="BIG_USD",
        price_precision=2,
        quantity_precision=0,
        inst_type=exch.InstrumentType.SPOT,
        quantity_tick_size=1.0,
        min_order_quantity=100.0,
        min_order_notional_usd=1.0,
    )
    assert (
        pair.min_order_quantity_at(1000.0) == 100.0
    )  # notional says 1, min qty says 100
    assert pair.is_orderable(100, 1000.0)
    assert not pair.is_orderable(99, 1000.0)


def test_max_notional_boundary() -> None:
    assert CRO.is_orderable(1_000_000, 1.0)  # exactly at the default max
    assert not CRO.is_orderable(1_000_001, 1.0)


def test_notional_boundary_survives_binary_product_noise() -> None:
    """The exchange multiplies DECIMALS; our float product must not lie.

    100 x 0.29 is exactly $29 on the exchange, but the IEEE-754 product is
    28.999999999999996 - with a $29 min notional the order IS placeable and
    must not be rejected (nor, worse, flip a bot into HOLDing a perfectly
    placeable quote). Genuine sub-minimum notionals stay rejected.
    """
    pair = exch.structs.Pair(
        exchange_name="NOISE_USD",
        price_precision=2,
        quantity_precision=2,
        inst_type=exch.structs.InstrumentType.SPOT,
        quantity_tick_size=1.0,
        min_order_notional_usd=29.0,
    )
    assert 100 * 0.29 < 29.0, "the float noise is real (guard the premise)"
    assert pair.validate_order_notional(100 * 0.29)
    assert pair.is_orderable(100, 0.29)
    assert not pair.is_orderable(99, 0.29)  # $28.71: genuinely below


def test_floor_quantity_survives_sum_noise() -> None:
    """Ledger SUMs of grid values carry last-bit noise: 0.1+0.1+0.1 is not 0.3."""
    pair = exch.structs.Pair(
        exchange_name="GRID_USD",
        price_precision=2,
        quantity_precision=2,
        inst_type=exch.structs.InstrumentType.SPOT,
        quantity_tick_size=0.1,
    )
    assert 0.1 + 0.1 + 0.1 != 0.3, "the float noise is real (guard the premise)"
    assert pair.floor_quantity(0.1 + 0.1 + 0.1) == 0.3
    assert pair.is_orderable(pair.floor_quantity(0.1 + 0.1 + 0.1), 100.0)


def test_grid_semantic_predicates_replace_epsilon_comparisons() -> None:
    """has_quantity / same_quantity / quantity_reaches / has_price_value.

    These carry the representability judgements a bot otherwise spells
    with a hand-tuned epsilon - on the pair's REAL grid.
    """
    # has_quantity: dust floors to zero, a real unit does not
    assert CRO.has_quantity(1.0)
    assert CRO.has_quantity(1.4)  # floors to 1
    assert not CRO.has_quantity(0.99)  # sub-tick dust is "no quantity"
    assert not CRO.has_quantity(1e-16)  # float noise is "no quantity"

    # same_quantity: ulp-different spellings of one grid step are equal
    assert CRO.same_quantity(34.0, 33.999999999999996)
    assert not CRO.same_quantity(34.0, 33.0)

    # quantity_reaches: accumulation noise reaches the target, real
    # shortfall does not
    assert CRO.quantity_reaches(199.99999999999997, 200.0)
    assert CRO.quantity_reaches(200.0, 200.0)
    assert not CRO.quantity_reaches(199.5, 200.0)

    # has_price_value on the price grid (CRO price_precision 5)
    assert CRO.has_price_value(0.05)
    assert not CRO.has_price_value(1e-17)
    assert not CRO.has_price_value(0.0)

    # precision-grid pair behaves on ITS grid, not CRO's
    fine = exch.Pair(
        exchange_name="FINE_USD",
        price_precision=2,
        quantity_precision=2,
        inst_type=exch.InstrumentType.SPOT,
    )
    assert fine.has_quantity(0.012)  # floors to 0.01
    assert not fine.has_quantity(0.009)  # sub-tick dust
    assert fine.quantity_reaches(1.99999999999997, 2.0)  # ulp noise snaps
    # a gap WIDER than the rounding tolerance is a real shortfall, not
    # noise - even when it is smaller than one grid step:
    assert not fine.quantity_reaches(1.9999999, 2.0)

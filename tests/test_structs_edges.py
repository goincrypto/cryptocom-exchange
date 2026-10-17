"""Edge tests for structs: pair dict fallback, notional bounds, parsers."""

import cryptocom.exchange as cro
import pytest
from cryptocom.exchange.structs import (
    BaseCurrencyConfig,
    DefaultPairDict,
    Deposit,
    DepositStatus,
    OrderInBook,
    RiskParameters,
)

PAIR = cro.pairs.CRO_USD


# ============================================================================
# Pair validation & DefaultPairDict fallback
# ============================================================================


def test_validate_order_notional_bounds():
    pair = cro.pairs.CRO_USD
    assert pair.validate_order_notional(pair.min_order_notional_usd)
    assert not pair.validate_order_notional(pair.min_order_notional_usd - 0.01)
    assert pair.validate_order_notional(pair.max_order_notional_usd)
    assert not pair.validate_order_notional(pair.max_order_notional_usd + 1)


def test_default_pair_dict_synthesizes_missing_pairs():
    # NOTE: pairs.all() returns the live REGISTRY - Market.sync_pairs()
    # replaces entries with API-built instances. Assert by name, not
    # identity against the module constant.
    registry = {p.name: p for p in cro.pairs.all()}
    d = DefaultPairDict(**registry)
    assert d["CRO_USD"].exchange_name == "CRO_USD"

    registry_keys_before = set(cro.structs.Pair._registry)
    ghost = d["SOME_DELISTED_TOKEN_USD"]
    # Defaults for old/deleted pairs (precision 8 as used by test_account)
    assert ghost.price_precision == 8
    assert ghost.quantity_precision == 8
    assert ghost.exchange_name == "SOME_DELISTED_TOKEN_USD"
    # Fallback pairs are deleted=True -> must NOT pollute the registry
    assert set(cro.structs.Pair._registry) == registry_keys_before


# ============================================================================
# OrderInBook volume
# ============================================================================


def test_order_in_book_volume_rounds_down():
    level = OrderInBook(
        price=0.0534,
        quantity=1234.0,
        count=3,
        pair=PAIR,
        side=cro.OrderSide.BUY,
    )
    exact = 0.0534 * 1234.0
    assert level.volume <= exact  # conservative rounding, never overstates
    assert abs(level.volume - exact) < 1e-4


# ============================================================================
# Transaction parsers (offline payloads)
# ============================================================================


def test_deposit_parser_full_and_defaults():
    deposit = Deposit.create_from_api(
        {
            "id": "d-1",
            "currency": "CRO",
            "fee": "0.0",
            "create_time": "1700000000000",
            "update_time": "1700000001000",
            "amount": "123.45",
            "address": "addr-1",
            "status": "1",
        }
    )
    assert deposit.status is DepositStatus.ARRIVED
    assert deposit.amount == 123.45
    assert deposit.instrument == cro.Instrument("CRO")


# ============================================================================
# BaseCurrencyConfig / RiskParameters parsing (shapes from live API captures)
# ============================================================================


def test_base_currency_config_parser():
    cfg = BaseCurrencyConfig.from_api(
        {
            "instrument_name": "USD",
            "min_order_notional_usd": "1.0",
            "max_order_notional_usd": "1000000.0",
            "order_limit": "500",
            "minimum_haircut": "0",
            "unit_margin_rate": "1",
        }
    )
    assert cfg.instrument_name == "USD"
    assert cfg.min_order_notional_usd == 1.0
    assert cfg.order_limit == 500.0
    # Optionals absent from the payload stay None (explicit-absence signal)
    assert cfg.collateral_cap_notional is None
    assert cfg.max_product_leverage_for_spot is None


def test_base_currency_config_parser_optionals():
    cfg = BaseCurrencyConfig.from_api(
        {
            "instrument_name": "CRO",
            "collateral_cap_notional": "500000",
            "max_product_leverage_for_spot": "2.5",
        }
    )
    assert cfg.collateral_cap_notional == 500000.0
    assert cfg.max_product_leverage_for_spot == 2.5


def test_risk_parameters_parser():
    params = RiskParameters.from_api(
        {
            "config_seq": 1,
            "config_ts": 1700000000000,
            "config_change_reason": "INIT",
            "max_withdraw_ratio": "0.9",
            "default_leverage_max": "10",
            "default_leverage_min": "1",
            "account_leverage_max": "10",
            "account_leverage_min": "1",
            "initial_margin_ratio_min": "0.1",
            "initial_margin_ratio_max": "1",
            "maintenance_margin_ratio_min": "0.05",
            "maintenance_margin_ratio_max": "1",
            "liquidation_fee_rate": "0.01",
            "liquidation_call_fee_rate": "0.005",
            "portfolio_margin_enabled": "false",
            "portfolio_margin_eligible": "false",
            "min_open_position_limit": "100",
            "max_position_limit": "1000000",
            "position_limit_hit_warning_threshold": "100000",
            "position_limit_hit_warning_threshold_usd": "100000",
            "max_open_position_limit": "1000000",
            "margin_call_ratio": "0.1",
            "base_currency_2_config_map": {},
            "cross_currency_configs": {},
            "currency_configs": {},
            "currency_configs_v2": {},
            "index_oracle": "CHAINLINK",
            "insurance_capped_amount": "0",
            "insurance_fund_ratio": "0",
            "insurance_fund_share_ratio": "0",
            "insurance_fund_share_cap": "0",
            "mmp_violation_periods": "[]",
            "auto_deleveraging_free_tier": "0",
            "order_rate_limits": "[]",
            "min_liquidation_fee": "0",
            "max_liquidation_fee": "0",
            "min_ad_free_amount": "0",
        }
    )
    assert params is not None


# ============================================================================
# Grid normalization, placeability, and fill-field defaults
# ============================================================================


def test_ticks_are_always_present():
    """An unset tick is derived from the precision decimal at construction.

    A zero grid step would wedge any decrement-to-fit loop downstream -
    so Pair guarantees a positive tick for BOTH grids, always.
    """
    registry = {p.name: p for p in cro.pairs.all()}
    ghost = DefaultPairDict(**registry)["SOME_UNLISTED_TOKEN_USD"]
    assert ghost.quantity_tick_size == 1e-8
    assert ghost.price_tick_size == 1e-8

    sparse = cro.Pair(
        exchange_name="TEST_USD",
        price_precision=4,
        quantity_precision=2,
        inst_type=cro.InstrumentType.SPOT,
    )
    assert sparse.quantity_tick_size == 0.01
    assert sparse.price_tick_size == 1e-4
    # authoritative tick survives when provided (CRO trades whole units)
    assert cro.pairs.CRO_USD.quantity_tick_size == 1.0


def test_is_placeable_floors_before_checking():
    """is_placeable = floor onto the grid, then the orderable contract."""
    pair = cro.pairs.CRO_USD  # tick 1.0, min quantity/notional from the venue
    assert pair.is_placeable(20.9, 1.0)  # floors to 20 - placeable
    assert not pair.is_placeable(0.9, 1.0)  # floors to 0 - nothing left
    assert not pair.is_placeable(5, 0.0)  # no usable price
    assert not pair.is_placeable(20.5, 0.01)  # floored notional below minimum


def test_order_fill_fields_default_to_zero_float():
    """A never-filled order parses filled_* as 0.0 floats, never None/KeyError."""
    payload = {
        "order_id": "1",
        "account_id": "a",
        "client_oid": "c",
        "order_type": "LIMIT",
        "time_in_force": "GOOD_TILL_CANCEL",
        "side": "BUY",
        "exec_inst": [],
        "quantity": "20",
        "limit_price": "0.05",
        "order_value": "1.0",
        "status": "ACTIVE",
        "update_user_id": "u",
        "order_date": "2026-01-01",
        "fee_instrument_name": "USD",
        "create_time": 1,
        "update_time": 1,
        "create_time_ns": 1,
    }
    order = cro.structs.Order.create_from_api(PAIR, payload)
    assert order.filled_quantity == 0.0
    assert order.filled_volume == 0.0
    assert order.filled_fee == 0.0
    assert order.filled_price == 0.0
    # and explicitly-null fields must not sneak None through
    order2 = cro.structs.Order.create_from_api(
        PAIR, {**payload, "cumulative_quantity": None, "avg_price": None}
    )
    assert order2.filled_quantity == 0.0
    assert order2.filled_price == 0.0


def test_order_fill_fields_normalize_noise_and_negatives():
    """Parse CONTRACT: fills are exactly 0.0 or exchange-representable.

    Sub-precision residue (float noise, venue dust) and malformed
    negatives collapse to 0.0 at PARSE time - so callers may test
    `> 0.0` instead of carrying epsilon comparisons against order fields.
    """
    payload = {
        "order_id": "1",
        "account_id": "a",
        "client_oid": "c",
        "order_type": "LIMIT",
        "time_in_force": "GOOD_TILL_CANCEL",
        "side": "BUY",
        "exec_inst": [],
        "quantity": "20",
        "limit_price": "0.05",
        "order_value": "1.0",
        "status": "ACTIVE",
        "update_user_id": "u",
        "order_date": "2026-01-01",
        "fee_instrument_name": "USD",
        "create_time": 1,
        "update_time": 1,
        "create_time_ns": 1,
    }
    # CRO_USD has quantity_precision 0: anything sub-unit is noise.
    noisy = cro.structs.Order.create_from_api(
        PAIR,
        {
            **payload,
            "cumulative_quantity": "1e-16",
            "cumulative_value": "0.000000001",
            "avg_price": "-0.0000001",
            "cumulative_fee": "-1e-12",
        },
    )
    assert noisy.filled_quantity == 0.0
    assert noisy.filled_volume == 0.0
    assert noisy.filled_price == 0.0
    assert noisy.filled_fee == 0.0
    # a REAL fill close to a grid point is tolerance-snapped, not lost:
    real = cro.structs.Order.create_from_api(
        PAIR, {**payload, "cumulative_quantity": "33.999999999"}
    )
    assert real.filled_quantity == pytest.approx(34.0)


# ============================================================================
# MarketTrade timestamp precision - the cursor `get_trades` paginates by
# ============================================================================


def test_market_trade_keeps_full_nanosecond_precision():
    """A 19-digit ns stamp must survive parsing exactly, int or digit-string.

    A float64 is exact only to 2**53 = 9_007_199_254_740_992, and an ns epoch stamp is ~1.8e18,
    so routing `tn` through float() rounds it. The old parser lost 7 ns on a real CRO_USD print.
    """
    ns = 1792256250893942777
    for raw_ns in (ns, str(ns)):
        trade = cro.structs.MarketTrade.from_api(
            PAIR,
            {
                "d": "1",
                "t": 1792256250893,
                "tn": raw_ns,
                "p": "0.05686",
                "q": "164",
                "s": "sell",
            },
        )
        assert trade.timestamp_ns == ns, f"lost precision parsing {raw_ns!r}"
        assert trade.time == ns // 1_000_000_000


def test_market_trade_never_collapses_two_prints_in_the_same_second():
    """Prints one nanosecond apart stay distinct - the collision that hid trades.

    `get_trades` walks `end_ts` back to the oldest print it saw; if two prints share a parsed
    timestamp, the walk can no longer tell them apart and the rest of that second goes missing.
    """
    base = 1792256250893942777

    def parse(ns):
        return cro.structs.MarketTrade.from_api(
            PAIR,
            {
                "d": str(ns),
                "t": ns // 1_000_000,
                "tn": ns,
                "p": "0.05686",
                "q": "1",
                "s": "buy",
            },
        )

    first, second = parse(base), parse(base + 1)
    assert first.timestamp_ns != second.timestamp_ns
    assert first.id != second.id


def test_market_trade_without_nanoseconds_falls_back_to_milliseconds():
    """WebSocket-sourced rows carry no `tn`; ms must convert without inventing digits."""
    trade = cro.structs.MarketTrade.from_api(
        PAIR, {"d": "9", "t": 1792256250893, "p": "0.05686", "q": "1", "s": "buy"}
    )
    assert trade.timestamp_ns == 1792256250893 * 1_000_000
    assert trade.time == 1792256250

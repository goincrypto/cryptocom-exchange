"""Edge tests for structs: pair dict fallback, notional bounds, parsers."""

import cryptocom.exchange as cro
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

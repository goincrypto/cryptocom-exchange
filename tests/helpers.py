"""Shared test helpers: pair-legal order sizing derived from pair rules."""

import cryptocom.exchange as cro


def min_order_quantity(pair: cro.Pair, price: float, margin: float = 1.1) -> float:
    """Smallest quantity legal for `price`, with a notional safety `margin`.

    Respects the pair's quantity tick and minimums - no hand-picked ints.
    """
    raw = pair.min_order_notional_usd * margin / price
    qty = pair.round_quantity_up(raw)
    while qty * price < pair.min_order_notional_usd:
        qty = pair.round_quantity_up(qty + pair.quantity_tick_size)
    return max(qty, pair.quantity_tick_size, pair.min_order_quantity)


def resting_buy_price(pair: cro.Pair, market_price: float, ticks: int = 10) -> float:
    """Buy price safely BELOW market (maker, stays open)."""
    price = pair.round_price_down(market_price - ticks * pair.price_tick_size)
    # Very cheap instruments: 10 ticks may not clear the spread noise.
    floor_floor = pair.round_price_down(market_price * 0.98)
    return min(price, floor_floor)


def resting_sell_price(pair: cro.Pair, market_price: float, ticks: int = 10) -> float:
    """Sell price safely ABOVE market (maker, stays open)."""
    price = pair.round_price_up(market_price + ticks * pair.price_tick_size)
    ceil_price = pair.round_price_up(market_price * 1.02)
    return max(price, ceil_price)

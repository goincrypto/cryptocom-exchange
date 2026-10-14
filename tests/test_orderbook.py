"""OrderBook normalization and best-price accessors.

Unit tests pin the best-first invariant; the live test validates it against
the real public order book (public endpoints need no API keys).
"""

import pytest

import cryptocom.exchange as cro


def _level(pair, price, quantity=1000.0):
    return cro.structs.OrderInBook(
        price=price,
        quantity=quantity,
        count=1,
        pair=pair,
        side=cro.OrderSide.BUY,
    )


@pytest.fixture
def pair():
    return cro.pairs.CRO_USDT


def test_normalization_is_best_first(pair):
    """Constructor order must not matter: buys DESC, sells ASC, both best-first."""
    buys = [_level(pair, p) for p in (0.0497, 0.0500, 0.0499)]
    sells = [_level(pair, p) for p in (0.0506, 0.0501, 0.0503)]
    book = cro.structs.OrderBook(buys=buys, sells=sells, pair=pair)

    assert [lvl.price for lvl in book.buys] == [0.0500, 0.0499, 0.0497]
    assert [lvl.price for lvl in book.sells] == [0.0501, 0.0503, 0.0506]
    assert book.best_bid.price == 0.0500
    assert book.best_ask.price == 0.0501
    assert abs(book.mid - 0.05005) < 1e-12
    assert 0 < book.spread < 0.01


def test_empty_book_raises_clear_error(pair):
    empty = cro.structs.OrderBook(buys=[], sells=[], pair=pair)
    with pytest.raises(ValueError, match="no bids"):
        _ = empty.best_bid
    with pytest.raises(ValueError, match="no asks"):
        _ = empty.best_ask

    one_sided = cro.structs.OrderBook(
        buys=[_level(pair, 0.05)], sells=[], pair=pair
    )
    assert one_sided.best_bid.price == 0.05
    with pytest.raises(ValueError, match="no asks"):
        _ = one_sided.best_ask


@pytest.mark.asyncio
async def test_live_public_orderbook():
    """Public get-book without API keys: accessors must match raw extremes."""
    api = cro.ApiProvider(api_key="public", api_secret="public", auth_required=False)
    market = cro.Market(api=api)

    book = await market.get_orderbook(cro.pairs.CRO_USDT, depth=10)

    assert book.buys and book.sells
    assert book.best_bid.price == max(lvl.price for lvl in book.buys)
    assert book.best_ask.price == min(lvl.price for lvl in book.sells)
    assert book.best_bid.price < book.best_ask.price
    assert book.buys[0] is book.best_bid and book.sells[0] is book.best_ask
    assert 0 < book.spread < 0.05
    assert book.best_bid.price < book.mid < book.best_ask.price

## Python 3.11+ async library for crypto.com/exchange API using httpx and websockets

[![Docs Build Status](https://readthedocs.org/projects/cryptocom-exchange/badge/?version=latest&style=flat)](https://readthedocs.org/projects/cryptocom-exchange)
![Test workflow](https://github.com/goincrypto/cryptocom-exchange/actions/workflows/test_release.yml/badge.svg)
[![PyPI implementation](https://img.shields.io/pypi/implementation/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI license](https://img.shields.io/pypi/l/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI version fury.io](https://badge.fury.io/py/cryptocom-exchange.svg)](https://badge.fury.io/py/cryptocom-exchange/)
[![PyPI download month](https://img.shields.io/pypi/dm/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![Gitter](https://badges.gitter.im/goincrypto/cryptocom-exchange.svg)](https://gitter.im/goincrypto/cryptocom-exchange?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

Documentation: [https://cryptocom-exchange.rtfd.io](https://cryptocom-exchange.rtfd.io)

Exchange original API docs: [https://exchange-docs.crypto.com](https://exchange-docs.crypto.com)

### Description

`pip install cryptocom-exchange` or `poetry add cryptocom-exchange`

- fully operational v1 exchange API, including websocket streams
- typed error taxonomy with an explicit indeterminate/deterministic contract
- `Account` order cache and cancel/wait primitives that never assume an outcome
- per-endpoint rate limits, bounded retries with optional backoff
- offline test suite replaying captured exchange responses, coverage gated at 90%

### Quick start

`Market` covers public data and needs no keys; `Account` covers trading.

```python
import asyncio

import cryptocom.exchange as cro


async def main():
    # public endpoints need no keys
    market = cro.Market()
    print(f"CRO price: {await market.get_price(cro.pairs.CRO_USD)}")

    # reads CRYPTOCOM_API_KEY / CRYPTOCOM_API_SECRET
    account = cro.Account(from_env=True)
    balance = await account.get_balance()  # dict[Instrument, InstrumentBalance]
    print(f"USD available: {balance[cro.instruments.USD].available}")


asyncio.run(main())
```

Pairs ship with the package as `cro.pairs.CRO_USD` and friends. Call
`await market.sync_pairs()` (or `await account.sync_pairs()`) to replace them
with the live instrument list.

### Error handling

Errors live in `cryptocom.exchange.exceptions`: named subclasses are mapped
from exchange error codes by `api_error_from_response`, and everything derives
from `ApiError`. The property that drives safe orchestration is
`is_indeterminate`.

- **Deterministic** (`is_indeterminate` is `False`): the exchange explicitly
  rejected the request with a known code — `ExchangeError` and its subclasses
  (`NotEnoughBalanceError`, `OrderNotFoundError`, `PostOnlyRejectedError`,
  `InvalidInstrumentError`, ...). The order was not created and nothing
  changed, so it is safe to act on that answer.
- **Indeterminate** (`True`): the outcome is unknown — `ApiError` with
  `code=None` (transport failure, timeout, malformed reply, HTTP 5xx without
  an API code) plus the known-code-but-unknowable `RequestTimeoutError`
  (40801) and `InternalError` (50001, 120009). Never read it as "did not
  happen" and never resend blindly: re-query by `client_oid`.

Branch on `is_indeterminate`, not on the exception class:

```python
try:
    keys = await account.create_order(
        pair,
        cro.OrderSide.BUY,
        cro.OrderType.LIMIT,
        quantity=100,
        price=0.05,
        client_id=client_id,
    )
except cro.ApiError as exc:
    if exc.is_indeterminate:
        # Unknown outcome: reconcile by client_oid, never resend blindly.
        order = await account.get_order(client_order_id=client_id, ignore_cache=True)
    else:
        # Deterministic rejection: exc.code is set, the order does not exist.
        log.warning("rejected %s: %s", exc.code, exc)
```

HTTP statuses route through the same taxonomy in `ApiProvider`: 401/403 →
`ApiAuthError`; a body carrying an API code → the taxonomy; 5xx without a code
→ indeterminate `ApiError`; any other 4xx → deterministic `ExchangeError`
carrying the HTTP status.

`retries` counts retries *after* the first attempt and is one budget for every
failure kind, transport errors included; `retry_backoff` sleeps between
attempts. Only transient failures retry: `RETRYABLE_ERROR_CODES` (40801,
42901, 10006, 50001, 120009, 9010001) and HTTP 408/429/5xx, testable with
`is_retryable_error_code`. A deterministic rejection raises on the first
response.

### Orders

`Account` caches orders by `client_oid` in `Account.order_cache` (the snippets
here use `from cryptocom.exchange import exceptions`). Terminal
entries (`Order.is_terminal`, `TERMINAL_ORDER_STATUSES`) are final and live
forever; live entries expire after `orders_ttl` seconds (default 5, `0`
disables live caching). The cache is only written from observed answers: cancel
and amend invalidate, they never write an assumed status.

```python
# Cache-backed by client_oid: terminal orders are cached forever, live ones
# for orders_ttl seconds. ignore_cache=True queries the exchange.
order = await account.get_order(client_order_id=client_id, ignore_cache=True)

# Poll to a status. Confirmed-absent keeps the wait going; only the deadline
# ends it, with an indeterminate error.
order = await account.wait_for_order(
    (cro.OrderStatus.FILLED, cro.OrderStatus.CANCELED),
    client_order_id=client_id,
    timeout=5.0,
)

# Cancel, then poll to a terminal status. Returns the terminal order, or None
# when the exchange confirms the order is gone.
try:
    order = await account.cancel_order_and_wait(pair, client_id, timeout=5.0)
except exceptions.CancelNotConfirmedError:
    await reconcile_later(client_id)  # cancel may still land: reconcile
else:
    print("terminal:", order.status if order else "absent")
```

A websocket feed can answer lookups directly: `updates` wins over cache and
API, and populates the cache:

```python
# A websocket snapshot beats cache and API, and populates the cache.
order = await account.get_order(client_order_id=client_id, updates={client_id: snapshot})
```

Two guards worth knowing:

- A `client_oid` created moments ago that reads back empty raises an
  indeterminate `ApiError`, not `OrderNotFoundError`, for `create_race_guard`
  seconds (default 2). Absence right after create is not proof of absence.
- `wait_for_order` raises `exceptions.WaitNotConfirmedError` (indeterminate) on
  timeout instead of returning `None`. `wait_for_status` is deprecated in its
  favor.

### Order book

`OrderBook` normalizes both sides to best-first in `__post_init__`, regardless
of the order the caller or the API provides: `buys` by price descending,
`sells` by price ascending. Use the properties; an empty book raises
`ValueError`.

```python
import cryptocom.exchange as cro
from cryptocom.exchange.structs import OrderBook, OrderInBook

pair = cro.pairs.CRO_USD
book = OrderBook(
    buys=[
        OrderInBook(0.150, 100, 0, pair, cro.OrderSide.BUY),
        OrderInBook(0.152, 100, 0, pair, cro.OrderSide.BUY),
    ],
    sells=[
        OrderInBook(0.155, 100, 0, pair, cro.OrderSide.SELL),
        OrderInBook(0.153, 100, 0, pair, cro.OrderSide.SELL),
    ],
    pair=pair,
)
assert book.best_bid.price == 0.152  # buys: price DESC
assert book.best_ask.price == 0.153  # sells: price ASC
print(book.mid, book.spread)
```

Snapshots and streams share the type:

```python
book = await market.get_orderbook(pair)
print(book.best_bid.price, book.best_ask.price, book.mid, book.spread)
```

### Instruments and balances

Instrument identity is `exchange_name`: `__eq__`/`__hash__` are defined on it
for `Instrument` and `InstrumentBalance`, so the two interoperate as dict
keys and `get_balance()` is keyed by plain `Instrument`s.

```python
balance = await account.get_balance()  # dict[Instrument, InstrumentBalance]
usd = balance[cro.instruments.USD]  # keys are plain Instruments

snapshot = await anext(account.listen_balances())  # a structs.Balance
snapshot.get("USD") is snapshot.get(cro.instruments.USD)  # str, Instrument
```

Scope note: `get_orders_history()` and `get_balance_history()` work with trade
API keys; `get_deposit_history()` and `get_withdrawal_history()` are
wallet/custody-side and answer HTTP 401 `USER_NOT_FOUND` for trade keys.

```python
orders = await account.get_orders_history(pair)
balances = await account.get_balance_history()
```

### Testing

The suite replays recorded exchange responses and never opens a socket, so CI
is deterministic and offline (it passes with no network and no keys).

- Captures live in `tests/captured/<test_file>/<test_name>.json`, keyed by
  `method path` plus sorted request arguments, and consumed in order.
  13-digit epoch-millis are normalized to `<ts>` so time windows match, and
  auto-generated `client_oid`s are recorded under `"__uuids__"` and replayed in
  sequence.
- Replay is strict: a miss raises `ApiError` listing the arguments that were
  captured. There is no silent live fallback, so a passing CI run cannot drift
  from reality unnoticed. Code that changes arguments, call order, or the
  number of generated client ids must be re-recorded.
- Re-record with a funded account (this spends real money):

    ```bash
    API_CAPTURE=true CRYPTOCOM_API_KEY=*** CRYPTOCOM_API_SECRET=*** \
      poetry run pytest tests/test_account.py
    ```

  then commit the regenerated capture files.
- Write a live test as an ordinary test using the `api`, `market` and
  `account` fixtures in `tests/conftest.py`. The `account` fixture rebalances
  USD/CRO 50/50 on the feeless `CRO_USD` pair and cancels its open orders on
  teardown; size orders from pair rules via `tests/helpers.py`
  (`min_order_quantity`, `resting_buy_price`, `resting_sell_price`) instead of
  magic numbers, and assert on shapes rather than exchange-side values so the
  capture replays.
- Transport behavior (retry accounting, status routing, taxonomy) is tested
  offline by overriding `ApiProvider._http_request()`, the single outbound HTTP
  call — see `tests/test_api_request.py`.
- CI command: `poetry run pytest -v --cov . --cov-report xml:coverage.xml
  --cov-fail-under=90`.

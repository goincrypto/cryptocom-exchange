# Python 3.7+ async library for crypto.com/exchange API using httpx and websockets

[![Docs Build Status](https://readthedocs.org/projects/cryptocom-exchange/badge/?version=latest&style=flat)](https://readthedocs.org/projects/cryptocom-exchange)
![Test workflow](https://github.com/goincrypto/cryptocom-exchange/actions/workflows/test.yml/badge.svg)
[![Maintainability](https://api.codeclimate.com/v1/badges/8d7ffdae54f3c6e86b5a/maintainability)](https://codeclimate.com/github/goincrypto/cryptocom-exchange/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/8d7ffdae54f3c6e86b5a/test_coverage)](https://codeclimate.com/github/goincrypto/cryptocom-exchange/test_coverage)
[![PyPI implementation](https://img.shields.io/pypi/implementation/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI license](https://img.shields.io/pypi/l/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI version fury.io](https://badge.fury.io/py/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI download month](https://img.shields.io/pypi/dm/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![Gitter](https://badges.gitter.im/goincrypto/cryptocom-exchange.svg)](https://gitter.im/goincrypto/cryptocom-exchange?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

Documentation: [https://cryptocom-exchange.rtfd.io](https://cryptocom-exchange.rtfd.io)

Exchange original API docs: [https://exchange-docs.crypto.com](https://exchange-docs.crypto.com)

### **WARNING: PLEASE use 0.10.3+ [prev versions have private websocket broken and memory leaks]

### Description

`pip install cryptocom-exchange`

- provides all methods to access crypto.com/exchange API (except for websockets temporary)
- full test coverage on real exchange with real money
- simple async methods with custom retries and timeouts

**Please do not use secret keys, they used only for test purposes**

### Changelog

- **0.10.4** - Updated pairs
- **0.10.3** - fixed websocket private endpoints not returning data
- **0.10.2** - fixed huge memory leak by `httpx`
- [leaks memory] **0.10.1** - added read timeouts for websockets, fixed test with tickers
- [leaks memory] **0.10.0** - moved into httpx + websockets, added autoreconnect, simplified code, improved stability
- **0.9.5** - added timeout for websocket if no data received in 3 mins we trying to reconnect
- **0.9.4** - fixed spread func, fixed missing params
- **0.9.3** - added RPS limiter by @Irishery
- **0.9.2** - fixed event loop import level
- **0.9.1** - fixed Windows bug with asyncio event loop
- **0.9.0** - updated coins, refactored wallet transactions
- **0.8.1** - fixed coin name generation
- **0.8** - fixed tests with updated coins
- **0.7.12** - updated coins, added websocket timeouts
- **0.7.11** - fixed orders history if empty
- **0.7.10** - updated pairs precision
- **0.7.9** - fixed price and quantity rounding, updated pairs and coins
- **0.7.8** - changed keys, removed depth from orderbook (not working, always 150), updated pairs
- **0.7.7** - updated pairs by JOB, fixed timeout
- **0.7.6** - updated pairs
- **0.7.5** - fixed `order.remaining_quantity` rounding
- **0.7.4** - fixed sync pairs for account
- **0.7.3** - fixed price of order if not filled, updated coins, added missing trades to `Order`
- **0.7.2** - fixed `listen_orders` private account method, added test
- **0.7.1** - fixed missing '.0' in order price and quantity (different in py3.7, py3.9)
- **0.7** - major changes, `Pair` -> `cro.pairs.CRO_USDT` moved to more complex structure so we can use round and server information about pairs.
    - If you have errors, just use `await account.sync_pairs()` or `await exchange.sync_pairs()`
    - Added rounding per pair, all floats will be with right precisions
- **0.6** - included changes from PR kudos to https://github.com/samueltayishere, fixed limit orders, fixed timeouts, fixed is_active order status
- **0.5.1** - added symbols YFI, BAND, fixed test with limit orders
- **0.5** - missing symbols MKR, UNI, possible refactoring for simple objects
- **0.4.5** - fixed missing CELR balances
- **0.4.4** - fixed missing QTUM, CELR coins
- **0.4.3** - fixed missing `fees_coin` Coin enum
- **0.4.2** - fixed supported pairs OMG and MANA
- **0.4.1** - fixed `cached_property` for python 3.7
- **0.4.0** - added `OrderForceType` and `OrderExecType`, refactored `Order` responses, splited private and market methods, added missing `Pair` and `Coin`, added `Balance` dataclass, public
keys for tests passing
- **0.3.4** - fixed balances listener, fixed pairs
- **0.3.3** - fixed orderbook depth
- **0.3.2** - added orderbook websocket method
- **0.3.1** - fixed missing DAI pair
- **0.3** - added websocket support for public endpoints and supports `sign=True` for private endpoints
- **0.2.1** - fixed order_id in `get_order` func, still preparing for stable release
- **0.2** - moved to new API v2, except for websockets

# Python 3.7+ library for crypto.com/exchange API using asyncio and aiohttp 

[![Docs Build Status](https://readthedocs.org/projects/cryptocom-exchange/badge/?version=latest&style=flat)](https://readthedocs.org/projects/cryptocom-exchange)
[![Build Status](https://travis-ci.org/goincrypto/cryptocom-exchange.svg?branch=master)](https://travis-ci.org/goincrypto/cryptocom-exchange)
[![Maintainability](https://api.codeclimate.com/v1/badges/8d7ffdae54f3c6e86b5a/maintainability)](https://codeclimate.com/github/goincrypto/cryptocom-exchange/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/8d7ffdae54f3c6e86b5a/test_coverage)](https://codeclimate.com/github/goincrypto/cryptocom-exchange/test_coverage)
[![Requirements Status](https://requires.io/github/goincrypto/cryptocom-exchange/requirements.svg?branch=master)](https://requires.io/github/goincrypto/cryptocom-exchange/requirements/?branch=master)
[![PyPI implementation](https://img.shields.io/pypi/implementation/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI license](https://img.shields.io/pypi/l/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI version fury.io](https://badge.fury.io/py/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![PyPI download month](https://img.shields.io/pypi/dm/cryptocom-exchange.svg)](https://pypi.python.org/pypi/cryptocom-exchange/)
[![Gitter](https://badges.gitter.im/goincrypto/cryptocom-exchange.svg)](https://gitter.im/goincrypto/cryptocom-exchange?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

Documentation: [https://cryptocom-exchange.rtfd.io](https://cryptocom-exchange.rtfd.io)

Exchange original API docs: [https://exchange-docs.crypto.com](https://exchange-docs.crypto.com)

### Description

`pip install cryptocom-exchange`

- provides all methods to access crypto.com/exchange API (except for websockets temporary)
- full test coverage on real exchange with real money
- simple async methods with custom retries and timeouts

**Please do not use secret keys, they used only for test purposes**

### Changelog

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

### Donation

If this lib helped you achieve profits will be glad to receive some donation to continue support 💪

ERC20(CRO,USDT,ETH etc.): **0x348c268A563b0C809e4E21F4371E8cdFbD1f51bf**

BTC: **3NxnzUbTDFrwCEChS4PMqXbxvESxkfU2UP**

LTC: **MK3DtnQaMs2eSDdTygF618xdQd7Q9y7Nr2**

NEO: **AdTApXpKjVh2YJUKuEHuWvoSdaSAzLakFF**


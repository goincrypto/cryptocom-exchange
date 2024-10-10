## Python 3.9+ async library for crypto.com/exchange API using httpx and websockets

[![Docs Build Status](https://readthedocs.org/projects/cryptocom-exchange/badge/?version=latest&style=flat)](https://readthedocs.org/projects/cryptocom-exchange)
![Test workflow](https://github.com/goincrypto/cryptocom-exchange/actions/workflows/test_release.yml/badge.svg)
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

### Description

`pip install cryptocom-exchange` or `poetry add cryptocom-exchange`

- fully operational v1 exchange API, improved testing with replay mechanics
- provides all methods to access crypto.com/exchange API including websockets
- *important*: temporary disabled tests for withdrawals (soon)
- full test coverage on real exchange with real money
- simple async methods with custom retries and timeouts

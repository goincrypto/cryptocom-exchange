.. cryptocom-exchange documentation master file
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. toctree::
    :hidden:
    :maxdepth: 3
    :caption: Contents:

    Home <self>
    api

Welcome to cryptocom-exchange documentation!
============================================
This package provides interfaces to access a https://crypto.com/exchange API.
Supports only **Python 3.7+** versions.
You can find tests with examples of trading and exchange data usage at
`github <https://github.com/goincrypto/cryptocom-exchange/tree/master/tests>`_.
Full reference you can find in the API section.

Quick-start
===========

Create virtual environment, activate, install

.. code-block:: bash

    python3 -m venv venv
    source venv/bin/activate
    pip3 install cryptocom-exchange

Userful examples
================

- Get historical data

.. testcode::

    import asyncio
    import cryptocom.exchange as cro

    async def main():
        exchange = cro.Exchange()
        candles = await exchange.get_candles(cro.Symbol.CROUSDT)
        avg_price = 0
        for candle in candles:
            avg_price += (candle.open + candle.close) / 2
        avg_price /= len(candles)

    asyncio.run(main())

- Watch latest candles live

- Get orderbook

- Buy or Sell with LIMIT or MARKET orders

- Get trades and orders

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

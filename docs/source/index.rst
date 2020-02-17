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

- Get historical price data

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
        print(f'Avg price {round(avg_price, 4)} for {len(candles)} days')

    asyncio.run(main())

.. testoutput::
    :hide:

    ...

- Listen latest candles live as they go (Websocket)

.. testcode::

    import asyncio
    import cryptocom.exchange as cro

    async def main():
        exchange = cro.Exchange()
        # NOTE: do not "break" if you need forever watch for new candles
        async for candle in exchange.listen_candles(cro.Symbol.CROUSDT):
            ohlc4 = candle.open + candle.high + candle.low + candle.close
            ohlc4 /= 4
            print(f'OHLC / 4 of last candle {ohlc4}')
            break

        # NOTE: wait to close background tasks, used only in docs
        # you can delete this in your code in real file
        await asyncio.sleep(1)

    asyncio.run(main())

.. testoutput::
    :hide:

    ...

- Get account balance. You can provide env vars for auth keys.

.. code-block:: bash

    export CRYPTOCOM_API_KEY="***"
    export CRYPTOCOM_API_SECRET="***"

    python3 mybot.py

or by providing attributes to :code:`Account(api_key='***', api_secret='***')`

.. testcode::

    import asyncio
    import cryptocom.exchange as cro

    async def main():
        account = cro.Account(from_env=True)
        data = await account.get_balance()
        print(f'Account balance {data}')

    asyncio.run(main())

.. testoutput::
    :hide:

    ...

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

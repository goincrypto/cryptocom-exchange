.. cryptocom-exchange documentation master file
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. toctree::
    :hidden:
    :maxdepth: 3
    :caption: Contents:

    Home <self>
    install
    guide
    api

Welcome to cryptocom-exchange documentation!
============================================
Get started with "Installation" and then get an overview with the User's guide with helpful examples. Also you can find tests with examples of trading and exchange data usage.
Full reference you can find in the API section. cryptocom-exchange depends on the aiohttp the documentation for this library can be found at: "link".

Quick-start
===========

- python3 -m venv venv (create virutalenv)
- source venv/bin/activate
- pip3 install cryptocom-exchange

- create simple file hello_crypto.py with contents

.. testcode::

    import asyncio
    import cryptocom.exchange as cro

    async def main():
        exchange = cro.Exchange()
        candles = [
            candle async for candle in exchange.get_candles(cro.Symbol.CROUSDT)
        ]
        assert len(candles) > 30

    asyncio.run(main())

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

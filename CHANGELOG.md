# Changelog

<!--next-version-placeholder-->

## v0.12.0 (2022-10-17)
### Feature
* Improved ssl error handling or empty data ([`da62f47`](https://github.com/goincrypto/cryptocom-exchange/commit/da62f47cb53d14b52176e5207519b6a1c1e1a8fc))

## v0.11.18 (2022-10-17)
### Fix
* Updated to use python 3.10.7 ([`b639d4d`](https://github.com/goincrypto/cryptocom-exchange/commit/b639d4d8a0b6ac5dab52015e3a97315dd88a9d50))

## v0.11.17 (2022-10-17)
### Fix
* [ci] update actions python version ([`a7db870`](https://github.com/goincrypto/cryptocom-exchange/commit/a7db870c80791e9e08fe72f3df8ccf9253629bfa))
* [ci] updated matrix config ([`59900b6`](https://github.com/goincrypto/cryptocom-exchange/commit/59900b6502896a0dc5f985f45ca962f422acba8f))

### Sync
* Updated API pairs and coins ([`41ca92a`](https://github.com/goincrypto/cryptocom-exchange/commit/41ca92ad8ae16925ef87b0a0717aa0e0c255dcd0))

## v0.11.16 (2022-06-21)
### Fix
* Missing pairs available with default precision ([`7cb325b`](https://github.com/goincrypto/cryptocom-exchange/commit/7cb325b5914ac8b89092f27d8a98eace94809d22))

## v0.11.15 (2022-06-11)
### Sync
* Updated API pairs and coins ([`d36762e`](https://github.com/goincrypto/cryptocom-exchange/commit/d36762eb79c33972603d332473797ac4cfe815fa))

## v0.11.14 (2022-06-06)
### Sync
* Updated API pairs and coins ([`91650c5`](https://github.com/goincrypto/cryptocom-exchange/commit/91650c5dbce978c59e01a0a4fb2a89f3ed4303fc))

## v0.11.13 (2022-06-02)
### Fix
* Updated httpx to 0.23 ([`ff655bd`](https://github.com/goincrypto/cryptocom-exchange/commit/ff655bd6fc5e9b11f7a05a0c9d3e4beb306d4553))

### Sync
* Updated API pairs and coins ([`2f2c264`](https://github.com/goincrypto/cryptocom-exchange/commit/2f2c264c79702350493a4447fec9b107e92787b7))

## v0.11.12 (2022-05-31)
### Sync
* Updated API pairs and coins ([`a94fe89`](https://github.com/goincrypto/cryptocom-exchange/commit/a94fe89aa0cdee349c3dd52f53ca1947ba77e088))

## v0.11.11 (2022-05-31)
### Sync
* Updated API pairs and coins ([`79218e3`](https://github.com/goincrypto/cryptocom-exchange/commit/79218e342086115b1e59b156f1e615d2b1ecddb7))

## v0.11.10 (2022-05-30)
### Sync
* Updated API pairs and coins ([`0acf2c0`](https://github.com/goincrypto/cryptocom-exchange/commit/0acf2c00f0daca72f34b71a50da8414223734520))

## v0.11.9 (2022-05-30)
### Sync
* Updated API pairs and coins ([`8094a74`](https://github.com/goincrypto/cryptocom-exchange/commit/8094a74abd3c3ee3011949a00dc93f9918625124))

## v0.11.8 (2022-05-26)
### Sync
* Updated API pairs and coins ([`233ca6a`](https://github.com/goincrypto/cryptocom-exchange/commit/233ca6aa3c4d2b2883dc9da1322c53bdbf844bc8))
* Updated API pairs and coins ([`de6e5f1`](https://github.com/goincrypto/cryptocom-exchange/commit/de6e5f1b0d6f089a0ba831fed135dee6b7a1bb97))

## v0.11.7 (2022-05-25)
### Sync
* Updated API pairs and coins ([`1b97049`](https://github.com/goincrypto/cryptocom-exchange/commit/1b97049c8a51e19bc63508be3f277200a6112fc4))

## v0.11.6 (2022-05-24)
### Sync
* Updated API pairs and coins ([`8cdb883`](https://github.com/goincrypto/cryptocom-exchange/commit/8cdb883fee716bc137636065d32b7c59ad864c1f))

## v0.11.5 (2022-05-23)
### Fix
* Updated exception handling for requests ([`4e52199`](https://github.com/goincrypto/cryptocom-exchange/commit/4e52199a9f471c7880f855a26bf7cf7466be6148))

### Sync
* Updated API pairs and coins ([`12d0c25`](https://github.com/goincrypto/cryptocom-exchange/commit/12d0c250a0749cad92c58926b1a8ab22067cc506))

## v0.11.4 (2022-05-20)
### Sync
* Updated API pairs and coins ([`a42f4e4`](https://github.com/goincrypto/cryptocom-exchange/commit/a42f4e4501da11e8e79f890b0b69966741777a1a))

## v0.11.3 (2022-05-19)


## v0.11.2 (2022-05-18)
### Fix
* Added retries for connection error ([`57dbc19`](https://github.com/goincrypto/cryptocom-exchange/commit/57dbc19f8d2e558bafa6a0aabf7b39e3d005e0bb))

## v0.11.1 (2022-05-17)


## v0.11.0 (2022-05-15)
### Feature
* Updated CI ([`89b4b8f`](https://github.com/goincrypto/cryptocom-exchange/commit/89b4b8fedfff8b74fed4d72a35a0f25c319680aa))

## Old Changelog
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

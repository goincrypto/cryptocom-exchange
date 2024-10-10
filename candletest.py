import asyncio

import cryptocom.exchange as cro


async def main():
    exchange = cro.Exchange()
    pair = cro.pairs.BEAT_USD
    candles = await exchange.get_candles(pair, cro.Period.MINS)

    balance = 1000
    instrument_balance = 0
    max_price = 0.005
    min_price = 0.002
    comission = 0.0002
    size = 100
    step = (max_price - min_price) / size
    volume = balance / size
    orders = {}
    take_profit = original_take_profit = 0.01
    old_candle = None

    # under sma not sell if bought
    # sell only on upside of sma and not buy

    for num in range(1, 100):
        orders[round(min_price + step * num, 4)] = None

    for index, candle in enumerate(candles):
        # print(candle)
        if old_candle and old_candle.close > old_candle.open:
            take_profit = max(
                old_candle.high / old_candle.low - 1, original_take_profit
            )
        for price in orders:
            if orders[price] is None:
                if candle.open <= price <= candle.close:
                    quantity = round(volume / price * (1 - comission), 4)
                    orders[price] = {"is_buy": True, "quantity": quantity}
                    balance -= volume
                    instrument_balance += quantity
            elif orders[price]["is_buy"] and candle.high > price * (1 + take_profit):
                quantity = orders[price]["quantity"]
                # print('sell at', price, price * (1 + take_profit))
                sell_volume = round(
                    quantity * price * (1 + take_profit) * (1 - comission), 6
                )
                # print('sell volume', quantity, sell_volume, (quantity * price))
                balance += sell_volume
                instrument_balance -= quantity
                orders[price] = None
                print("profit", (sell_volume / (quantity * price) - 1) * 100)

        old_candle = candle
        # what grid items is filled
        # check each grid order if it's there
        # if it's above the price sell if it's available to sell
        # fill orders based on high, low of the day
        # print({k: v for k, v in orders.items() if v})
    print(
        "USD",
        balance,
        pair,
        instrument_balance,
        "TOTAL",
        balance + instrument_balance * candle.close,
    )

    # if index > 160:
    #     break

    # for candle in candles:


if __name__ == "__main__":
    asyncio.run(main())

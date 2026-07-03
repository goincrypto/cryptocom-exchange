import asyncio
from pathlib import Path

from cryptocom import exchange as cro

ALL_TEMPLATE = """
def all():
    return [
        value
        for name, value in globals().items()
        if isinstance(value, {})
    ]
"""

SRC_PATH = Path(__file__).parent / "src" / "cryptocom" / "exchange"


async def main():
    exchange = cro.Exchange()
    await exchange.sync_pairs()

    # Fetch risk parameters to get min/max order notional per instrument
    risk_params = await exchange.get_risk_parameters()
    order_limits = {}
    for config in risk_params.get("base_currency_config", []):
        instrument_name = config.get("instrument_name")
        if instrument_name:
            order_limits[instrument_name] = {
                "min_order_notional_usd": config.get(
                    "min_order_notional_usd", 1.0
                ),
                "max_order_notional_usd": config.get(
                    "max_order_notional_usd", 1000000.0
                ),
            }

    instruments = set()
    pairs = await exchange.get_pairs()
    for pair in pairs:
        instruments.add(pair.base_instrument)
        instruments.add(pair.quote_instrument)

    instruments = sorted(instruments, key=lambda c: c.exchange_name)

    with (SRC_PATH / "pairs.py").open("w") as f:
        f.writelines(
            [
                "from .structs import Pair\n\n",
            ]
            + [
                f'{pair.name} = Pair("{pair.exchange_name}", '
                f"price_precision={pair.price_precision}, "
                f"quantity_precision={pair.quantity_precision}, "
                f"min_order_notional_usd={order_limits.get(pair.quote_instrument.exchange_name, {}).get('min_order_notional_usd', 1.0)}, "
                f"max_order_notional_usd={order_limits.get(pair.quote_instrument.exchange_name, {}).get('max_order_notional_usd', 1000000.0)})\n"
                for pair in sorted(pairs, key=lambda p: p.name)
            ]
            + ["\n", ALL_TEMPLATE.format("Pair")]
        )

    with (SRC_PATH / "instruments.py").open("w") as f:
        f.writelines(
            [
                "from .structs import Instrument\n\n",
            ]
            + [
                f'{instrument.name} = Instrument("{instrument.exchange_name}")\n'
                for instrument in instruments
            ]
            + ["\n", ALL_TEMPLATE.format("Instrument")]
        )

    print(f"Generated {len(pairs)} pairs and {len(instruments)} instruments")
    print(f"Order limits loaded for {len(order_limits)} instruments")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from pathlib import Path

from cryptocom import exchange as cro
from cryptocom.exchange.structs import BaseCurrencyConfig

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
    order_limits = {
        config.instrument_name: config for config in risk_params.base_currency_config
    }

    def get_config(instrument_name: str) -> BaseCurrencyConfig:
        return order_limits.get(instrument_name) or BaseCurrencyConfig(
            instrument_name=instrument_name
        )

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
                f"min_order_notional_usd={get_config(pair.quote_instrument.exchange_name).min_order_notional_usd}, "
                f"max_order_notional_usd={get_config(pair.quote_instrument.exchange_name).max_order_notional_usd})\n"
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

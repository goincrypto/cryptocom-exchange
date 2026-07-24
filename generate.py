import asyncio
from pathlib import Path

from cryptocom import exchange as cro
from cryptocom.exchange.structs import BaseCurrencyConfig

SRC_PATH = Path(__file__).parent / "src" / "cryptocom" / "exchange"


async def main():
    exchange = cro.Exchange()
    await exchange.sync_pairs()

    # Clear old generated files to avoid stale data
    pairs_file = SRC_PATH / "pairs.py"
    instruments_file = SRC_PATH / "instruments.py"
    if pairs_file.exists():
        pairs_file.unlink()
    if instruments_file.exists():
        instruments_file.unlink()

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
            ["from .structs import Pair, InstrumentType, Instrument\n\n"]
            + [
                f'{pair.name} = Pair("{pair.exchange_name}", '
                f"price_precision={pair.price_precision}, "
                f"quantity_precision={pair.quantity_precision}, "
                f"inst_type=InstrumentType.{pair.inst_type.name if pair.inst_type else None}, "
                f'display_name="{pair.display_name or ""}", '
                f'base_currency=Instrument("{pair.base_currency.exchange_name if pair.base_currency else ""}"), '
                f'quote_currency=Instrument("{pair.quote_currency.exchange_name if pair.quote_currency else ""}"), '
                f"quantity_tick_size={pair.quantity_tick_size}, "
                f"price_tick_size={pair.price_tick_size}, "
                f"min_order_quantity={pair.min_order_quantity}, "
                f"max_order_quantity={pair.max_order_quantity}, "
                f"maker_fee_rate={pair.maker_fee_rate}, "
                f"taker_fee_rate={pair.taker_fee_rate}, "
                f"min_order_notional_usd={get_config(pair.quote_instrument.exchange_name).min_order_notional_usd}, "
                f"max_order_notional_usd={get_config(pair.quote_instrument.exchange_name).max_order_notional_usd})\n"
                for pair in sorted(pairs, key=lambda p: p.name)
            ]
            + ["\n", "\ndef all() -> list[Pair]:\n", "    return Pair.all()\n"]
        )

    with (SRC_PATH / "instruments.py").open("w") as f:
        f.writelines(
            ["from .structs import Instrument\n\n"]
            + [
                f'{instrument.name} = Instrument("{instrument.exchange_name}")\n'
                for instrument in instruments
            ]
            + [
                "\n",
                "\ndef all() -> list[Instrument]:\n",
                "    return Instrument.all()\n",
            ]
        )

    print(f"Generated {len(pairs)} pairs and {len(instruments)} instruments")
    print(f"Order limits loaded for {len(order_limits)} instruments")


if __name__ == "__main__":
    asyncio.run(main())

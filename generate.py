#!/usr/bin/env python3
"""Generate pairs.py and instruments.py from API.

This script is independent and will blank out the generated files before regenerating.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
SRC_PATH = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_PATH))


def cleanup_generated_files():
    """Blank out generated files to prevent import errors during regeneration."""
    pairs_file = SRC_PATH / "cryptocom" / "exchange" / "pairs.py"
    instruments_file = SRC_PATH / "cryptocom" / "exchange" / "instruments.py"

    # Write empty stubs with all() function to prevent import errors
    with pairs_file.open("w") as f:
        f.write("# Auto-generated file - will be overwritten\n")
        f.write("def all() -> list: return []\n")

    with instruments_file.open("w") as f:
        f.write("# Auto-generated file - will be overwritten\n")
        f.write("def all() -> list: return []\n")

    print("✓ Cleaned up generated files")


async def main():
    # Step 1: Cleanup - blank out files to prevent crashes (BEFORE imports!)
    cleanup_generated_files()

    # Now import after cleanup - this is safe
    from cryptocom.exchange.structs import BaseCurrencyConfig
    from cryptocom.exchange.market import Market

    # Step 2: Initialize market and sync pairs
    market = Market()
    await market.sync_pairs()
    print("✓ Synced pairs from API")

    # Step 3: Fetch risk parameters for order limits
    risk_params = await market.get_risk_parameters()
    order_limits = {
        config.instrument_name: config for config in risk_params.base_currency_config
    }

    def get_config(instrument_name: str) -> BaseCurrencyConfig:
        return order_limits.get(instrument_name) or BaseCurrencyConfig(
            instrument_name=instrument_name
        )

    # Step 4: Collect all instruments
    pairs = await market.get_pairs()
    instruments = set()
    for pair in pairs:
        instruments.add(pair.base_instrument)
        instruments.add(pair.quote_instrument)

    instruments = sorted(instruments, key=lambda c: c.exchange_name)

    # Step 5: Generate pairs.py
    with (SRC_PATH / "cryptocom" / "exchange" / "pairs.py").open("w") as f:
        f.write("from .structs import Pair, InstrumentType, Instrument\n\n")
        for pair in sorted(pairs, key=lambda p: p.name):
            config = get_config(pair.quote_instrument.exchange_name)
            f.write(
                f"{pair.name} = Pair("
                f'exchange_name="{pair.exchange_name}", '
                f"price_precision={pair.price_precision}, "
                f"quantity_precision={pair.quantity_precision}, "
                f"inst_type=InstrumentType.{pair.inst_type.name}, "
                f'display_name="{pair.display_name or pair.exchange_name}", '
                f'base_currency=Instrument("{pair.base_currency.exchange_name}"), '
                f'quote_currency=Instrument("{pair.quote_currency.exchange_name}"), '
                f"quantity_tick_size={pair.quantity_tick_size}, "
                f"price_tick_size={pair.price_tick_size}, "
                f"min_order_quantity={pair.min_order_quantity}, "
                f"max_order_quantity={pair.max_order_quantity}, "
                f"min_order_notional_usd={config.min_order_notional_usd}, "
                f"max_order_notional_usd={config.max_order_notional_usd})\n"
            )
        f.write("\n")
        f.write("def all() -> list[Pair]:\n")
        f.write("    return Pair.all()\n")

    # Step 6: Generate instruments.py
    with (SRC_PATH / "cryptocom" / "exchange" / "instruments.py").open("w") as f:
        f.write("from .structs import Instrument\n\n")
        for instrument in instruments:
            f.write(f'{instrument.name} = Instrument("{instrument.exchange_name}")\n')
        f.write("\n")
        f.write("def all() -> list[Instrument]:\n")
        f.write("    return Instrument.all()\n")

    print(f"✓ Generated {len(pairs)} pairs and {len(instruments)} instruments")
    print(f"✓ Order limits loaded for {len(order_limits)} instruments")
    print("✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())

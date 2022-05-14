import asyncio
from pathlib import Path

from cryptocom import exchange as cro

ALL_TEMPLATE = """
def all():
    return [
        value for name, value in globals().items() if isinstance(value, {})
    ]
"""

SRC_PATH = Path(__file__).parent / "src" / "cryptocom" / "exchange"


async def main():
    exchange = cro.Exchange()
    account = cro.Account(from_env=True)
    coins = (await account.get_balance()).keys()
    pairs = await exchange.get_pairs()

    with (SRC_PATH / "pairs.py").open("w") as f:
        f.writelines(
            [
                "from .structs import Pair\n\n",
            ]
            + [
                f'{pair.name} = Pair("{pair.exchange_name}", '
                f"price_precision={pair.price_precision}, "
                f"quantity_precision={pair.quantity_precision})\n"
                for pair in sorted(pairs, key=lambda p: p.name)
            ]
            + ["\n", ALL_TEMPLATE.format("Pair")]
        )

    with (SRC_PATH / "coins.py").open("w") as f:
        f.writelines(
            [
                "from .structs import Coin\n\n",
            ]
            + [
                f'{coin.name} = Coin("{coin.exchange_name}")\n'
                for coin in sorted(coins, key=lambda c: c.name)
            ]
            + ["\n", ALL_TEMPLATE.format("Coin")]
        )


if __name__ == "__main__":
    asyncio.run(main())

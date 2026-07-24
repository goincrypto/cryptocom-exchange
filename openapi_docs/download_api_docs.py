#!/usr/bin/env python3
"""
Download all Crypto.com Exchange API documentation YAML files.

Based on the pattern: https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/{endpoint}.yaml
and https://exchange-developer.crypto.com/exchange/v1/docs/api/public/{endpoint}.yaml
"""

import asyncio
from pathlib import Path
from httpx import AsyncClient

BASE_URL_REST = "https://exchange-developer.crypto.com/exchange/v1/docs/api/rest"
BASE_URL_PUBLIC = "https://exchange-developer.crypto.com/exchange/v1/docs/api/public"
OUTPUT_DIR = Path("specs")

# Base endpoints to discover links from
DISCOVERY_PAGES = [
    "trading",
    "account-balance-and-positions",
    "transaction-history",
    "advanced-order-management",
    "crypto-wallet",
    "fiat-wallet",
    "staking",
    "otc-rfq-for-taker",
    "reference-and-market-data",
    "trading-bot-api",
]


async def download_endpoint(
    client: AsyncClient, base_url: str, endpoint: str
) -> tuple[str | None, str | None]:
    """Download a single YAML endpoint. Returns (endpoint, content or error)."""
    url = f"{base_url}/{endpoint}.yaml"
    try:
        response = await client.get(url, timeout=10.0)
        if response.status_code == 200:
            return endpoint, response.text
        else:
            return endpoint, f"HTTP {response.status_code}"
    except Exception as e:
        return endpoint, str(e)


async def discover_endpoints(client: AsyncClient) -> set[str]:
    """Discover all endpoints by scraping HTML pages."""
    endpoints = set()

    print("Discovering endpoints from documentation pages...")
    for page in DISCOVERY_PAGES:
        url = f"{BASE_URL_REST}/{page}"
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                # Extract endpoint links
                import re

                matches = re.findall(
                    r'/exchange/v1/docs/api/rest/([^"]+)', response.text
                )
                for match in matches:
                    if not match.startswith("http") and "." not in match:
                        endpoints.add(match)
                print(f"  Found {len(matches)} links in {page}")
        except Exception as e:
            print(f"  Failed to scrape {page}: {e}")

    return endpoints


async def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    async with AsyncClient() as client:
        # First, discover all endpoints
        endpoints = await discover_endpoints(client)
        endpoints.discard("")  # Remove empty strings

        print(f"\nDiscovered {len(endpoints)} endpoints:")
        for ep in sorted(endpoints):
            print(f"  - {ep}")

        print(f"\nDownloading YAML files from {BASE_URL_REST}...")

        tasks = []
        for endpoint in endpoints:
            tasks.append(download_endpoint(client, BASE_URL_REST, endpoint))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        downloaded = 0
        failed = 0
        skipped = 0

        for endpoint, result in results:
            if isinstance(result, Exception):
                print(f"❌ {endpoint}.yaml: {result}")
                failed += 1
            elif result.startswith("HTTP"):
                print(f"⚠️  {endpoint}.yaml: {result}")
                skipped += 1
            elif "Access Denied" in result or "<Error>" in result:
                print(f"🚫 {endpoint}.yaml: Access Denied")
                skipped += 1
            else:
                filename = f"{endpoint}.yaml"
                filepath = OUTPUT_DIR / filename
                filepath.write_text(result)
                print(f"✅ {filename}")
                downloaded += 1

        print(f"\n{'=' * 60}")
        print(f"Downloaded: {downloaded}")
        print(f"Skipped/Failed: {failed + skipped}")
        print(f"Output directory: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())

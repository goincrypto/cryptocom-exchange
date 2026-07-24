# Crypto.com Exchange API Documentation

This directory contains OpenAPI 3.0 specifications for all Crypto.com Exchange API endpoints, downloaded from the official documentation.

## Downloaded Files

- **101 YAML files** covering REST API endpoints
- Organized by endpoint name in `specs/` folder
- Base URL: https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/

## How to Use

### 1. Browse Endpoints
Each YAML file contains:
- Request/response schema definitions
- Example requests
- Parameters and validation rules
- Code samples (JavaScript/Python)

### 2. Quick Reference

```bash
# View available endpoints
ls specs/*.yaml | head -20

# Search for specific endpoint
grep -l "create-order" specs/*.yaml

# Extract request parameters from an endpoint
python -c "import yaml; print(yaml.safe_load(open('specs/private-create-order.yaml'))['components']['schemas'].keys())"
```

### 3. Regenerate Documentation
```bash
cd openapi_docs
poetry run python download_api_docs.py
```

## Endpoint Categories

### Trading & Order Management
- `private-create-order` - Submit new orders
- `private-amend-order` - Modify existing orders
- `private-cancel-order` - Cancel single order
- `private-get-order-detail` - Get order details
- `private-get-open-orders` - List active orders
- `private-get-order-history` - Historical orders

### Advanced Orders (OCO, OTO, OTOCO)
- `private-advanced-create-order` - Create advanced orders
- `private-advanced-create-oco` - One-Cancels-the-Other
- `private-advanced-create-oto` - One-Triggers-the-Other
- `private-advanced-create-otoco` - One-Triggers-a-One-Cancels-the-Other

### Trading Bots
- `private-bot-create-trading-bot-grid` - Grid trading bot
- `private-bot-create-trading-bot-dca` - Dollar-cost averaging
- `private-bot-update-trading-bot-*` - Update bot parameters
- `private-bot-get-trading-bots` - List active bots

### Wallet & Account
- `private-user-balance` - Get account balances
- `private-get-deposit-address` - Deposit addresses
- `private-create-withdrawal` - Submit withdrawal
- `private-get-transactions` - Transaction history

### Positions (Derivatives)
- `private-get-positions` - List positions
- `private-close-position` - Close position
- `private-change-account-leverage` - Adjust leverage
- `private-set-isolated-margin` - Set isolated margin

### Public Data
- `public-get-instruments` - Available instruments
- `public-get-tickers` - Market tickers
- `public-get-candlestick` - OHLCV data
- `public-get-trades` - Recent trades

## Common Schema Objects

| Schema | Description | Key Fields |
|--------|-------------|------------|
| `PrivateOrder` | Order object | order_id, instrument_name, side, quantity, status |
| `TradeItemBase` | Trade execution | traded_quantity, traded_price, side |
| `AccountBalanceBase` | Balance info | total_available_balance, total_margin_balance |
| `PositionBalanceItem` | Position data | instrument_name, quantity, market_value |
| `InstrumentItem` | Instrument config | symbol, base_ccy, quote_ccy, type |

## Analysis Report

Run the analysis script for detailed breakdown:

```bash
cd openapi_docs
poetry run python analyze_api.py
```

This generates `api_summary.json` (in this directory) with:
- All 100+ endpoints and their methods
- Schema definitions and relationships
- Property lists for each data model

## Source

Official Crypto.com Exchange API docs:
https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/trading

Last updated: Generated automatically via `download_api_docs.py`

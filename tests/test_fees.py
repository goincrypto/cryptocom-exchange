"""Fee endpoints: the numbers a trade's profitability is decided on.

WHY THIS FILE EXISTS. Until now this library had no fee accessor at all, so the
consuming bot measured fees from its own fills and nobody believed the venue
exposed them. It does — `private/get-fee-rate`, `private/get-instrument-fee-rate`
and `private/get-fee-credit-balances` are all in this repo's own vendored OpenAPI
specs (`openapi_docs/specs/`). The answer was in the repo while an agent was
guessing path names and reporting "no fee endpoint exists".

The payloads below are TRANSCRIBED FROM LIVE RESPONSES captured on the operator's
account on 2026-10-18, not invented, because the interesting facts are ones no
author would invent:

* `CRO_USD` costs **0 bp maker / 4 bp taker** at instrument level while the
  account tier says 24.25/48.5 — so the account endpoint and the instrument
  endpoint are NOT proxies for each other, and a caller that asks the wrong one
  prices a trade wrong.
* The same endpoint answers `"0"`, `"4.0000"` and `"25.0000"` — the decimal
  count is NOT stable, so nothing may assume a scale.
* A 0 bp rate is a real answer here, which is exactly why an ABSENT field must
  raise instead of producing one. `0` and "unknown" have to stay different
  answers: a fee of 0 turns an unprofitable trade into a profitable one.

Like `test_trades_pagination.py`, these tests drive a scripted venue and need no
capture file and no credentials, so they run anywhere and cannot rot into a
replay of their own assumptions.
"""

import copy
from typing import Any

import pytest

import cryptocom.exchange as cro

#: Live `private/get-fee-rate` result, transcribed verbatim.
FEE_RATE_LIVE: dict[str, Any] = {
    "spot_tier": "1",
    "deriv_tier": "1",
    "effective_spot_maker_rate_bps": "24.2500000000",
    "effective_spot_taker_rate_bps": "48.5000000000",
    "effective_deriv_maker_rate_bps": "1.9400000000",
    "effective_deriv_taker_rate_bps": "3.8800000000",
}

#: Live `private/get-instrument-fee-rate` results, transcribed verbatim.
CRO_USD_LIVE = {
    "instrument_name": "CRO_USD",
    "effective_maker_rate_bps": "0",
    "effective_taker_rate_bps": "4.0000",
}
BTC_USD_LIVE = {
    "instrument_name": "BTC_USD",
    "effective_maker_rate_bps": "25.0000",
    "effective_taker_rate_bps": "50.000",
}
BTCUSD_PERP_LIVE = {
    "instrument_name": "BTCUSD-PERP",
    "effective_maker_rate_bps": "2.0000",
    "effective_taker_rate_bps": "4.0000",
}

#: Every fee field `private/get-fee-rate` must supply.
FEE_RATE_FIELDS = tuple(FEE_RATE_LIVE)


class ScriptedVenue(cro.ApiProvider):
    """Answers the fee endpoints the way the venue does.

    A scripted venue that ignored the request envelope would prove nothing, so
    every call is recorded: the tests assert the envelope too, since the live
    failure that motivated this work was an ENVELOPE error (a body with no
    `params` key answers 10004 BAD_REQUEST for a perfectly valid instrument
    name) being misread as "this endpoint does not accept that instrument".
    """

    def __init__(self, responses: dict[str, Any]) -> None:
        super().__init__(api_key="dummy", api_secret="dummy", auth_required=False)
        self.responses = responses
        self.calls: list[tuple[str, Any, bool]] = []

    async def post(self, path, data=None, sign=True):  # noqa: ANN001
        self.calls.append((path, data, sign))
        if path not in self.responses:
            raise cro.ApiError(f"unscripted path {path}", method=path)
        reply = self.responses[path]
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = reply(data)
        # Deep copy: a parser that mutated the payload could not otherwise
        # leak into the next test, but it could corrupt this one.
        return copy.deepcopy(reply)

    @property
    def paths(self) -> list[str]:
        return [call[0] for call in self.calls]


@pytest.fixture
def venue() -> ScriptedVenue:
    """A venue serving the live fee-rate payload."""
    return ScriptedVenue({"private/get-fee-rate": copy.deepcopy(FEE_RATE_LIVE)})


@pytest.fixture
def account(venue: ScriptedVenue) -> cro.Account:
    return cro.Account(api=venue, market=cro.Market(api=venue))


# ===========================================================================
# private/get-fee-rate
# ===========================================================================


@pytest.mark.asyncio
async def test_the_live_fee_rate_payload_parses_to_the_measured_numbers(
    account: cro.Account,
) -> None:
    """The point of the accessor: the bot's fills and this endpoint must agree.

    The consuming bot measures maker 24.25 bp / taker 48.5 bp from its own
    CRO_USD fills. These are the same numbers — the cross-check holds, so a
    future disagreement means one side broke.
    """
    fees = await account.get_fee_rate()

    assert (fees.spot_tier, fees.deriv_tier) == (1, 1)
    assert fees.spot_maker_bps == 24.25  # what the bot measures from fills
    assert fees.spot_taker_bps == 48.5  # what the bot measures from fills
    assert fees.deriv_maker_bps == 1.94
    assert fees.deriv_taker_bps == 3.88


@pytest.mark.asyncio
async def test_a_bps_string_is_basis_points_and_the_fraction_divides_by_10000(
    account: cro.Account,
) -> None:
    """The unit contract, pinned deliberately: `"24.2500000000"` is 24.25 bp.

    Two units exist in this file and each field says which one it holds:
    `*_bps` is basis points exactly as the venue sends it, `*_fraction` is
    bps/10_000 — the multiplier for a notional. The repo has already been
    burned by a fee unit ambiguity, so the suffix IS the unit and there is no
    third convention (no percent, no per-mille) to drift into.
    """
    fees = await account.get_fee_rate()

    assert fees.spot_maker_bps == 24.25
    assert fees.spot_maker_fraction == 0.002425
    assert fees.spot_taker_fraction == 0.00485
    assert fees.deriv_maker_fraction == 0.000194
    assert fees.deriv_taker_fraction == 0.000388
    # The two views must stay consistent with each other.
    for bps, fraction in (
        (fees.spot_maker_bps, fees.spot_maker_fraction),
        (fees.spot_taker_bps, fees.spot_taker_fraction),
        (fees.deriv_maker_bps, fees.deriv_maker_fraction),
        (fees.deriv_taker_bps, fees.deriv_taker_fraction),
    ):
        assert fraction == pytest.approx(bps / 10_000)


@pytest.mark.asyncio
async def test_tiers_are_integers_not_the_venue_strings(account: cro.Account) -> None:
    """`spot_tier: "1"` becomes the int 1. A tier is compared, not concatenated."""
    fees = await account.get_fee_rate()

    assert isinstance(fees.spot_tier, int)
    assert isinstance(fees.deriv_tier, int)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", FEE_RATE_FIELDS)
async def test_a_missing_fee_field_raises_indeterminate_rather_than_becoming_zero(
    missing: str,
) -> None:
    """No field, no fee — and definitely not a fee of 0.

    The fields are all in the venue's reply. If one is gone the reply is not
    the reply, and `float(data.get(k, 0))` (the reflex this file forbids)
    would hand a caller a 0 bp fee: the most expensive kind of wrong number,
    because it makes every trade look profitable.
    """
    payload = copy.deepcopy(FEE_RATE_LIVE)
    del payload[missing]
    venue = ScriptedVenue({"private/get-fee-rate": payload})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_rate()

    assert excinfo.value.is_indeterminate, (
        "an unreadable fee is UNKNOWN, not a value; the caller must skip the "
        "decision rather than price it"
    )
    assert excinfo.value.code is None
    assert "UNKNOWN" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("effective_spot_maker_rate_bps", "abc"),  # not a number
        ("effective_spot_maker_rate_bps", ""),  # empty string
        ("effective_spot_taker_rate_bps", None),  # explicit null
        ("effective_deriv_maker_rate_bps", "-1"),  # a fee below zero
        ("effective_deriv_taker_rate_bps", "nan"),  # float() accepts this!
        ("effective_spot_maker_rate_bps", "inf"),  # ...and this
        ("effective_spot_taker_rate_bps", True),  # bool is an int subclass
        # 1_000_000 bp = 10_000% of the notional: a decimal-shift bug, and
        # exactly what MAX_FEE_BPS exists to catch before it is traded on.
        ("effective_spot_taker_rate_bps", "1000000"),
    ],
)
async def test_an_absurd_rate_raises_instead_of_being_traded_on(
    field: str, value: Any
) -> None:
    """Every junk shape the venue could send, refused locally.

    `float()` happily parses "nan" and "inf", and `True` is 1 to Python. A fee
    that is NaN silently NaN-poisons every downstream P&L number, so it must
    be refused at the boundary.
    """
    payload = copy.deepcopy(FEE_RATE_LIVE)
    payload[field] = value
    venue = ScriptedVenue({"private/get-fee-rate": payload})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_rate()

    assert excinfo.value.is_indeterminate


@pytest.mark.asyncio
async def test_a_rate_at_the_ceiling_is_accepted_but_a_step_above_is_not() -> None:
    """`MAX_FEE_BPS` is a ceiling, not a tripwire on legitimate data."""
    payload = copy.deepcopy(FEE_RATE_LIVE)
    payload["effective_spot_maker_rate_bps"] = str(int(cro.MAX_FEE_BPS))
    venue = ScriptedVenue({"private/get-fee-rate": payload})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    fees = await account.get_fee_rate()
    assert fees.spot_maker_bps == cro.MAX_FEE_BPS

    payload["effective_spot_maker_rate_bps"] = "10000.0000000001"
    with pytest.raises(cro.ApiError):
        await account.get_fee_rate()


@pytest.mark.asyncio
async def test_a_real_zero_rate_parses_while_an_absent_one_raises(
    venue: ScriptedVenue,
) -> None:
    """The distinction the whole design rests on: 0 is data, absence is not.

    CRO_USD genuinely pays 0 bp maker (see the instrument tests below), so a
    parser may not treat 0 as "missing" — and may not treat missing as 0.
    """
    payload = copy.deepcopy(FEE_RATE_LIVE)
    payload["effective_spot_maker_rate_bps"] = "0"
    venue.responses["private/get-fee-rate"] = payload
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    fees = await account.get_fee_rate()
    assert fees.spot_maker_bps == 0.0
    assert fees.spot_maker_fraction == 0.0
    # The other fields still came through: this is a zero, not a blank reply.
    assert fees.spot_taker_bps == 48.5

    del payload["effective_spot_maker_rate_bps"]
    with pytest.raises(cro.ApiError):
        await account.get_fee_rate()


@pytest.mark.asyncio
async def test_fee_rate_is_a_signed_private_call_with_an_empty_params_object(
    account: cro.Account, venue: ScriptedVenue
) -> None:
    """The envelope the venue accepts: `params: {}`, signed.

    The spec requires `params` (an empty object) on this endpoint; the live
    probe confirmed both `{}` and omitting it work, and the spec shape is the
    one sent. Signing is pinned because an unsigned private call is a 401 at
    the venue and a silent 401 in an outage-sized bug hunt.
    """
    await account.get_fee_rate()

    path, data, sign = venue.calls[0]
    assert path == "private/get-fee-rate"
    assert data == {"params": {}}
    assert sign is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload", "corrupt"),
    [
        # A bare scalar: `"tier" in 5` raises TypeError and `5.get` raises
        # AttributeError, so this is what the object-shape guard actually
        # guards. (A list of strings would NOT: `name not in [...]` succeeds
        # and the missing-field check absorbs it - which is precisely how the
        # first version of this test failed to pin the guard at all.)
        ("private/get-fee-rate", 5, "rate"),
        # A list has no `.get`, so the instrument parser reaches the guard.
        ("private/get-instrument-fee-rate", ["BTC_USD"], "instrument"),
        # A credit ENTRY that is not an object: the entry parser must hold.
        ("private/get-fee-credit-balances", {"fee_credits": [5]}, "credits"),
        # The credits endpoint's own envelope checks: a non-object reply, and
        # a `fee_credits` that is present but not an array.
        ("private/get-fee-credit-balances", ["not", "a", "dict"], "credits"),
        ("private/get-fee-credit-balances", {"fee_credits": "nope"}, "credits"),
    ],
)
async def test_a_result_of_the_wrong_shape_raises_rather_than_crashing(
    path: str, payload: Any, corrupt: str
) -> None:
    """A venue reply of the wrong SHAPE is an indeterminate ApiError too.

    `AttributeError`/`TypeError` escaping a parser is indistinguishable from a
    bug in the caller's own code, and callers key their reconciliation on
    ApiError. Whatever the venue sends, the fee path answers with the taxonomy
    or with a value - never with a Python internals error.
    """
    venue = ScriptedVenue({path: payload})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    call = {
        "rate": account.get_fee_rate,
        "instrument": lambda: account.get_instrument_fee_rate("BTC_USD"),
        "credits": account.get_fee_credit_balances,
    }[corrupt]

    with pytest.raises(cro.ApiError) as excinfo:
        await call()

    assert excinfo.value.is_indeterminate


# ===========================================================================
# private/get-instrument-fee-rate
# ===========================================================================


@pytest.mark.asyncio
async def test_instrument_fee_rate_puts_instrument_name_under_params() -> None:
    """The contract that was guessed wrong live, pinned so it cannot recur.

    A body with NO `params` key answers `10004 BAD_REQUEST` — measured, and it
    is what a hand-built probe got while asking about `NEAR_USD`, which is a
    perfectly good instrument name. Reading that as "this endpoint does not
    take NEAR_USD" costs an hour and produces a false "no such endpoint"
    report. The name goes in `params.instrument_name`.
    """
    venue = ScriptedVenue({"private/get-instrument-fee-rate": BTC_USD_LIVE})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    await account.get_instrument_fee_rate("BTC_USD")

    _path, data, sign = venue.calls[0]
    assert "params" in data, "the envelope needs a params object (10004 otherwise)"
    assert data["params"] == {"instrument_name": "BTC_USD"}
    assert sign is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("instrument", "expected", "reply"),
    [
        ("CRO_USD", "CRO_USD", CRO_USD_LIVE),
        (cro.pairs.CRO_USD, "CRO_USD", CRO_USD_LIVE),
        (cro.pairs.BTC_USD, "BTC_USD", BTC_USD_LIVE),
        # A perpetual: NOT in Account.pairs, so the string form is how you
        # price one. This is the evidence the endpoint is not deriv-only.
        ("BTCUSD-PERP", "BTCUSD-PERP", BTCUSD_PERP_LIVE),
    ],
)
async def test_instrument_fee_rate_accepts_spot_pairs_and_perpetuals(
    instrument: Any, expected: str, reply: dict
) -> None:
    """Spot `Pair`, spot name and perp name all reach the same accessor."""
    venue = ScriptedVenue({"private/get-instrument-fee-rate": reply})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    rate = await account.get_instrument_fee_rate(instrument)

    assert rate.instrument_name == expected
    assert venue.calls[0][1]["params"] == {"instrument_name": expected}


@pytest.mark.asyncio
async def test_cro_usd_instrument_rate_is_the_promo_zero_maker() -> None:
    """The number an account-level query CANNOT produce, and must not.

    Account tier: 24.25 bp maker. This pair: 0 bp maker / 4 bp taker. A bot
    that reads only `get_fee_rate()` believes a CRO_USD maker fill costs six
    times more than it does.
    """
    venue = ScriptedVenue({"private/get-instrument-fee-rate": CRO_USD_LIVE})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    rate = await account.get_instrument_fee_rate("CRO_USD")

    assert rate.maker_bps == 0.0
    assert rate.maker_fraction == 0.0
    assert rate.taker_bps == 4.0
    assert rate.taker_fraction == 0.0004
    assert rate.maker_bps < 24.25, "instrument rate must be able to beat the tier"


@pytest.mark.asyncio
async def test_a_reply_pricing_another_instrument_is_refused() -> None:
    """Right number, wrong instrument: the most expensive kind of correct.

    If the venue ever answers BTC_USD's rate to a CRO_USD question, applying
    it would silently price a real order with someone else's fee schedule.
    """
    venue = ScriptedVenue({"private/get-instrument-fee-rate": BTC_USD_LIVE})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_instrument_fee_rate("CRO_USD")

    assert excinfo.value.is_indeterminate
    assert "CRO_USD" in str(excinfo.value) and "BTC_USD" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing", ["effective_maker_rate_bps", "effective_taker_rate_bps"]
)
async def test_a_missing_instrument_rate_raises(missing: str) -> None:
    """Same rule as the tier endpoint: absence raises, it does not default."""
    payload = dict(BTC_USD_LIVE)
    del payload[missing]
    venue = ScriptedVenue({"private/get-instrument-fee-rate": payload})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_instrument_fee_rate("BTC_USD")

    assert excinfo.value.is_indeterminate


@pytest.mark.asyncio
async def test_an_unknown_instrument_is_determinate_and_propagates() -> None:
    """Code 209 is a CONFIRMED answer, so it must not be blurred into unknown.

    Measured live: `NOT_A_REAL_COIN_USD` and an empty `instrument_name` both
    answer 209 INVALID_INSTRUMENT. The bot's rule is that an indeterminate
    error defers the decision while a determinate one settles it, so this
    distinction is load-bearing: "no such instrument" is a fact.
    """
    venue = ScriptedVenue(
        {
            "private/get-instrument-fee-rate": cro.exceptions.InvalidInstrumentError(
                "INVALID_INSTRUMENT", code=209, method="private/get-instrument-fee-rate"
            )
        }
    )
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.exceptions.InvalidInstrumentError) as excinfo:
        await account.get_instrument_fee_rate("NOT_A_REAL_COIN_USD")

    assert excinfo.value.code == 209
    assert not excinfo.value.is_indeterminate


@pytest.mark.asyncio
async def test_an_empty_instrument_name_fails_locally_without_a_request(
    account: cro.Account, venue: ScriptedVenue
) -> None:
    """A blank name is a programming error, refused before the wire.

    The venue would answer 209; failing locally keeps the rate-limit budget
    and points at the caller instead of at the exchange.
    """
    with pytest.raises(ValueError):
        await account.get_instrument_fee_rate("")

    assert venue.calls == [], "nothing may reach the venue for a bad argument"


# ===========================================================================
# private/get-fee-credit-balances
# ===========================================================================


@pytest.mark.asyncio
async def test_fee_credit_balances_sends_the_pagination_params(
    account: cro.Account,
) -> None:
    """`page`/`page_size` go through as-is (venue default 200, max 200)."""
    venue = ScriptedVenue({"private/get-fee-credit-balances": {"fee_credits": []}})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    await account.get_fee_credit_balances(page=2, page_size=50)

    _path, data, sign = venue.calls[0]
    assert data == {"params": {"page": 2, "page_size": 50}}
    assert sign is True


@pytest.mark.asyncio
async def test_an_empty_fee_credit_list_is_a_confirmed_answer() -> None:
    """`{"fee_credits": []}` -> `[]`: the venue confirmed there are none.

    Measured live on the account whose CRO_USD maker fee is 0 bp. The credits
    are EMPTY, which rules out "the 0 bp is a promo credit being burned" and
    leaves the instrument-level schedule (0 bp, per the tests above) as the
    explanation. An empty list must be distinguishable from "we could not
    read the reply", which is the next test.
    """
    venue = ScriptedVenue({"private/get-fee-credit-balances": {"fee_credits": []}})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    credits = await account.get_fee_credit_balances()

    assert credits == []


@pytest.mark.asyncio
async def test_a_response_without_fee_credits_is_not_read_as_no_credits() -> None:
    """Unknown is never absent. `fee_credits` is spec-required; absent means
    the reply is not the reply, and `[]` would be a fabricated fact."""
    venue = ScriptedVenue({"private/get-fee-credit-balances": {"unexpected": True}})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_credit_balances()

    assert excinfo.value.is_indeterminate
    assert "fee_credits" in str(excinfo.value)


@pytest.mark.asyncio
async def test_a_fee_credit_page_parses_into_typed_entries() -> None:
    """Master-account shape, built from the spec's own example values.

    `expiry_date`/`distribution_date` arrive as epoch MILLISECONDS and become
    epoch SECONDS (the unit every other timestamp in this library uses);
    `type` becomes `campaigns`/`campaign` because the wire key tells you
    nothing and `type` shadows a builtin.
    """
    venue = ScriptedVenue(
        {
            "private/get-fee-credit-balances": {
                "fee_credits": [
                    {
                        "expiry_date": 1735689540000,
                        "type": "Campaign1, Campaign2",
                        "distributed_amount": "200.00000000",
                        "available_balance": "150.00000000",
                        "details": [
                            {
                                "type": "Campaign1",
                                "distribution_date": 1704067140000,
                                "distributed_amount": "100.00000000",
                            }
                        ],
                    },
                    # A sub-account shape: only the two required fields.
                    {
                        "expiry_date": 1767225540000,
                        "available_balance": "12.50000000",
                    },
                ]
            }
        }
    )
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    credits = await account.get_fee_credit_balances()

    assert len(credits) == 2
    first = credits[0]
    assert first.expiry_at == 1735689540
    assert first.available_balance == 150.0
    assert first.distributed_amount == 200.0
    assert first.campaigns == "Campaign1, Campaign2"
    assert first.details[0].campaign == "Campaign1"
    assert first.details[0].distributed_at == 1704067140
    assert first.details[0].distributed_amount == 100.0
    second = credits[1]
    assert second.available_balance == 12.5
    assert second.distributed_amount is None, "absent, NOT 0.0"
    assert second.campaigns is None
    assert second.details == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["expiry_date", "available_balance"])
async def test_a_fee_credit_missing_a_required_field_raises(missing: str) -> None:
    """An entry we cannot date or value is not a credit balance."""
    entry = {
        "expiry_date": 1735689540000,
        "available_balance": "150.00000000",
    }
    del entry[missing]
    venue = ScriptedVenue({"private/get-fee-credit-balances": {"fee_credits": [entry]}})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_credit_balances()

    assert excinfo.value.is_indeterminate


@pytest.mark.asyncio
async def test_the_basis_point_ceiling_does_not_leak_into_credit_amounts() -> None:
    """`MAX_FEE_BPS` caps RATES. A credit BALANCE is money, not a rate.

    Without this, "1_500_000.0 USD distributed" would be refused by a cap that
    only makes sense for a fee percentage — and a wrongly-rejected balance is
    its own kind of missing data.
    """
    venue = ScriptedVenue(
        {
            "private/get-fee-credit-balances": {
                "fee_credits": [
                    {
                        "expiry_date": 1735689540000,
                        "available_balance": "1500000.00000000",
                        "distributed_amount": "9000000.00000000",
                    }
                ]
            }
        }
    )
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    credits = await account.get_fee_credit_balances()

    assert credits[0].available_balance == 1_500_000.0
    assert credits[0].distributed_amount == 9_000_000.0


@pytest.mark.asyncio
async def test_a_fee_detail_missing_its_amount_raises() -> None:
    """The per-campaign breakdown is only trustworthy if it adds up locally."""
    venue = ScriptedVenue(
        {
            "private/get-fee-credit-balances": {
                "fee_credits": [
                    {
                        "expiry_date": 1735689540000,
                        "available_balance": "150.00000000",
                        "details": [
                            {"type": "Campaign1", "distribution_date": 1704067140000}
                        ],
                    }
                ]
            }
        }
    )
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError):
        await account.get_fee_credit_balances()


# ===========================================================================
# The pair path must stay fee-free.
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tier",
    [
        "1.5",  # a tier that has drifted into decimal form
        "one",  # not a number at all
        True,  # bool is an int subclass: True must not become tier 1
        -1,  # a negative tier is corruption, not a discount
        "-1",
    ],
)
async def test_a_tier_that_is_not_a_non_negative_integer_raises(tier: Any) -> None:
    """Tiers are identity/limit inputs, not money to be approximated.

    A tier read through `float()` is how "1" becomes 10 or "0.1" becomes 0 -
    so the parser refuses anything that is not plainly a non-negative integer
    rather than repairing it.
    """
    payload = copy.deepcopy(FEE_RATE_LIVE)
    payload["spot_tier"] = tier
    venue = ScriptedVenue({"private/get-fee-rate": payload})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_rate()

    assert excinfo.value.is_indeterminate


@pytest.mark.asyncio
async def test_a_tier_sent_as_a_number_rather_than_a_string_is_accepted() -> None:
    """The venue sends `"1"`; an unambiguous JSON int 1 is still a 1.

    Accepting both costs nothing and neither is ambiguous - unlike a decimal
    tier, where the venue's intent could only be guessed at.
    """
    payload = copy.deepcopy(FEE_RATE_LIVE)
    payload["spot_tier"] = 2
    payload["deriv_tier"] = 3
    venue = ScriptedVenue({"private/get-fee-rate": payload})
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    fees = await account.get_fee_rate()

    assert (fees.spot_tier, fees.deriv_tier) == (2, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize("campaign", [None, "", 5])
async def test_a_fee_credit_detail_without_a_campaign_name_raises(
    campaign: Any,
) -> None:
    """A breakdown line with no campaign is a number with no owner.

    The per-campaign split is the only way to tell WHICH promo a credit came
    from; an unlabelled amount must not be summed into a balance.
    """
    detail: dict[str, Any] = {
        "distribution_date": 1704067140000,
        "distributed_amount": "100.00000000",
    }
    if campaign is not None:
        detail["type"] = campaign
    venue = ScriptedVenue(
        {
            "private/get-fee-credit-balances": {
                "fee_credits": [
                    {
                        "expiry_date": 1735689540000,
                        "available_balance": "150.00000000",
                        "details": [detail],
                    }
                ]
            }
        }
    )
    account = cro.Account(api=venue, market=cro.Market(api=venue))

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_credit_balances()

    assert excinfo.value.is_indeterminate


def test_a_pair_carries_no_fee_field_anywhere() -> None:
    """Fee is not an instrument constant, so `Pair` must not hold one.

    `public/get-instruments` reports no fee and `generate.py` writes none, so
    any `Pair.maker_fee` would be a fabricated 0.0 — and a 0.0 fee on the
    object a bot sizes orders from is the exact bug this feature exists to
    prevent. The fee comes from `Account`, or not at all.
    """
    pair = cro.pairs.CRO_USD

    fee_fields = [name for name in vars(pair) if "fee" in name.lower()]

    assert fee_fields == [], f"Pair grew fee state: {fee_fields}"
    assert "fee" not in repr(pair).lower()

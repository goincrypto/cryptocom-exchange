"""Fee endpoints: the numbers a trade's profitability is decided on.

WHY THIS FILE EXISTS. Until now this library had no fee accessor at all, so the
consuming bot measured fees from its own fills and nobody believed the venue
exposed them. It does — `private/get-fee-rate`, `private/get-instrument-fee-rate`
and `private/get-fee-credit-balances` are all in this repo's own vendored OpenAPI
specs (`openapi_docs/specs/`). The answer was in the repo while an agent was
guessing path names and reporting "no fee endpoint exists".

TWO KINDS OF COVERAGE, AND WHY BOTH.

* **Captured** (bottom section, `tests/captured/test_fees/*.json`): the strict
  replay harness serves responses recorded from the operator's live account.
  These are the tests that say what Crypto.com ACTUALLY sends — field set,
  stringly-typed numbers and all. Missing capture = failure, never a skip, and
  no credentials are needed to replay them.
* **Scripted** (everything above): a venue the tests dictate. It exists for the
  shapes the real venue will not produce on demand — a missing field, a NaN
  rate, a tier of `"one"`, a fee-credit page for an account that has no
  credits. Their payloads are TRANSCRIBED FROM LIVE RESPONSES, not invented,
  and `test_the_recorded_tier_payload_is_the_payload_this_file_scripts` is what
  keeps that claim honest: it compares the scripted constants against the
  recorded truth, so a scripted payload that drifts into fiction goes red.

The facts worth pinning, all of them measured rather than assumed:

* `CRO_USD` costs **0 bp maker / 4 bp taker** at instrument level while the
  account tier says 24.25/48.5 — so the account endpoint and the instrument
  endpoint are NOT proxies for each other, and a caller that asks the wrong one
  prices a trade wrong. `NEAR_USD`/`BTC_USD` cost 25/50, i.e. ABOVE the tier.
* The same endpoint family answers `"0"`, `"4.0000"`, `"25.0000"` and
  `"50.000"` — the decimal count is NOT stable, so nothing may assume a scale.
* A 0 bp rate is a real answer here, which is exactly why an ABSENT field must
  raise instead of producing one. `0` and "unknown" have to stay different
  answers: a fee of 0 turns an unprofitable trade into a profitable one.
"""

import copy
import json
from typing import Any

import pytest

import cryptocom.exchange as cro

# Wire paths, named once: they are the recorder's keys as well as the strings
# the accessors post, and a typo here silently retargets a whole test.
FEE_RATE_PATH = "private/get-fee-rate"
INSTRUMENT_FEE_PATH = "private/get-instrument-fee-rate"
FEE_CREDITS_PATH = "private/get-fee-credit-balances"

#: `private/get-fee-rate` result, transcribed from a live response and pinned
#: against the capture by test_the_recorded_tier_payload_is_the_payload...
FEE_RATE_LIVE: dict[str, Any] = {
    "spot_tier": "1",
    "deriv_tier": "1",
    "effective_spot_maker_rate_bps": "24.2500000000",
    "effective_spot_taker_rate_bps": "48.5000000000",
    "effective_deriv_maker_rate_bps": "1.9400000000",
    "effective_deriv_taker_rate_bps": "3.8800000000",
}

#: `private/get-instrument-fee-rate` results, transcribed from live responses.
#: Note the decimal counts differ BOTH across instruments AND inside one
#: payload: this family sends no fixed scale.
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
NEAR_USD_LIVE = {
    "instrument_name": "NEAR_USD",
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

    A response value may be a payload, an Exception to raise, or a callable of
    the request body. Use `serving()` rather than constructing this directly.
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


def serving(path: str, response: Any) -> tuple[ScriptedVenue, cro.Account]:
    """One venue + the account on it, for the scripted tests.

    Every scripted test serves exactly ONE path (a mutated payload, an error,
    or an empty page) and needs both objects; spelling `ScriptedVenue(...)`
    plus `Account(api=..., market=Market(api=...))` out twenty-odd times proved
    nothing and cost forty lines. `ScriptedVenue` stays the single place the
    scripted wire is defined.
    """
    venue = ScriptedVenue({path: response})
    return venue, cro.Account(api=venue, market=cro.Market(api=venue))


# ===========================================================================
# private/get-fee-rate
# ===========================================================================


@pytest.mark.asyncio
async def test_the_live_fee_rate_payload_parses_to_the_measured_numbers() -> None:
    """The point of the accessor: the bot's fills and this endpoint must agree.

    The consuming bot measures maker 24.25 bp / taker 48.5 bp from its own
    CRO_USD fills. These are the same numbers — the cross-check holds, so a
    future disagreement means one side broke.
    """
    _, account = serving(FEE_RATE_PATH, FEE_RATE_LIVE)

    fees = await account.get_fee_rate()

    assert (fees.spot_tier, fees.deriv_tier) == (1, 1)
    assert fees.spot_maker_bps == 24.25  # what the bot measures from fills
    assert fees.spot_taker_bps == 48.5  # what the bot measures from fills
    assert fees.deriv_maker_bps == 1.94
    assert fees.deriv_taker_bps == 3.88


@pytest.mark.asyncio
async def test_a_bps_string_is_basis_points_and_the_fraction_divides_by_10000() -> None:
    """The unit contract, pinned deliberately: `"24.2500000000"` is 24.25 bp.

    Two units exist in this file and each field says which one it holds:
    `*_bps` is basis points exactly as the venue sends it, `*_fraction` is
    bps/10_000 — the multiplier for a notional. The repo has already been
    burned by a fee unit ambiguity, so the suffix IS the unit and there is no
    third convention (no percent, no per-mille) to drift into.
    """
    _, account = serving(FEE_RATE_PATH, FEE_RATE_LIVE)
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
async def test_tiers_are_integers_not_the_venue_strings() -> None:
    """`spot_tier: "1"` becomes the int 1. A tier is compared, not concatenated."""
    _, account = serving(FEE_RATE_PATH, FEE_RATE_LIVE)
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
    _, account = serving(FEE_RATE_PATH, payload)

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
    _, account = serving(FEE_RATE_PATH, payload)

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_rate()

    assert excinfo.value.is_indeterminate


@pytest.mark.asyncio
async def test_a_rate_at_the_ceiling_is_accepted_but_a_step_above_is_not() -> None:
    """`MAX_FEE_BPS` is a ceiling, not a tripwire on legitimate data."""
    payload = copy.deepcopy(FEE_RATE_LIVE)
    payload["effective_spot_maker_rate_bps"] = str(int(cro.MAX_FEE_BPS))
    _, account = serving(FEE_RATE_PATH, payload)

    fees = await account.get_fee_rate()
    assert fees.spot_maker_bps == cro.MAX_FEE_BPS

    payload["effective_spot_maker_rate_bps"] = "10000.0000000001"
    with pytest.raises(cro.ApiError):
        await account.get_fee_rate()


@pytest.mark.asyncio
async def test_a_real_zero_rate_parses_while_an_absent_one_raises() -> None:
    """The distinction the whole design rests on: 0 is data, absence is not.

    CRO_USD genuinely pays 0 bp maker (see the instrument tests below), so a
    parser may not treat 0 as "missing" — and may not treat missing as 0.
    """
    zero = copy.deepcopy(FEE_RATE_LIVE)
    zero["effective_spot_maker_rate_bps"] = "0"
    _, account = serving(FEE_RATE_PATH, zero)

    fees = await account.get_fee_rate()
    assert fees.spot_maker_bps == 0.0
    assert fees.spot_maker_fraction == 0.0
    # The other fields still came through: this is a zero, not a blank reply.
    assert fees.spot_taker_bps == 48.5

    absent = copy.deepcopy(FEE_RATE_LIVE)
    del absent["effective_spot_maker_rate_bps"]
    _, account = serving(FEE_RATE_PATH, absent)
    with pytest.raises(cro.ApiError):
        await account.get_fee_rate()


@pytest.mark.asyncio
async def test_fee_rate_is_a_signed_private_call_with_an_empty_params_object() -> None:
    """The envelope the venue accepts: `params: {}`, signed.

    The spec requires `params` (an empty object) on this endpoint; the live
    probe confirmed both `{}` and omitting it work, and the spec shape is the
    one sent. Signing is pinned because an unsigned private call is a 401 at
    the venue and a silent 401 in an outage-sized bug hunt.
    """
    venue, account = serving(FEE_RATE_PATH, FEE_RATE_LIVE)
    await account.get_fee_rate()

    path, data, sign = venue.calls[0]
    assert path == FEE_RATE_PATH
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
        (FEE_RATE_PATH, 5, "rate"),
        # A list has no `.get`, so the instrument parser reaches the guard.
        (INSTRUMENT_FEE_PATH, ["BTC_USD"], "instrument"),
        # A credit ENTRY that is not an object: the entry parser must hold.
        (FEE_CREDITS_PATH, {"fee_credits": [5]}, "credits"),
        # The credits endpoint's own envelope checks: a non-object reply, and
        # a `fee_credits` that is present but not an array.
        (FEE_CREDITS_PATH, ["not", "a", "dict"], "credits"),
        (FEE_CREDITS_PATH, {"fee_credits": "nope"}, "credits"),
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
    _, account = serving(path, payload)

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
    venue, account = serving(INSTRUMENT_FEE_PATH, BTC_USD_LIVE)
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
        (cro.pairs.NEAR_USD, "NEAR_USD", NEAR_USD_LIVE),
        # A perpetual: NOT in Account.pairs, so the string form is how you
        # price one. This is the evidence the endpoint is not deriv-only.
        ("BTCUSD-PERP", "BTCUSD-PERP", BTCUSD_PERP_LIVE),
    ],
)
async def test_instrument_fee_rate_accepts_spot_pairs_and_perpetuals(
    instrument: Any, expected: str, reply: dict
) -> None:
    """Spot `Pair`, spot name and perp name all reach the same accessor."""
    venue, account = serving(INSTRUMENT_FEE_PATH, reply)

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
    _, account = serving(INSTRUMENT_FEE_PATH, CRO_USD_LIVE)

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
    _, account = serving(INSTRUMENT_FEE_PATH, BTC_USD_LIVE)

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
    _, account = serving(INSTRUMENT_FEE_PATH, payload)

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
    _, account = serving(
        INSTRUMENT_FEE_PATH,
        cro.exceptions.InvalidInstrumentError(
            "INVALID_INSTRUMENT", code=209, method=INSTRUMENT_FEE_PATH
        ),
    )

    with pytest.raises(cro.exceptions.InvalidInstrumentError) as excinfo:
        await account.get_instrument_fee_rate("NOT_A_REAL_COIN_USD")

    assert excinfo.value.code == 209
    assert not excinfo.value.is_indeterminate


@pytest.mark.asyncio
async def test_an_empty_instrument_name_fails_locally_without_a_request() -> None:
    """A blank name is a programming error, refused before the wire.

    The venue would answer 209; failing locally keeps the rate-limit budget
    and points at the caller instead of at the exchange.
    """
    venue, account = serving(FEE_RATE_PATH, FEE_RATE_LIVE)

    with pytest.raises(ValueError):
        await account.get_instrument_fee_rate("")

    assert venue.calls == [], "nothing may reach the venue for a bad argument"


# ===========================================================================
# private/get-fee-credit-balances
# ===========================================================================


@pytest.mark.asyncio
async def test_fee_credit_balances_sends_the_pagination_params() -> None:
    """`page`/`page_size` go through as-is (venue default 200, max 200)."""
    venue, account = serving(FEE_CREDITS_PATH, {"fee_credits": []})

    await account.get_fee_credit_balances(page=2, page_size=50)

    _path, data, sign = venue.calls[0]
    assert data == {"params": {"page": 2, "page_size": 50}}
    assert sign is True


@pytest.mark.asyncio
async def test_an_empty_fee_credit_list_is_a_confirmed_answer() -> None:
    """`{"fee_credits": []}` -> `[]`: the venue confirmed there are none.

    Measured live on the account whose CRO_USD maker fee is 0 bp - and pinned
    against the capture by `test_the_recorded_fee_credit_page...` below. The
    credits are EMPTY, which rules out "the 0 bp is a promo credit being
    burned" and leaves the instrument-level schedule (0 bp, per the tests
    above) as the explanation. An empty list must be distinguishable from "we
    could not read the reply", which is the next test.
    """
    _, account = serving(FEE_CREDITS_PATH, {"fee_credits": []})

    credits = await account.get_fee_credit_balances()

    assert credits == []


@pytest.mark.asyncio
async def test_a_response_without_fee_credits_is_not_read_as_no_credits() -> None:
    """Unknown is never absent. `fee_credits` is spec-required; absent means
    the reply is not the reply, and `[]` would be a fabricated fact."""
    _, account = serving(FEE_CREDITS_PATH, {"unexpected": True})

    with pytest.raises(cro.ApiError) as excinfo:
        await account.get_fee_credit_balances()

    assert excinfo.value.is_indeterminate
    assert "fee_credits" in str(excinfo.value)


#: A master-account credit page, built from the spec's own example values:
#: this account has no credits to record, so this shape stays scripted (see
#: `test_the_recorded_fee_credit_page_is_a_confirmed_empty_answer`).
SPEC_CREDIT_PAGE = {
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


@pytest.mark.asyncio
async def test_a_fee_credit_page_parses_into_typed_entries() -> None:
    """Master-account shape, built from the spec's own example values.

    `expiry_date`/`distribution_date` arrive as epoch MILLISECONDS and become
    epoch SECONDS (the unit every other timestamp in this library uses);
    `type` becomes `campaigns`/`campaign` because the wire key tells you
    nothing and `type` shadows a builtin.
    """
    _, account = serving(FEE_CREDITS_PATH, SPEC_CREDIT_PAGE)

    credits = await account.get_fee_credit_balances()

    assert len(credits) == 2
    first, second = credits
    assert first.expiry_at == 1735689540
    assert first.available_balance == 150.0
    assert first.distributed_amount == 200.0
    assert first.campaigns == "Campaign1, Campaign2"
    assert first.details[0].campaign == "Campaign1"
    assert first.details[0].distributed_at == 1704067140
    assert first.details[0].distributed_amount == 100.0
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
    _, account = serving(FEE_CREDITS_PATH, {"fee_credits": [entry]})

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
    page = {
        "fee_credits": [
            {
                "expiry_date": 1735689540000,
                "available_balance": "1500000.00000000",
                "distributed_amount": "9000000.00000000",
            }
        ]
    }
    _, account = serving(FEE_CREDITS_PATH, page)

    credits = await account.get_fee_credit_balances()

    assert credits[0].available_balance == 1_500_000.0
    assert credits[0].distributed_amount == 9_000_000.0


@pytest.mark.asyncio
async def test_a_fee_detail_missing_its_amount_raises() -> None:
    """The per-campaign breakdown is only trustworthy if it adds up locally."""
    page = {
        "fee_credits": [
            {
                "expiry_date": 1735689540000,
                "available_balance": "150.00000000",
                "details": [{"type": "Campaign1", "distribution_date": 1704067140000}],
            }
        ]
    }
    _, account = serving(FEE_CREDITS_PATH, page)

    with pytest.raises(cro.ApiError):
        await account.get_fee_credit_balances()


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
    _, account = serving(FEE_RATE_PATH, payload)

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
    _, account = serving(FEE_RATE_PATH, payload)

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
    page = {
        "fee_credits": [
            {
                "expiry_date": 1735689540000,
                "available_balance": "150.00000000",
                "details": [detail],
            }
        ]
    }
    _, account = serving(FEE_CREDITS_PATH, page)

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


# ===========================================================================
# Captured: what the venue REALLY answered.
#
# `tests/captured/test_fees/*.json` were recorded from the operator's live
# account (see tests/conftest.py: capture pins IPv4 egress, because an
# unpinned signed request leaves over IPv6 and the IP-bound key answers
# 40101). Replaying needs no credentials; recording needs them. The harness is
# STRICT — a missing capture, a changed call order or a request whose args
# differ from the recorded ones fails the test instead of skipping it, which
# is what makes these assertions about the API and not about this file.
# ===========================================================================


def recorded_payload(
    api: cro.RecordApiProvider, path: str, instrument: str | None = None
) -> Any:
    """The payload the venue really answered for `path` in this test.

    Reads the capture back instead of trusting the accessor's own view, so the
    assertions below are about what Crypto.com sent (stringly-typed numbers
    included) and not about what our parser produced. Works in both modes:
    capture mode flushes the in-memory records first (`save()` is idempotent;
    the `api` fixture flushes again at teardown), replay mode reads the
    committed capture unchanged.

    `instrument` selects by the echoed `instrument_name` rather than by the
    recorder's args key — a test that asked about several instruments must
    find the answer it is pinning, and the echo is the venue's own label.
    """
    if api.capture:
        api.save()
    blob = json.loads(api.cache_file.read_text())
    hits = [
        entry["response"]
        for by_args in blob.get(f"post_{path}", {}).values()
        for entry in by_args
    ]
    if instrument is not None:
        hits = [h for h in hits if h.get("instrument_name") == instrument]
    assert len(hits) == 1, (
        f"expected exactly one recorded answer for {path}"
        + (f" / {instrument}" if instrument else "")
        + f", found {len(hits)}: {hits}"
    )
    return hits[0]


@pytest.mark.asyncio
async def test_the_recorded_tier_payload_is_the_payload_this_file_scripts(
    api: cro.RecordApiProvider,
) -> None:
    """The scripted constants above are not fiction: they ARE the venue reply.

    Everything in the scripted section is built on `FEE_RATE_LIVE`, so this is
    the test that keeps the whole file honest - if the account's tier changes,
    or if this file starts inventing fields, the comparison below goes red and
    says which. Field set and values are the venue's, asserted verbatim.
    """
    account = cro.Account(api=api)

    fees = await account.get_fee_rate()
    raw = recorded_payload(api, FEE_RATE_PATH)

    assert raw == FEE_RATE_LIVE, "the scripted payload diverged from the venue"
    # Every value arrives as a decimal STRING, ten of them after the point.
    assert all(isinstance(value, str) for value in raw.values())
    assert raw["effective_spot_maker_rate_bps"] == "24.2500000000"
    # And the accessor is faithful to those exact strings, not to a scale:
    # what float() of the venue's own text says is what the caller gets.
    assert (fees.spot_maker_bps, fees.spot_taker_bps) == (
        float(raw["effective_spot_maker_rate_bps"]),
        float(raw["effective_spot_taker_rate_bps"]),
    )
    assert (fees.deriv_maker_bps, fees.deriv_taker_bps) == (
        float(raw["effective_deriv_maker_rate_bps"]),
        float(raw["effective_deriv_taker_rate_bps"]),
    )
    assert (fees.spot_tier, fees.deriv_tier) == (
        int(raw["spot_tier"]),
        int(raw["deriv_tier"]),
    )
    # The recording is the account's own state, cross-checked against what the
    # consuming bot measures from its fills.
    assert fees.spot_maker_fraction == pytest.approx(0.002425)


@pytest.mark.asyncio
async def test_the_recorded_tier_payload_fails_honestly_field_by_field(
    api: cro.RecordApiProvider,
) -> None:
    """Each REAL field of the recorded reply is required - proved on the reply.

    Same rule as the scripted missing-field test, but the payload here is the
    venue's own bytes: every one of the six fields it actually sends is
    mandatory, and dropping any of them must yield an UNKNOWN fee rather than
    a number. Nothing is invented to be missing here.
    """
    account = cro.Account(api=api)
    await account.get_fee_rate()
    raw = recorded_payload(api, FEE_RATE_PATH)

    assert set(raw) == set(FEE_RATE_FIELDS)
    for field in FEE_RATE_FIELDS:
        broken = {key: value for key, value in raw.items() if key != field}
        error: cro.ApiError | None = None
        try:
            cro.FeeRate.from_api(broken)
        except cro.ApiError as exc:
            error = exc
        assert error is not None, f"dropping {field} produced a fee, not an error"
        assert error.is_indeterminate, field
        assert error.code is None, field


@pytest.mark.asyncio
async def test_the_recorded_cro_usd_promo_beats_the_recorded_account_tier(
    api: cro.RecordApiProvider,
) -> None:
    """0 bp maker is a fact about the venue, not a parsing accident.

    Both numbers come from the same recording session, so this is the live
    evidence that the account tier and the instrument schedule are NOT proxies
    for each other: a caller that prices CRO_USD from `get_fee_rate()` believes
    a maker fill costs six times what the venue charges.
    """
    account = cro.Account(api=api)

    tier = await account.get_fee_rate()
    rate = await account.get_instrument_fee_rate(cro.pairs.CRO_USD)
    raw = recorded_payload(api, INSTRUMENT_FEE_PATH, instrument="CRO_USD")

    assert raw == CRO_USD_LIVE, "the scripted payload diverged from the venue"
    # `"0"` is the venue's whole answer for maker: zero, with no decimals.
    assert rate.maker_bps == 0.0
    assert rate.maker_fraction == 0.0
    assert rate.taker_bps == 4.0
    assert (rate.maker_bps, rate.taker_bps) == (
        float(raw["effective_maker_rate_bps"]),
        float(raw["effective_taker_rate_bps"]),
    )
    assert rate.maker_bps < tier.spot_maker_bps
    assert rate.taker_bps < tier.spot_taker_bps


@pytest.mark.asyncio
async def test_the_recorded_instrument_schedules_genuinely_differ(
    api: cro.RecordApiProvider,
) -> None:
    """Three instruments, three schedules, one recording session.

    CRO_USD 0/4, NEAR_USD and BTC_USD 25/50 (ABOVE the account tier's
    24.25/48.5), BTCUSD-PERP 2/4 - so no accessor can be inferred from
    another, and the decimal counts (`"0"`, `"4.0000"`, `"25.0000"`,
    `"50.000"`) differ within one endpoint family, which is why no parser here
    assumes a scale.
    """
    account = cro.Account(api=api)

    rates = {
        name: await account.get_instrument_fee_rate(name)
        for name in ("CRO_USD", "NEAR_USD", "BTC_USD", "BTCUSD-PERP")
    }

    assert recorded_payload(api, INSTRUMENT_FEE_PATH, "NEAR_USD") == NEAR_USD_LIVE
    assert recorded_payload(api, INSTRUMENT_FEE_PATH, "BTC_USD") == BTC_USD_LIVE
    assert recorded_payload(api, INSTRUMENT_FEE_PATH, "BTCUSD-PERP") == BTCUSD_PERP_LIVE
    assert [rate.maker_bps for rate in rates.values()] == [0.0, 25.0, 25.0, 2.0]
    assert [rate.taker_bps for rate in rates.values()] == [4.0, 50.0, 50.0, 4.0]
    # The promo pair is cheaper than the venue's plain spot schedule...
    assert rates["CRO_USD"].maker_bps < rates["NEAR_USD"].maker_bps
    # ...and the plain spot schedule is priced ABOVE the discounted tier, so
    # the tier answers neither question.
    assert rates["NEAR_USD"].maker_bps > 24.25
    assert rates["NEAR_USD"].taker_bps > 48.5
    # A perp is reachable by name and priced on its own schedule.
    assert rates["BTCUSD-PERP"].maker_bps != rates["BTC_USD"].maker_bps


@pytest.mark.asyncio
async def test_the_recorded_instrument_payload_fails_honestly_field_by_field(
    api: cro.RecordApiProvider,
) -> None:
    """The recorded instrument reply carries two fee fields and needs both.

    `instrument_name` is deliberately excluded: the accessor treats the name IT
    asked for as authoritative and only refuses a MISMATCH, so an absent echo
    is survivable while an absent rate is not.
    """
    account = cro.Account(api=api)
    await account.get_instrument_fee_rate("CRO_USD")
    raw = recorded_payload(api, INSTRUMENT_FEE_PATH, instrument="CRO_USD")

    assert set(raw) == {
        "instrument_name",
        "effective_maker_rate_bps",
        "effective_taker_rate_bps",
    }
    for field in ("effective_maker_rate_bps", "effective_taker_rate_bps"):
        broken = {key: value for key, value in raw.items() if key != field}
        error: cro.ApiError | None = None
        try:
            cro.InstrumentFeeRate.from_api("CRO_USD", broken)
        except cro.ApiError as exc:
            error = exc
        assert error is not None, f"dropping {field} produced a fee, not an error"
        assert error.is_indeterminate, field


@pytest.mark.asyncio
async def test_the_recorded_fee_credit_page_is_a_confirmed_empty_answer(
    api: cro.RecordApiProvider,
) -> None:
    """The venue's whole answer for credits is `{"fee_credits": []}`.

    Empty is CONFIRMED here, not inferred: the reply is well-formed and says
    there are none. On the same account CRO_USD pays 0 bp maker, which pins
    the explanation of that zero at the instrument schedule rather than at a
    credit being burned.

    WHAT THIS CAPTURE CANNOT PROVE: the account holds no credits, so
    `FeeCredit`'s field handling (epoch ms -> seconds, `type` -> campaigns,
    absent `distributed_amount`) is covered only by the scripted spec page
    above. Re-record this test on an account that has one.
    """
    account = cro.Account(api=api)

    credits = await account.get_fee_credit_balances()
    raw = recorded_payload(api, FEE_CREDITS_PATH)

    assert raw == {"fee_credits": []}
    assert credits == []

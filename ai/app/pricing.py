"""School-advertised rates and decimal estimates, never confirmed billed charges."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from threading import Lock

logger = logging.getLogger(__name__)
COST_UNIT = "provider_dollars"


class PricingUnavailable(Exception):
    """Optional pricing metadata could not be loaded."""


def nonnegative_decimal(value: object) -> Decimal | None:
    if type(value) not in {int, float, str, Decimal}:
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and 0 <= number <= Decimal("1e15") else None
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class ModelRate:
    model_id: str
    fetched_at: str
    input_microdollars_per_million_tokens: Decimal | None = None
    output_microdollars_per_million_tokens: Decimal | None = None
    audio_microdollars_per_minute: Decimal | None = None
    alias_of: str | None = None

    def chat_cost(self, input_tokens: int | None, output_tokens: int | None) -> Decimal | None:
        if (
            type(input_tokens) is not int
            or input_tokens < 0
            or type(output_tokens) is not int
            or output_tokens < 0
            or self.input_microdollars_per_million_tokens is None
            or self.output_microdollars_per_million_tokens is None
        ):
            return None
        with localcontext() as context:
            context.prec = 50
            return (
                input_tokens * self.input_microdollars_per_million_tokens
                + output_tokens * self.output_microdollars_per_million_tokens
            ) / Decimal(1_000_000_000_000)

    def audio_cost(self, seconds: Decimal | None) -> Decimal | None:
        if seconds is None or seconds <= 0 or self.audio_microdollars_per_minute is None:
            return None
        with localcontext() as context:
            context.prec = 50
            return seconds * self.audio_microdollars_per_minute / Decimal(60_000_000)

    def metadata(self) -> dict:
        return {
            "source": "school_models",
            "model_id": self.model_id,
            "fetched_at": self.fetched_at,
            **{
                name: str(value) if value is not None else None
                for name in (
                    "input_microdollars_per_million_tokens",
                    "output_microdollars_per_million_tokens",
                    "audio_microdollars_per_minute",
                )
                for value in (getattr(self, name),)
            },
        }


class PricingCache:
    """One cache per school client/runtime; no waiting on another thread's refresh.

    Failed refreshes return unknown rates and back off for at most 30 seconds.
    Expired prices are never silently reused as current prices.
    """

    def __init__(
        self,
        loader: Callable[[], object],
        *,
        ttl: float = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._loader, self._ttl, self._clock = loader, ttl, clock
        self._refresh_after = 0.0
        self._rates: dict[str, ModelRate] = {}
        self._lock = Lock()

    def snapshot(self) -> dict[str, ModelRate]:
        if self._clock() < self._refresh_after:
            return self._rates
        if not self._lock.acquire(blocking=False):
            return {}
        try:
            # A different caller may have finished between the first check and lock.
            if self._clock() < self._refresh_after:
                return self._rates
            try:
                body = self._loader()
                if not isinstance(body, dict) or not isinstance(body.get("data"), list):
                    raise PricingUnavailable()
                fetched_at = datetime.now(UTC).isoformat()
                rates = {}
                for entry in body["data"]:
                    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                        continue
                    metadata = entry.get("soclaas")
                    if not isinstance(metadata, dict):
                        continue
                    rates[entry["id"]] = ModelRate(
                        model_id=entry["id"],
                        fetched_at=fetched_at,
                        alias_of=metadata.get("alias_of"),
                        **{
                            name: nonnegative_decimal(metadata.get(name))
                            for name in (
                                "input_microdollars_per_million_tokens",
                                "output_microdollars_per_million_tokens",
                                "audio_microdollars_per_minute",
                            )
                        },
                    )
                self._rates = rates
                self._refresh_after = self._clock() + self._ttl
            except (PricingUnavailable, ValueError, TypeError):
                logger.warning("School pricing metadata unavailable")
                self._rates = {}
                self._refresh_after = self._clock() + min(30, self._ttl)
            return self._rates
        finally:
            self._lock.release()


def rate_for_model(rates: dict[str, ModelRate], requested: str, returned: str) -> ModelRate | None:
    if returned in rates:
        return rates[returned]
    requested_rate = rates.get(requested)
    if requested_rate and (requested == returned or requested_rate.alias_of == returned):
        return requested_rate
    return None


def cost_text(cost: Decimal | None) -> str | None:
    return format(cost, "f") if cost is not None else None

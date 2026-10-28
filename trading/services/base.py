from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class MarketAPIError(RuntimeError):
    pass

@dataclass(frozen=True, slots=True)
class Market:
    symbol: str
    base_asset: str
    quote_asset: str
    last_price: Decimal | None = None
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class Ticker:
    symbol: str
    last_price: Decimal
    bid_price: Decimal | None = None
    ask_price: Decimal | None = None
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None
    volume_24h: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OrderBook:
    symbol: str
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    resolution: str
    opened_at: int
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


class MarketAPIService(ABC):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()
        retry_policy: Retry = Retry(
            total=4,
            connect=3,
            read=3,
            status=4,
            backoff_factor=0.75,
            status_forcelist=(408, 429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry_policy))

    def _get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise MarketAPIError(f"Market API request failed: {exc}") from exc

        if not isinstance(payload, dict):
            raise MarketAPIError("Market API returned an invalid JSON payload")
        if payload.get("success") is False:
            raise MarketAPIError(
                str(payload.get("message") or "Market API request failed")
            )
        return payload

    @abstractmethod
    def _headers(self) -> dict[str, str]:
        pass
    @abstractmethod
    def list_markets(self) -> list[Market]:
        pass

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        pass

    @abstractmethod
    def get_order_book(self, symbol: str) -> OrderBook:
        pass

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        resolution: str,
        from_timestamp: int,
        to_timestamp: int,
    ) -> tuple[Candle, ...]:
        pass
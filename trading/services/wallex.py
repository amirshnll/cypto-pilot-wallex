from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings

from .base import Candle, Market, MarketAPIError, MarketAPIService, OrderBook, Ticker


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MarketAPIError(
            f"Wallex returned an invalid decimal value: {value!r}"
        ) from exc


class WallexMarketService(MarketAPIService):
    MARKETS_PATH = "/hector/web/v1/markets"
    ORDER_BOOK_PATH = "/v1/depth"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("base_url", settings.WALLEX_BASE_URL)
        kwargs.setdefault("api_key", settings.WALLEX_API_KEY)
        super().__init__(**kwargs)
        self._symbols_cache: dict[str, Any] | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def list_markets(self) -> list[Market]:
        payload = self._get(self.MARKETS_PATH)
        raw_markets = payload.get("result", {}).get("markets", [])
        if not isinstance(raw_markets, list):
            raise MarketAPIError("Wallex markets response has an unexpected shape")

        markets: list[Market] = []
        for item in raw_markets:
            if not isinstance(item, dict) or not item.get("symbol"):
                continue
            stats = item.get("stats") or {}
            markets.append(
                Market(
                    symbol=str(item["symbol"]).upper(),
                    base_asset=str(
                        item.get("base_asset") or item.get("baseAsset") or ""
                    ).upper(),
                    quote_asset=str(
                        item.get("quote_asset") or item.get("quoteAsset") or ""
                    ).upper(),
                    last_price=_decimal(
                        stats.get("lastPrice") or item.get("last_price")
                    ),
                    is_active=bool(item.get("is_spot", True)),
                )
            )
        return markets

    def get_ticker(self, symbol: str) -> Ticker:
        normalized_symbol = self._normalize_symbol(symbol)
        if self._symbols_cache is None:
            payload = self._get("/v1/markets")
            raw_symbols = payload.get("result", {}).get("symbols", {})
            if not isinstance(raw_symbols, dict):
                raise MarketAPIError("Wallex markets response has an unexpected shape")
            self._symbols_cache = raw_symbols
        symbols: dict[str, Any] = self._symbols_cache
        raw = symbols.get(normalized_symbol) if isinstance(symbols, dict) else None
        if not isinstance(raw, dict):
            raise MarketAPIError(f"Wallex market not found: {normalized_symbol}")

        stats = raw.get("stats") or {}
        last_price = _decimal(stats.get("lastPrice"))
        if last_price is None:
            raise MarketAPIError(
                f"Wallex ticker has no last price: {normalized_symbol}"
            )
        return Ticker(
            symbol=normalized_symbol,
            last_price=last_price,
            bid_price=_decimal(stats.get("bidPrice")),
            ask_price=_decimal(stats.get("askPrice")),
            high_24h=_decimal(stats.get("24h_highPrice")),
            low_24h=_decimal(stats.get("24h_lowPrice")),
            volume_24h=_decimal(stats.get("24h_volume")),
        )

    def get_order_book(self, symbol: str) -> OrderBook:
        normalized_symbol = self._normalize_symbol(symbol)
        payload = self._get(self.ORDER_BOOK_PATH, params={"symbol": normalized_symbol})
        result = payload.get("result") or {}
        return OrderBook(
            symbol=normalized_symbol,
            bids=self._parse_levels(result.get("bid")),
            asks=self._parse_levels(result.get("ask")),
        )

    def get_candles(
        self,
        symbol: str,
        resolution: str,
        from_timestamp: int,
        to_timestamp: int,
    ) -> tuple[Candle, ...]:
        normalized_symbol: str = self._normalize_symbol(symbol)
        if from_timestamp >= to_timestamp:
            raise ValueError("from_timestamp must be before to_timestamp")
        payload = self._get(
            "/v1/udf/history",
            params={
                "symbol": normalized_symbol,
                "resolution": resolution,
                "from": from_timestamp,
                "to": to_timestamp,
            },
        )
        if payload.get("s") == "no_data":
            return ()
        timestamps = payload.get("t", [])
        opens = payload.get("o", [])
        highs = payload.get("h", [])
        lows = payload.get("l", [])
        closes = payload.get("c", [])
        volumes = payload.get("v", [])
        lengths: set[int] = {
            len(values) for values in (timestamps, opens, highs, lows, closes, volumes)
        }
        if len(lengths) != 1:
            raise MarketAPIError("Wallex candle response arrays have different lengths")
        return tuple(
            Candle(
                symbol=normalized_symbol,
                resolution=resolution,
                opened_at=int(timestamps[index]),
                open_price=_decimal(opens[index]) or Decimal("0"),
                high_price=_decimal(highs[index]) or Decimal("0"),
                low_price=_decimal(lows[index]) or Decimal("0"),
                close_price=_decimal(closes[index]) or Decimal("0"),
                volume=_decimal(volumes[index]) or Decimal("0"),
            )
            for index in range(len(timestamps))
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.replace("/", "").replace("-", "").strip().upper()
        if not normalized or not normalized.isalnum():
            raise ValueError("symbol must contain only letters and numbers")
        return normalized

    @staticmethod
    def _parse_levels(levels: Any) -> tuple[tuple[Decimal, Decimal], ...]:
        if not isinstance(levels, list):
            raise MarketAPIError("Wallex order-book response has an unexpected shape")
        parsed = []
        for level in levels:
            if not isinstance(level, dict):
                continue
            price = _decimal(level.get("price"))
            quantity = _decimal(level.get("quantity"))
            if price is not None and quantity is not None:
                parsed.append((price, quantity))
        return tuple(parsed)

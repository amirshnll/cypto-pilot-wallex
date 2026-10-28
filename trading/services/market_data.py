from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.db import transaction

from trading.models import MarketCandle, OrderBookSnapshot
from trading.services.base import Candle, MarketAPIError, OrderBook
from trading.services.wallex import WallexMarketService
from trading.services.candles import resolution_seconds
from trading.services.market_freshness import MarketFreshnessService


@dataclass(frozen=True, slots=True)
class MarketDataResult:
    symbol: str
    candles_saved: int
    order_book_saved: bool
    error: str | None = None


class MarketDataCollectionService:
    def __init__(
        self,
        market_service: WallexMarketService | None = None,
        stale_after_hours: int = 3,
    ) -> None:
        self.market_service: WallexMarketService = (
            market_service or WallexMarketService()
        )
        self.freshness = MarketFreshnessService(stale_after_hours)

    def collect(
        self,
        symbols: tuple[str, ...],
        *,
        resolution: str = "60",
        lookback_seconds: int = 604_800,
    ) -> tuple[MarketDataResult, ...]:
        now: int = int(time.time())
        results: list[MarketDataResult] = []
        for symbol in symbols:
            try:
                order_book: OrderBook = self.market_service.get_order_book(symbol)
                latest_opened_at = (
                    MarketCandle.objects.filter(symbol=symbol, resolution=resolution)
                    .order_by("-opened_at")
                    .values_list("opened_at", flat=True)
                    .first()
                )
                from_timestamp: int = (
                    max(
                        now - lookback_seconds, int(latest_opened_at.timestamp()) - 3600
                    )
                    if latest_opened_at is not None
                    else now - lookback_seconds
                )
                candles: tuple[Candle, ...] = self.market_service.get_candles(
                    symbol, resolution, from_timestamp, now
                )
                closed_candles: tuple[Candle, ...] = tuple(
                    candle
                    for candle in candles
                    if candle.opened_at + resolution_seconds(resolution) <= now
                )
                saved: int = self._persist(
                    symbol, resolution, order_book, closed_candles
                )
                results.append(MarketDataResult(symbol, saved, True))
            except (MarketAPIError, ValueError) as exc:
                results.append(MarketDataResult(symbol, 0, False, str(exc)))
            finally:
                self.freshness.refresh(
                    symbol,
                    resolution,
                    checked_at=datetime.fromtimestamp(now, tz=dt_timezone.utc),
                )
        return tuple(results)

    @staticmethod
    @transaction.atomic
    def _persist(
        symbol: str,
        resolution: str,
        order_book: OrderBook,
        candles: tuple[Candle, ...],
    ) -> int:
        bids: tuple[tuple[Decimal, Decimal], ...] = order_book.bids[:20]
        asks: tuple[tuple[Decimal, Decimal], ...] = order_book.asks[:20]
        best_bid: Decimal | None = max((level[0] for level in bids), default=None)
        best_ask: Decimal | None = min((level[0] for level in asks), default=None)
        spread: Decimal | None = (
            best_ask - best_bid
            if best_bid is not None and best_ask is not None
            else None
        )
        midpoint: Decimal | None = (
            (best_bid + best_ask) / Decimal("2")
            if best_bid is not None and best_ask is not None
            else None
        )
        spread_bps: Decimal | None = (
            spread / midpoint * Decimal("10000")
            if spread is not None and midpoint not in (None, Decimal("0"))
            else None
        )
        OrderBookSnapshot.objects.create(
            symbol=symbol,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_bps=spread_bps,
            bid_depth=sum((price * quantity for price, quantity in bids), Decimal("0")),
            ask_depth=sum((price * quantity for price, quantity in asks), Decimal("0")),
            bids=[[str(price), str(quantity)] for price, quantity in bids],
            asks=[[str(price), str(quantity)] for price, quantity in asks],
        )
        saved: int = 0
        for candle in candles:
            _instance, created = MarketCandle.objects.update_or_create(
                symbol=symbol,
                resolution=resolution,
                opened_at=datetime.fromtimestamp(candle.opened_at, tz=dt_timezone.utc),
                defaults={
                    "open_price": candle.open_price,
                    "high_price": candle.high_price,
                    "low_price": candle.low_price,
                    "close_price": candle.close_price,
                    "volume": candle.volume,
                },
            )
            saved += int(created)
        return saved

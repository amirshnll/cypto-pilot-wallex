from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from trading.models import MarketCandle, OrderBookSnapshot
from trading.services.base import Candle, OrderBook
from trading.services.market_data import MarketDataCollectionService


class MarketDataCollectionServiceTests(TestCase):
    @patch("trading.services.market_data.time.time", return_value=1_700_003_600)
    def test_collect_excludes_current_unclosed_candle(self, _time: Mock) -> None:
        market_service = Mock()
        market_service.get_order_book.return_value = OrderBook(
            symbol="BTCTMN",
            bids=((Decimal("100"), Decimal("1")),),
            asks=((Decimal("101"), Decimal("1")),),
        )
        closed = Candle(
            "BTCTMN",
            "60",
            1_700_000_000,
            Decimal("100"),
            Decimal("102"),
            Decimal("99"),
            Decimal("101"),
            Decimal("10"),
        )
        open_candle = Candle(
            "BTCTMN",
            "60",
            1_700_003_600,
            Decimal("101"),
            Decimal("103"),
            Decimal("100"),
            Decimal("102"),
            Decimal("2"),
        )
        market_service.get_candles.return_value = (closed, open_candle)

        result = MarketDataCollectionService(market_service).collect(("BTCTMN",))

        self.assertIsNone(result[0].error)
        self.assertEqual(MarketCandle.objects.count(), 1)
        self.assertEqual(
            MarketCandle.objects.get().opened_at.timestamp(), closed.opened_at
        )

    def test_persist_calculates_spread_depth_and_deduplicates_candles(self) -> None:
        book = OrderBook(
            symbol="BTCUSDT",
            bids=((Decimal("100"), Decimal("2")),),
            asks=((Decimal("101"), Decimal("3")),),
        )
        candle = Candle(
            symbol="BTCUSDT",
            resolution="5",
            opened_at=1_700_000_000,
            open_price=Decimal("100"),
            high_price=Decimal("102"),
            low_price=Decimal("99"),
            close_price=Decimal("101"),
            volume=Decimal("10"),
        )

        first = MarketDataCollectionService._persist("BTCUSDT", "5", book, (candle,))
        second = MarketDataCollectionService._persist("BTCUSDT", "5", book, (candle,))

        snapshot = OrderBookSnapshot.objects.first()
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(MarketCandle.objects.count(), 1)
        self.assertEqual(snapshot.spread, Decimal("1"))
        self.assertEqual(snapshot.bid_depth, Decimal("200"))

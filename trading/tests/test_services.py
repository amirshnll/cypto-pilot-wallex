from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from trading.services import WallexMarketService


def response_with(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@override_settings(WALLEX_API_KEY="secret-key", WALLEX_BASE_URL="https://api.wallex.ir")
class WallexMarketServiceTests(SimpleTestCase):
    def setUp(self):
        self.session = Mock()
        self.service = WallexMarketService(session=self.session)

    def test_api_key_is_sent_in_header(self):
        self.session.get.return_value = response_with(
            {"result": {"markets": []}, "success": True}
        )

        self.service.list_markets()

        headers = self.session.get.call_args.kwargs["headers"]
        self.assertEqual(headers["x-api-key"], "secret-key")

    def test_get_ticker_normalizes_wallex_response(self):
        self.session.get.return_value = response_with(
            {
                "success": True,
                "result": {
                    "symbols": {
                        "BTCUSDT": {
                            "stats": {
                                "lastPrice": "62000.10",
                                "bidPrice": "61999.00",
                                "askPrice": "62001.00",
                                "24h_highPrice": "63000",
                                "24h_lowPrice": "60000",
                                "24h_volume": "12.5",
                            }
                        }
                    }
                },
            }
        )

        ticker = self.service.get_ticker("btc/usdt")

        self.assertEqual(ticker.symbol, "BTCUSDT")
        self.assertEqual(str(ticker.last_price), "62000.10")

    def test_get_order_book_normalizes_levels(self):
        self.session.get.return_value = response_with(
            {
                "success": True,
                "result": {
                    "bid": [{"price": "100", "quantity": "2"}],
                    "ask": [{"price": "101", "quantity": 3}],
                },
            }
        )

        book = self.service.get_order_book("BTC-USDT")

        self.assertEqual(str(book.bids[0][0]), "100")
        self.assertEqual(str(book.asks[0][1]), "3")

    def test_get_candles_normalizes_ohlcv_arrays(self):
        self.session.get.return_value = response_with(
            {
                "s": "ok",
                "t": [1_700_000_000],
                "o": ["100"],
                "h": ["110"],
                "l": ["90"],
                "c": ["105"],
                "v": ["12.5"],
            }
        )

        candles = self.service.get_candles("BTCUSDT", "5", 1_699_999_000, 1_700_001_000)

        self.assertEqual(len(candles), 1)
        self.assertEqual(str(candles[0].close_price), "105")

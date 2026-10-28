from unittest.mock import Mock

from django.test import SimpleTestCase, TestCase

from trading.forms import BotConfigurationForm
from trading.models import BotConfiguration
from trading.services.wallex import WallexMarketService

from .test_services import response_with

COMMODITY_SYMBOLS = (
    "USOONTMN",
    "UNGONTMN",
    "PPLTONTMN",
    "XAUTTMN",
    "SLVONTMN",
    "COPXONTMN",
)


class CommodityMarketValidationTests(TestCase):
    def test_all_commodity_symbols_are_allowed(self) -> None:
        config = BotConfiguration(
            name="commodities",
            symbols=list(COMMODITY_SYMBOLS),
            strategy_weights={"sma_rsi": 1},
        )
        config.full_clean()

    def test_all_commodity_symbols_are_available_in_dashboard(self) -> None:
        choices = {value for value, _label in BotConfigurationForm.SYMBOL_CHOICES}
        self.assertTrue(set(COMMODITY_SYMBOLS).issubset(choices))


class CommodityWallexParsingTests(SimpleTestCase):
    def test_dash_in_optional_ticker_stat_is_treated_as_missing(self) -> None:
        service = WallexMarketService(session=Mock())
        service.session.get.return_value = response_with(
            {
                "success": True,
                "result": {
                    "symbols": {
                        "PPLTONTMN": {
                            "stats": {
                                "lastPrice": "95000000",
                                "bidPrice": "-",
                                "askPrice": "-",
                                "24h_highPrice": "-",
                                "24h_lowPrice": "-",
                                "24h_volume": "-",
                            }
                        }
                    }
                },
            }
        )
        ticker = service.get_ticker("PPLTONTMN")
        self.assertEqual(str(ticker.last_price), "95000000")
        self.assertIsNone(ticker.bid_price)
        self.assertIsNone(ticker.ask_price)

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from trading.models import BotConfiguration
from trading.services.market_data import MarketDataCollectionService, MarketDataResult
from trading.services.wallex import WallexMarketService
from trading.services.worker import WorkerHeartbeatService


class Command(BaseCommand):
    help = "Collect Wallex OHLCV candles and order-book snapshots."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--symbols", nargs="+", type=str)

    def handle(self, *args: object, **options: object) -> None:
        worker_name: str = "market-data-worker"
        WorkerHeartbeatService.started(worker_name)
        try:
            self._collect(options)
        except Exception as exc:
            WorkerHeartbeatService.failed(worker_name, exc)
            raise
        WorkerHeartbeatService.succeeded(worker_name)

    def _collect(self, options: dict[str, object]) -> None:
        configured: BotConfiguration | None = BotConfiguration.objects.filter(
            name="default"
        ).first()
        raw_symbols: list[str] | None = options.get("symbols")
        symbols: tuple[str, ...] = (
            tuple(raw_symbols)
            if raw_symbols
            else tuple(configured.symbols) if configured else settings.PAPER_BOT_SYMBOLS
        )
        api_key: str = (
            configured.get_wallex_api_key() if configured else settings.WALLEX_API_KEY
        )
        stale_after_hours: int = (
            configured.market_data_stale_hours
            if configured
            else settings.MARKET_DATA_STALE_HOURS
        )
        service = MarketDataCollectionService(
            WallexMarketService(api_key=api_key),
            stale_after_hours=stale_after_hours,
        )
        results: tuple[MarketDataResult, ...] = service.collect(symbols)
        for result in results:
            if result.error:
                self.stderr.write(f"{result.symbol} error={result.error}")
            else:
                self.stdout.write(
                    f"{result.symbol} candles_saved={result.candles_saved} order_book=stored"
                )

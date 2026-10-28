from django.core.management.base import BaseCommand, CommandParser

from trading.models import BotConfiguration
from trading.services.paper_trading import PaperBotResult, PaperTradingService
from trading.services.worker import WorkerHeartbeatService


class Command(BaseCommand):
    help = "Fetch Wallex market data and run one paper-trading cycle."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--symbols", nargs="+", type=str)

    def handle(self, *args: object, **options: object) -> None:
        worker_name: str = "paper-trading-worker"
        WorkerHeartbeatService.started(worker_name)
        try:
            self._run(options)
        except Exception as exc:
            WorkerHeartbeatService.failed(worker_name, exc)
            raise
        WorkerHeartbeatService.succeeded(worker_name)

    def _run(self, options: dict[str, object]) -> None:
        raw_symbols: list[str] | None = options.get("symbols")
        configuration: BotConfiguration | None = BotConfiguration.objects.filter(
            name="default"
        ).first()
        if configuration is not None and not configuration.enabled:
            self.stdout.write(
                self.style.WARNING("Paper bot is disabled in dashboard settings.")
            )
            return
        symbols: tuple[str, ...] | None = (
            tuple(raw_symbols)
            if raw_symbols
            else tuple(configuration.symbols) if configuration else None
        )
        service: PaperTradingService = (
            PaperTradingService.from_configuration(configuration)
            if configuration
            else PaperTradingService()
        )
        results: tuple[PaperBotResult, ...] = service.run(symbols)
        for result in results:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{result.symbol} price={result.price} action={result.action} "
                    f"trade_id={result.trade_id or '-'} reason={result.reason}"
                )
            )

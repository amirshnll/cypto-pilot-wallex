from django.core.management.base import BaseCommand, CommandParser, CommandError

from trading.models import BotConfiguration
from trading.services.backtesting import BacktestResult, BacktestingService


class Command(BaseCommand):
    help = "Run an expanding walk-forward backtest and compare it with buy-and-hold."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--symbols", nargs="+", type=str)
        parser.add_argument("--resolution", default="60", type=str)
        parser.add_argument("--train-size", default=100, type=int)
        parser.add_argument("--test-size", default=50, type=int)

    def handle(self, *args: object, **options: object) -> None:
        configuration: BotConfiguration | None = BotConfiguration.objects.filter(
            name="default"
        ).first()
        if configuration is None:
            raise CommandError("Default bot configuration does not exist.")
        symbols: list[str] = options["symbols"] or list(configuration.symbols)
        service: BacktestingService = BacktestingService(configuration)
        succeeded: int = 0
        for symbol in symbols:
            try:
                result: BacktestResult = service.run(
                    symbol.upper(),
                    options["resolution"],
                    options["train_size"],
                    options["test_size"],
                )
            except ValueError as exc:
                self.stderr.write(self.style.WARNING(str(exc)))
                continue
            succeeded += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"{result.symbol} return={result.total_return:.2%} buy_hold={result.buy_hold_return:.2%} "
                    f"excess={result.excess_return:.2%} drawdown={result.maximum_drawdown:.2%} "
                    f"trades={result.trade_count} folds={result.fold_count} run_id={result.run_id}"
                )
            )
        if not succeeded:
            raise CommandError(
                "No backtest ran; collect more OHLCV candles or reduce window sizes."
            )

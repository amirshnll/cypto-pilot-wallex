from django.core.management.base import BaseCommand, CommandError, CommandParser

from trading.models import BotConfiguration
from trading.services.optimization import (
    OptimizationResult,
    StrategyOptimizationService,
)


class Command(BaseCommand):
    help = "Optimize strategy composition with train/validation/test splits and regime detection."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--symbols", nargs="+", type=str)
        parser.add_argument("--resolution", default="60", type=str)

    def handle(self, *args: object, **options: object) -> None:
        configuration = BotConfiguration.objects.filter(name="default").first()
        if configuration is None:
            raise CommandError("Default bot configuration does not exist.")
        symbols: list[str] = options["symbols"] or list(configuration.symbols)
        service = StrategyOptimizationService(configuration)
        completed = 0
        for symbol in symbols:
            try:
                result: OptimizationResult = service.optimize(
                    symbol.upper(), options["resolution"]
                )
            except ValueError as exc:
                self.stderr.write(self.style.WARNING(str(exc)))
                continue
            completed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"{result.symbol} validation={result.validation_return:.2%} test={result.test_return:.2%} "
                    f"overfit_gap={result.overfit_gap:.2%} stability={result.stability_score:.2%} "
                    f"regime={result.market_regime} run_id={result.run_id}"
                )
            )
        if completed == 0:
            raise CommandError("No optimization completed.")

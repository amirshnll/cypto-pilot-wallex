from django.core.management.base import BaseCommand, CommandError, CommandParser

from trading.models import BotConfiguration
from trading.services.machine_learning import MLResult, MachineLearningPipeline


class Command(BaseCommand):
    help = "Build time-series datasets, train ML models, evaluate them and detect feature drift."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--symbols", nargs="+", type=str)
        parser.add_argument("--resolution", default="60", type=str)
        parser.add_argument("--horizon", default=3, type=int)

    def handle(self, *args: object, **options: object) -> None:
        configuration = BotConfiguration.objects.filter(name="default").first()
        if configuration is None:
            raise CommandError("Default bot configuration does not exist.")
        symbols: list[str] = options["symbols"] or list(configuration.symbols)
        completed = 0
        for symbol in symbols:
            try:
                result: MLResult = MachineLearningPipeline().train(
                    symbol.upper(), options["resolution"], options["horizon"]
                )
            except ValueError as exc:
                self.stderr.write(self.style.WARNING(str(exc)))
                continue
            completed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"{result.symbol} rows={result.dataset_size} accuracy={result.test_accuracy:.2%} "
                    f"f1={result.test_f1:.3f} auc={result.test_auc:.3f} drift={result.drift_score:.3f} "
                    f"drift_detected={result.drift_detected} probability_up={result.latest_probability_up:.2%} run_id={result.run_id}"
                )
            )
        if not completed:
            raise CommandError("No ML model completed.")

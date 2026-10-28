import json

from django.core.management.base import BaseCommand, CommandParser

from trading.models import BotConfiguration
from trading.services.commodity_optimization import CommodityWalkForwardOptimizer


class Command(BaseCommand):
    help = "Walk-forward tune the shared commodity strategy profile."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args: object, **options: object) -> None:
        configuration = BotConfiguration.objects.get(name="default")
        result = CommodityWalkForwardOptimizer(configuration).optimize(
            tuple(configuration.symbols), apply=bool(options["apply"])
        )
        self.stdout.write(
            json.dumps(
                {
                    "parameters": result.parameters,
                    "score": result.score,
                    "baseline_score": result.baseline_score,
                    "eligible_symbols": result.eligible_symbols,
                    "candidate_count": result.candidate_count,
                    "fold_count": len(result.folds),
                    "applied": bool(options["apply"]),
                },
                ensure_ascii=False,
                default=str,
            )
        )

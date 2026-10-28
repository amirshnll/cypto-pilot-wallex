from django.core.management.base import BaseCommand, CommandError

from trading.models import PaperPortfolio, PerformanceSnapshot
from trading.services.performance import PerformanceAnalysisService


class Command(BaseCommand):
    help = "Calculate and persist paper portfolio performance metrics."

    def handle(self, *args: object, **options: object) -> None:
        portfolio: PaperPortfolio | None = PaperPortfolio.objects.filter(
            name="Wallex Paper Bot TMN"
        ).first()
        if portfolio is None:
            raise CommandError("Paper portfolio does not exist yet.")
        snapshot: PerformanceSnapshot = PerformanceAnalysisService().record_portfolio(
            portfolio
        )
        factor: str = (
            str(snapshot.profit_factor) if snapshot.profit_factor is not None else "N/A"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"net_profit={snapshot.net_profit} win_rate={snapshot.win_rate:.2%} "
                f"profit_factor={factor} drawdown={snapshot.maximum_drawdown:.2%} "
                f"sharpe={snapshot.sharpe_ratio:.3f} sortino={snapshot.sortino_ratio:.3f}"
            )
        )

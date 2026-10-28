import json
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.conf import settings
from django.utils import timezone

from trading.models import BotConfiguration, MarketCandle
from trading.services.candles import last_closed_open_time
from trading.services.entry_research import VARIANTS
from trading.services.portfolio_research import replay


class Command(BaseCommand):
    help = "Research-only shared-wallet comparison; reads data and emits JSON, never enables filters."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--isolated-copy",
            action="store_true",
            help="Required acknowledgement: use an isolated database copy.",
        )

    def handle(self, *args: object, **options: object) -> None:
        if not options["isolated_copy"]:
            raise CommandError("Run against an isolated DB copy with --isolated-copy")
        config = BotConfiguration.objects.get(name="default")
        datasets = {
            s: list(
                MarketCandle.objects.filter(
                    symbol=s,
                    resolution="60",
                    opened_at__lte=last_closed_open_time("60"),
                ).order_by("opened_at")
            )
            for s in config.symbols
            if s.endswith("TMN")
        }
        datasets = {s: cs for s, cs in datasets.items() if len(cs) >= 180}
        if not datasets:
            raise CommandError("No markets have 180 hourly candles")
        timeline = sorted({c.opened_at for cs in datasets.values() for c in cs})
        excluded = [
            s
            for s, cs in datasets.items()
            if cs[-1].opened_at < timeline[-1] - timedelta(hours=3)
        ]
        datasets = {s: cs for s, cs in datasets.items() if s not in excluded}
        start = timeline[100]
        split = timeline[100 + int((len(timeline) - 100) * 0.6)]
        windows = {
            "development": (start, timeline[timeline.index(split) - 1]),
            "validation": (split, timeline[-1]),
        }
        results = []
        signal_cache = {}
        for window, (begin, end) in windows.items():
            for multiplier in (Decimal("1"), Decimal("2")):
                for variant in VARIANTS:
                    row = replay(
                        config,
                        datasets,
                        begin,
                        end,
                        variant,
                        cost_multiplier=multiplier,
                        signal_cache=signal_cache,
                    )
                    row["window"] = window
                    results.append(row)
        payload = {
            "captured_at": timezone.now().isoformat(),
            "schema_version": 1,
            "configuration": {
                field: str(getattr(config, field))
                for field in (
                    "risk_level",
                    "risk_per_trade_fraction",
                    "maximum_total_risk_fraction",
                    "maximum_symbol_allocation_fraction",
                    "maximum_crypto_allocation_fraction",
                    "commodity_allocation_cap_fraction",
                    "minimum_order_tmn",
                    "stop_loss_fraction",
                    "take_profit_fraction",
                    "trailing_stop_fraction",
                    "paper_fee_fraction",
                    "paper_slippage_bps",
                    "maximum_drawdown_fraction",
                    "maximum_open_positions",
                    "symbol_loss_streak_limit",
                    "symbol_loss_limit_fraction",
                    "symbol_halt_days",
                    "enabled_strategies",
                    "strategy_weights",
                    "commodity_enabled_strategies",
                    "commodity_strategy_weights",
                    "consensus_threshold",
                    "commodity_consensus_threshold",
                )
            },
            "data": {
                s: {
                    "count": len(cs),
                    "first": cs[0].opened_at.isoformat(),
                    "last": cs[-1].opened_at.isoformat(),
                }
                for s, cs in datasets.items()
            },
            "excluded_stale_at_end": excluded,
            "predeclared_rules": {
                "trend": "last complete UTC 4h close > SMA20; SMA5 > SMA20; SMA20 rising",
                "cost": "prior hourly ATR14 >= 2 * estimated round-trip friction",
                "spread_assumption_bps": 10,
                "split": "first 60% development, final 40% chronological validation; flat start each window",
                "acceptance": "validation return positive, profit factor >= 1.2, >= 30 closed positions, drawdown <= 5%, positive return under 2x cost; no automatic activation",
            },
            "limitations": [
                "Historical market path is already partly known; validation is not a genuinely unseen future holdout.",
                "OHLC intrabar ordering and historical depth are unavailable; fills use stated spread/slippage assumptions.",
                "Current settings are replayed throughout; historical universe membership is not reconstructed.",
                "Universe excludes markets stale at the snapshot end; this can introduce survivorship bias.",
                "All variants share one wallet and identical market ordering; partial hourly gaps are excluded from entry signals.",
                "ATR is a movement proxy, not an expected profit estimate; no fitted prediction is claimed.",
            ],
            "results": results,
        }
        self.stdout.write(json.dumps(payload, default=str))

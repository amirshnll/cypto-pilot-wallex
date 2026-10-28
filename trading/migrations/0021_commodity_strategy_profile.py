from decimal import Decimal

import django.core.validators
from django.db import migrations, models
import trading.models


class Migration(migrations.Migration):
    dependencies = [("trading", "0020_symbol_risk_halts")]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_fast_period",
            field=models.PositiveSmallIntegerField(default=5),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_slow_period",
            field=models.PositiveSmallIntegerField(default=20),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_rsi_period",
            field=models.PositiveSmallIntegerField(default=14),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_rsi_buy_ceiling",
            field=models.DecimalField(decimal_places=3, default=70, max_digits=6),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_rsi_sell_floor",
            field=models.DecimalField(decimal_places=3, default=70, max_digits=6),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_enabled_strategies",
            field=models.JSONField(default=trading.models.default_enabled_strategies),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_strategy_weights",
            field=models.JSONField(
                default=trading.models.default_commodity_strategy_weights
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_consensus_threshold",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.50"),
                max_digits=4,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_optimization_report",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

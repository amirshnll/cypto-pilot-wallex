from decimal import Decimal

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("trading", "0019_high_risk_default")]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="symbol_halt_days",
            field=models.PositiveSmallIntegerField(
                default=7,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(365),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="symbol_loss_limit_fraction",
            field=models.DecimalField(
                decimal_places=5,
                default=Decimal("0.05"),
                max_digits=6,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.00001")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="symbol_loss_streak_limit",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.CreateModel(
            name="SymbolRiskState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("symbol", models.CharField(max_length=30)),
                ("consecutive_losses", models.PositiveSmallIntegerField(default=0)),
                (
                    "cycle_realized_pnl",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "halted_until",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "halt_reason",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("last_trade_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="symbol_risk_states",
                        to="trading.paperportfolio",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("portfolio", "symbol"), name="unique_symbol_risk_state"
                    )
                ],
            },
        ),
        migrations.AlterField(
            model_name="riskevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("stop_loss", "Stop loss"),
                    ("take_profit", "Take profit"),
                    ("trailing_stop", "Trailing stop"),
                    ("drawdown_halt", "Drawdown halt"),
                    ("emergency_stop", "Emergency stop"),
                    ("position_limit", "Position limit"),
                    ("symbol_halt", "Symbol halt"),
                ],
                max_length=20,
            ),
        ),
    ]

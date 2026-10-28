import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0009_botconfiguration_consensus_threshold_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="emergency_stop",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="maximum_drawdown_fraction",
            field=models.DecimalField(
                decimal_places=5,
                default=Decimal("0.15"),
                max_digits=6,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="maximum_open_positions",
            field=models.PositiveSmallIntegerField(default=4),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="risk_halt_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="risk_halted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="risk_halted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="stop_loss_fraction",
            field=models.DecimalField(
                decimal_places=5,
                default=Decimal("0.03"),
                max_digits=6,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="take_profit_fraction",
            field=models.DecimalField(
                decimal_places=5,
                default=Decimal("0.06"),
                max_digits=6,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("10")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="trailing_stop_fraction",
            field=models.DecimalField(
                decimal_places=5,
                default=Decimal("0.025"),
                max_digits=6,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="paperposition",
            name="highest_price",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="paperposition",
            name="opened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="paperposition",
            name="stop_loss_price",
            field=models.DecimalField(
                blank=True, decimal_places=12, max_digits=30, null=True
            ),
        ),
        migrations.AddField(
            model_name="paperposition",
            name="take_profit_price",
            field=models.DecimalField(
                blank=True, decimal_places=12, max_digits=30, null=True
            ),
        ),
        migrations.AddField(
            model_name="paperposition",
            name="trailing_stop_price",
            field=models.DecimalField(
                blank=True, decimal_places=12, max_digits=30, null=True
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="execution_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.CreateModel(
            name="RiskEvent",
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
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("stop_loss", "Stop loss"),
                            ("take_profit", "Take profit"),
                            ("trailing_stop", "Trailing stop"),
                            ("drawdown_halt", "Drawdown halt"),
                            ("emergency_stop", "Emergency stop"),
                            ("position_limit", "Position limit"),
                        ],
                        max_length=20,
                    ),
                ),
                ("symbol", models.CharField(blank=True, default="", max_length=30)),
                (
                    "price",
                    models.DecimalField(
                        blank=True, decimal_places=12, max_digits=30, null=True
                    ),
                ),
                ("details", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="risk_events",
                        to="trading.paperportfolio",
                    ),
                ),
                (
                    "position",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="trading.paperposition",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]

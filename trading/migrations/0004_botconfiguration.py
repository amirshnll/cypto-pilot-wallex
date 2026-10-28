import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0003_paperportfoliosnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotConfiguration",
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
                    "name",
                    models.CharField(default="default", max_length=100, unique=True),
                ),
                ("enabled", models.BooleanField(default=False)),
                ("symbols", models.JSONField(default=list)),
                (
                    "initial_balance",
                    models.DecimalField(
                        decimal_places=12, default=10000, max_digits=30
                    ),
                ),
                (
                    "trade_fraction",
                    models.DecimalField(
                        decimal_places=5,
                        default=Decimal("0.10"),
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(
                                Decimal("0.00001")
                            ),
                            django.core.validators.MaxValueValidator(Decimal("1")),
                        ],
                    ),
                ),
                ("fast_period", models.PositiveSmallIntegerField(default=5)),
                ("slow_period", models.PositiveSmallIntegerField(default=20)),
                ("rsi_period", models.PositiveSmallIntegerField(default=14)),
                (
                    "rsi_buy_ceiling",
                    models.DecimalField(decimal_places=3, default=70, max_digits=6),
                ),
                (
                    "rsi_sell_floor",
                    models.DecimalField(decimal_places=3, default=70, max_digits=6),
                ),
                (
                    "wallex_api_key_encrypted",
                    models.BinaryField(blank=True, default=bytes),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

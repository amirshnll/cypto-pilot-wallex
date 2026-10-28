import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trading", "0021_commodity_strategy_profile")]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="market_data_stale_hours",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(168),
                ],
            ),
        ),
        migrations.CreateModel(
            name="MarketHealthState",
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
                ("symbol", models.CharField(max_length=30, unique=True)),
                ("trading_enabled", models.BooleanField(default=False)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("last_candle_at", models.DateTimeField(blank=True, null=True)),
                ("disabled_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("symbol",)},
        ),
    ]

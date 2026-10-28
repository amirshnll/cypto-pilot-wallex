import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaperPortfolio",
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
                    models.CharField(
                        default="Wallex Paper Bot", max_length=100, unique=True
                    ),
                ),
                ("quote_asset", models.CharField(default="USDT", max_length=15)),
                (
                    "initial_balance",
                    models.DecimalField(decimal_places=12, max_digits=30),
                ),
                ("cash_balance", models.DecimalField(decimal_places=12, max_digits=30)),
                (
                    "realized_pnl",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="MarketSnapshot",
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
                ("symbol", models.CharField(db_index=True, max_length=30)),
                ("last_price", models.DecimalField(decimal_places=12, max_digits=30)),
                (
                    "bid_price",
                    models.DecimalField(
                        blank=True, decimal_places=12, max_digits=30, null=True
                    ),
                ),
                (
                    "ask_price",
                    models.DecimalField(
                        blank=True, decimal_places=12, max_digits=30, null=True
                    ),
                ),
                (
                    "volume_24h",
                    models.DecimalField(
                        blank=True, decimal_places=12, max_digits=30, null=True
                    ),
                ),
                ("captured_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ("-captured_at",),
                "indexes": [
                    models.Index(
                        fields=["symbol", "captured_at"],
                        name="trading_mar_symbol_8ae1fa_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="TradingSignal",
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
                    "action",
                    models.CharField(
                        choices=[("buy", "Buy"), ("sell", "Sell"), ("hold", "Hold")],
                        max_length=4,
                    ),
                ),
                (
                    "fast_sma",
                    models.DecimalField(
                        blank=True, decimal_places=12, max_digits=30, null=True
                    ),
                ),
                (
                    "slow_sma",
                    models.DecimalField(
                        blank=True, decimal_places=12, max_digits=30, null=True
                    ),
                ),
                (
                    "rsi",
                    models.DecimalField(
                        blank=True, decimal_places=6, max_digits=10, null=True
                    ),
                ),
                ("reason", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="signals",
                        to="trading.marketsnapshot",
                    ),
                ),
                (
                    "strategy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signals",
                        to="trading.strategy",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PaperPosition",
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
                (
                    "quantity",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "average_entry_price",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="positions",
                        to="trading.paperportfolio",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("portfolio", "symbol"), name="unique_paper_position"
                    )
                ],
            },
        ),
    ]

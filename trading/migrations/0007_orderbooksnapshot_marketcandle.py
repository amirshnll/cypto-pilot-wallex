from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0006_botconfiguration_risk_level"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderBookSnapshot",
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
                (
                    "best_bid",
                    models.DecimalField(decimal_places=12, max_digits=30, null=True),
                ),
                (
                    "best_ask",
                    models.DecimalField(decimal_places=12, max_digits=30, null=True),
                ),
                (
                    "spread",
                    models.DecimalField(decimal_places=12, max_digits=30, null=True),
                ),
                (
                    "spread_bps",
                    models.DecimalField(decimal_places=8, max_digits=20, null=True),
                ),
                (
                    "bid_depth",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "ask_depth",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                ("bids", models.JSONField(default=list)),
                ("asks", models.JSONField(default=list)),
                ("captured_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ("-captured_at",),
            },
        ),
        migrations.CreateModel(
            name="MarketCandle",
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
                ("resolution", models.CharField(max_length=10)),
                ("opened_at", models.DateTimeField(db_index=True)),
                ("open_price", models.DecimalField(decimal_places=12, max_digits=30)),
                ("high_price", models.DecimalField(decimal_places=12, max_digits=30)),
                ("low_price", models.DecimalField(decimal_places=12, max_digits=30)),
                ("close_price", models.DecimalField(decimal_places=12, max_digits=30)),
                ("volume", models.DecimalField(decimal_places=12, max_digits=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-opened_at",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("symbol", "resolution", "opened_at"),
                        name="unique_market_candle",
                    )
                ],
            },
        ),
    ]

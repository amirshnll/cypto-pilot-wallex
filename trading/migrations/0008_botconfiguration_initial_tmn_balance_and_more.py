import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0007_orderbooksnapshot_marketcandle"),
    ]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="initial_tmn_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="paperportfoliosnapshot",
            name="position_values",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="paperportfoliosnapshot",
            name="wallet_balances",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="paperposition",
            name="base_asset",
            field=models.CharField(default="", max_length=15),
        ),
        migrations.AddField(
            model_name="paperposition",
            name="quote_asset",
            field=models.CharField(default="USDT", max_length=15),
        ),
        migrations.AddField(
            model_name="trade",
            name="notional",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="trade",
            name="portfolio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="trades",
                to="trading.paperportfolio",
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="quote_asset",
            field=models.CharField(default="USDT", max_length=15),
        ),
        migrations.CreateModel(
            name="PaperWallet",
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
                ("asset", models.CharField(max_length=15)),
                (
                    "initial_balance",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "balance",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "realized_pnl",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wallets",
                        to="trading.paperportfolio",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PaperLedgerEntry",
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
                    "entry_type",
                    models.CharField(
                        choices=[
                            ("initial", "Initial funding"),
                            ("buy", "Paper buy"),
                            ("sell", "Paper sell"),
                            ("adjustment", "Adjustment"),
                        ],
                        max_length=12,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=12, max_digits=30)),
                (
                    "balance_after",
                    models.DecimalField(decimal_places=12, max_digits=30),
                ),
                ("description", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "trade",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="trading.trade",
                    ),
                ),
                (
                    "wallet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ledger_entries",
                        to="trading.paperwallet",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="paperwallet",
            constraint=models.UniqueConstraint(
                fields=("portfolio", "asset"), name="unique_paper_wallet"
            ),
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0002_paperportfolio_marketsnapshot_tradingsignal_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaperPortfolioSnapshot",
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
                ("cash_balance", models.DecimalField(decimal_places=12, max_digits=30)),
                (
                    "positions_value",
                    models.DecimalField(decimal_places=12, max_digits=30),
                ),
                ("total_equity", models.DecimalField(decimal_places=12, max_digits=30)),
                ("realized_pnl", models.DecimalField(decimal_places=12, max_digits=30)),
                ("captured_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="snapshots",
                        to="trading.paperportfolio",
                    ),
                ),
            ],
            options={
                "ordering": ("-captured_at",),
            },
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0012_backtestrun_backtestfold"),
    ]

    operations = [
        migrations.AddField(
            model_name="backtestrun",
            name="gross_loss",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="backtestrun",
            name="gross_profit",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="backtestrun",
            name="net_profit",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="backtestrun",
            name="profit_factor",
            field=models.DecimalField(
                blank=True, decimal_places=8, max_digits=20, null=True
            ),
        ),
        migrations.AddField(
            model_name="backtestrun",
            name="sharpe_ratio",
            field=models.DecimalField(decimal_places=8, default=0, max_digits=20),
        ),
        migrations.AddField(
            model_name="backtestrun",
            name="sortino_ratio",
            field=models.DecimalField(decimal_places=8, default=0, max_digits=20),
        ),
        migrations.CreateModel(
            name="PerformanceSnapshot",
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
                ("total_equity", models.DecimalField(decimal_places=12, max_digits=30)),
                ("net_profit", models.DecimalField(decimal_places=12, max_digits=30)),
                ("total_return", models.DecimalField(decimal_places=10, max_digits=20)),
                (
                    "gross_profit",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "gross_loss",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "win_rate",
                    models.DecimalField(decimal_places=8, default=0, max_digits=10),
                ),
                (
                    "profit_factor",
                    models.DecimalField(
                        blank=True, decimal_places=8, max_digits=20, null=True
                    ),
                ),
                (
                    "maximum_drawdown",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "sharpe_ratio",
                    models.DecimalField(decimal_places=8, default=0, max_digits=20),
                ),
                (
                    "sortino_ratio",
                    models.DecimalField(decimal_places=8, default=0, max_digits=20),
                ),
                ("closed_trades", models.PositiveIntegerField(default=0)),
                ("captured_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="performance_snapshots",
                        to="trading.paperportfolio",
                    ),
                ),
            ],
            options={
                "ordering": ("-captured_at",),
            },
        ),
    ]

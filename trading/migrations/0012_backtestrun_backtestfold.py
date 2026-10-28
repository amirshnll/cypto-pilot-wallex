import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0011_botconfiguration_paper_fee_fraction_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BacktestRun",
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
                ("resolution", models.CharField(default="60", max_length=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=12,
                    ),
                ),
                (
                    "initial_balance",
                    models.DecimalField(decimal_places=12, max_digits=30),
                ),
                (
                    "final_equity",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "total_return",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "buy_hold_return",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "excess_return",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "maximum_drawdown",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                ("trade_count", models.PositiveIntegerField(default=0)),
                (
                    "win_rate",
                    models.DecimalField(decimal_places=8, default=0, max_digits=10),
                ),
                ("fold_count", models.PositiveIntegerField(default=0)),
                ("parameters", models.JSONField(default=dict)),
                ("equity_curve", models.JSONField(default=list)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ("-started_at",),
            },
        ),
        migrations.CreateModel(
            name="BacktestFold",
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
                ("fold_number", models.PositiveIntegerField()),
                ("train_start", models.DateTimeField()),
                ("train_end", models.DateTimeField()),
                ("test_start", models.DateTimeField()),
                ("test_end", models.DateTimeField()),
                ("start_equity", models.DecimalField(decimal_places=12, max_digits=30)),
                ("end_equity", models.DecimalField(decimal_places=12, max_digits=30)),
                (
                    "return_fraction",
                    models.DecimalField(decimal_places=10, max_digits=20),
                ),
                (
                    "buy_hold_return",
                    models.DecimalField(decimal_places=10, max_digits=20),
                ),
                (
                    "maximum_drawdown",
                    models.DecimalField(decimal_places=10, max_digits=20),
                ),
                ("trade_count", models.PositiveIntegerField(default=0)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="folds",
                        to="trading.backtestrun",
                    ),
                ),
            ],
            options={
                "ordering": ("fold_number",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("run", "fold_number"), name="unique_backtest_fold"
                    )
                ],
            },
        ),
    ]

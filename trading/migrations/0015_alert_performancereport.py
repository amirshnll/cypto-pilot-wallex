from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0014_workerheartbeat"),
    ]

    operations = [
        migrations.CreateModel(
            name="Alert",
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
                    "alert_type",
                    models.CharField(
                        choices=[
                            ("trade", "Trade"),
                            ("risk", "Risk"),
                            ("worker", "Worker"),
                            ("drawdown", "Drawdown"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("info", "Info"),
                            ("warning", "Warning"),
                            ("critical", "Critical"),
                        ],
                        default="info",
                        max_length=10,
                    ),
                ),
                ("title", models.CharField(max_length=160)),
                ("message", models.TextField()),
                ("source_key", models.CharField(max_length=160, unique=True)),
                ("metadata", models.JSONField(default=dict)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="PerformanceReport",
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
                    "period",
                    models.CharField(
                        choices=[("daily", "Daily"), ("weekly", "Weekly")],
                        max_length=10,
                    ),
                ),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                ("trade_count", models.PositiveIntegerField(default=0)),
                ("buy_count", models.PositiveIntegerField(default=0)),
                ("sell_count", models.PositiveIntegerField(default=0)),
                (
                    "traded_notional",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "fees_paid",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "net_profit",
                    models.DecimalField(decimal_places=12, default=0, max_digits=30),
                ),
                (
                    "total_return",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "maximum_drawdown",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
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
                    "sharpe_ratio",
                    models.DecimalField(decimal_places=8, default=0, max_digits=20),
                ),
                (
                    "sortino_ratio",
                    models.DecimalField(decimal_places=8, default=0, max_digits=20),
                ),
                ("summary", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("-period_end",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("period", "period_start"),
                        name="unique_performance_report_period",
                    )
                ],
            },
        ),
    ]

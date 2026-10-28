from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0015_alert_performancereport"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketRegimeSnapshot",
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
                    "regime",
                    models.CharField(
                        choices=[
                            ("trend_up", "Uptrend"),
                            ("trend_down", "Downtrend"),
                            ("ranging", "Ranging"),
                            ("volatile", "Volatile"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "trend_strength",
                    models.DecimalField(decimal_places=10, max_digits=20),
                ),
                ("volatility", models.DecimalField(decimal_places=10, max_digits=20)),
                ("confidence", models.DecimalField(decimal_places=8, max_digits=10)),
                ("detected_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ("-detected_at",),
            },
        ),
        migrations.CreateModel(
            name="StrategyOptimizationRun",
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
                ("candle_count", models.PositiveIntegerField(default=0)),
                ("candidate_count", models.PositiveIntegerField(default=0)),
                ("best_parameters", models.JSONField(default=dict)),
                (
                    "train_return",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "validation_return",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "test_return",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "test_drawdown",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "overfit_gap",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                (
                    "stability_score",
                    models.DecimalField(decimal_places=10, default=0, max_digits=12),
                ),
                ("market_regime", models.CharField(default="unknown", max_length=30)),
                ("sensitivity", models.JSONField(default=list)),
                ("top_candidates", models.JSONField(default=list)),
                ("error", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("-started_at",),
            },
        ),
    ]

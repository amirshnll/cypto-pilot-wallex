from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0016_marketregimesnapshot_strategyoptimizationrun"),
    ]

    operations = [
        migrations.CreateModel(
            name="MLTrainingRun",
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
                    "model_type",
                    models.CharField(default="logistic_regression", max_length=40),
                ),
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
                ("horizon", models.PositiveSmallIntegerField(default=3)),
                ("dataset_size", models.PositiveIntegerField(default=0)),
                ("train_size", models.PositiveIntegerField(default=0)),
                ("validation_size", models.PositiveIntegerField(default=0)),
                ("test_size", models.PositiveIntegerField(default=0)),
                ("feature_names", models.JSONField(default=list)),
                ("coefficients", models.JSONField(default=dict)),
                ("scaler", models.JSONField(default=dict)),
                ("validation_metrics", models.JSONField(default=dict)),
                ("test_metrics", models.JSONField(default=dict)),
                ("feature_importance", models.JSONField(default=dict)),
                ("drift_report", models.JSONField(default=dict)),
                (
                    "drift_score",
                    models.DecimalField(decimal_places=10, default=0, max_digits=20),
                ),
                ("drift_detected", models.BooleanField(default=False)),
                (
                    "latest_probability_up",
                    models.DecimalField(
                        blank=True, decimal_places=8, max_digits=10, null=True
                    ),
                ),
                ("error", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("-started_at",),
            },
        ),
        migrations.CreateModel(
            name="MLFeatureRow",
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
                ("opened_at", models.DateTimeField(db_index=True)),
                ("horizon", models.PositiveSmallIntegerField(default=3)),
                ("features", models.JSONField(default=dict)),
                ("target_up", models.BooleanField()),
                (
                    "future_return",
                    models.DecimalField(decimal_places=10, max_digits=20),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("opened_at",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("symbol", "opened_at", "horizon"),
                        name="unique_ml_feature_row",
                    )
                ],
            },
        ),
    ]

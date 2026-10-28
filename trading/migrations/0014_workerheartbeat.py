from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0013_backtestrun_gross_loss_backtestrun_gross_profit_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkerHeartbeat",
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
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("healthy", "Healthy"),
                            ("error", "Error"),
                        ],
                        default="running",
                        max_length=10,
                    ),
                ),
                ("last_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("cycles", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={
                "ordering": ("name",),
            },
        ),
    ]

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0010_botconfiguration_emergency_stop_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="paper_fee_fraction",
            field=models.DecimalField(
                decimal_places=6,
                default=Decimal("0.001"),
                max_digits=7,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("0.1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="paper_latency_ms",
            field=models.PositiveIntegerField(default=500),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="paper_max_book_participation",
            field=models.DecimalField(
                decimal_places=5,
                default=Decimal("0.10"),
                max_digits=6,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.00001")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="paper_slippage_bps",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("5"),
                max_digits=8,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("10000")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="fee_amount",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="trade",
            name="liquidity_fraction",
            field=models.DecimalField(decimal_places=10, default=1, max_digits=12),
        ),
        migrations.AddField(
            model_name="trade",
            name="reference_price",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="trade",
            name="requested_quantity",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="trade",
            name="simulated_latency_ms",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="trade",
            name="slippage_amount",
            field=models.DecimalField(decimal_places=12, default=0, max_digits=30),
        ),
        migrations.AddField(
            model_name="trade",
            name="slippage_bps",
            field=models.DecimalField(decimal_places=8, default=0, max_digits=20),
        ),
        migrations.AlterField(
            model_name="trade",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("filled", "Filled"),
                    ("partial", "Partially filled"),
                    ("cancelled", "Cancelled"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=10,
            ),
        ),
    ]

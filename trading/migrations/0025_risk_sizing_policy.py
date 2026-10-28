from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trading", "0024_configuration_activity_dates")]
    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="risk_per_trade_fraction",
            field=models.DecimalField(
                max_digits=6,
                decimal_places=5,
                default=Decimal("0.005"),
                validators=[
                    MinValueValidator(Decimal("0.00001")),
                    MaxValueValidator(Decimal("0.05")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="maximum_total_risk_fraction",
            field=models.DecimalField(
                max_digits=6,
                decimal_places=5,
                default=Decimal("0.02"),
                validators=[
                    MinValueValidator(Decimal("0.00001")),
                    MaxValueValidator(Decimal("0.20")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="maximum_symbol_allocation_fraction",
            field=models.DecimalField(
                max_digits=6,
                decimal_places=5,
                default=Decimal("0.25"),
                validators=[
                    MinValueValidator(Decimal("0.00001")),
                    MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="maximum_crypto_allocation_fraction",
            field=models.DecimalField(
                max_digits=6,
                decimal_places=5,
                default=Decimal("0.60"),
                validators=[
                    MinValueValidator(Decimal("0.00001")),
                    MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="minimum_order_tmn",
            field=models.DecimalField(
                max_digits=20,
                decimal_places=2,
                default=Decimal("50000"),
                validators=[MinValueValidator(Decimal("0"))],
            ),
        ),
    ]

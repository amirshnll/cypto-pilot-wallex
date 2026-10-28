from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trading", "0022_market_health_state")]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="commodity_allocation_cap_fraction",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.20"),
                max_digits=4,
                validators=[
                    MinValueValidator(Decimal("0")),
                    MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
    ]

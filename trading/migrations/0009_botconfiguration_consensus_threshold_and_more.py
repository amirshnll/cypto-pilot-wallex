import django.core.validators
import trading.models
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0008_botconfiguration_initial_tmn_balance_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="consensus_threshold",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.35"),
                max_digits=4,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="enabled_strategies",
            field=models.JSONField(default=trading.models.default_enabled_strategies),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="strategy_weights",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="tradingsignal",
            name="component_signals",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="tradingsignal",
            name="confidence",
            field=models.DecimalField(decimal_places=5, default=0, max_digits=6),
        ),
    ]

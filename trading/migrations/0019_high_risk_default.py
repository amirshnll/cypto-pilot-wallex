from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trading", "0018_switch_default_markets_to_tmn")]

    operations = [
        migrations.AlterField(
            model_name="botconfiguration",
            name="risk_level",
            field=models.CharField(
                choices=[("low", "Low risk"), ("medium", "Balanced"), ("high", "High risk")],
                default="high",
                max_length=10,
            ),
        ),
    ]

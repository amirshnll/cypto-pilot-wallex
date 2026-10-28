from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0005_remove_botconfiguration_trade_fraction_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="risk_level",
            field=models.CharField(
                choices=[
                    ("low", "Low risk"),
                    ("medium", "Balanced"),
                    ("high", "High risk"),
                ],
                default="medium",
                max_length=10,
            ),
        ),
    ]

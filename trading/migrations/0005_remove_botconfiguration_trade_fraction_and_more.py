from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0004_botconfiguration"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="botconfiguration",
            name="trade_fraction",
        ),
        migrations.AlterField(
            model_name="botconfiguration",
            name="initial_balance",
            field=models.DecimalField(decimal_places=12, default=100, max_digits=30),
        ),
    ]

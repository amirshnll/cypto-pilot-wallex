from decimal import Decimal

from django.db import migrations

TMN_SYMBOLS = [
    "BTCTMN",
    "ETHTMN",
    "SHIBTMN",
    "DOGETMN",
    "SOLTMN",
    "XRPTMN",
    "ADATMN",
    "TRXTMN",
    "USDTTMN",
    "BNBTMN",
]


def switch_to_tmn(apps, schema_editor):
    BotConfiguration = apps.get_model("trading", "BotConfiguration")
    BotConfiguration.objects.filter(name="default").update(
        symbols=TMN_SYMBOLS,
        initial_tmn_balance=Decimal("21330000"),
    )


class Migration(migrations.Migration):
    dependencies = [("trading", "0017_mltrainingrun_mlfeaturerow")]
    operations = [migrations.RunPython(switch_to_tmn, migrations.RunPython.noop)]

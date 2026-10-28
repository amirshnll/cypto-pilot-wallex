from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trading", "0023_commodity_allocation_cap")]
    operations = [
        migrations.AddField(
            model_name="botconfiguration",
            name="last_code_release_at",
            field=models.DateTimeField(
                null=True, blank=True, editable=False, verbose_name="Latest code release"
            ),
        ),
        migrations.AddField(
            model_name="botconfiguration",
            name="last_results_review_at",
            field=models.DateTimeField(
                null=True, blank=True, editable=False, verbose_name="Latest results review"
            ),
        ),
    ]

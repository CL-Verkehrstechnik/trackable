from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0005_org_branding"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="holidays_enabled",
            field=models.BooleanField(
                default=True,
                verbose_name="Holidays enabled",
                help_text="When disabled, holidays are not deducted from vacation workday calculations.",
            ),
        ),
    ]

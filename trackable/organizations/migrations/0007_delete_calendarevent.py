from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0006_organization_holidays_enabled"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CalendarEvent",
        ),
    ]

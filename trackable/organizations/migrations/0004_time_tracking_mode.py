from django.db import migrations, models


def migrate_timer_only_to_mode(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    for org in Organization.objects.all():
        org.time_tracking_mode = "restricted" if org.timer_only_mode else "classic"
        org.save()


def reverse_migrate(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    for org in Organization.objects.all():
        org.timer_only_mode = org.time_tracking_mode == "restricted"
        org.save()


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_organization_cal_end_time_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="time_tracking_mode",
            field=models.CharField(
                default="classic",
                max_length=20,
                choices=[
                    ("classic", "Classic – Full CRUD access"),
                    (
                        "restricted",
                        "Restricted – Timer only (except managers)",
                    ),
                ],
                verbose_name="Time tracking mode",
            ),
        ),
        migrations.RunPython(migrate_timer_only_to_mode, reverse_migrate),
        migrations.RemoveField(
            model_name="organization",
            name="timer_only_mode",
        ),
    ]

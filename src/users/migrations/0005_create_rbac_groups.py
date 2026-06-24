from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Clinical_Admin")
    Group.objects.get_or_create(name="Data_Analyst")
    Group.objects.get_or_create(name="IT Manager")


def remove_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Clinical_Admin", "Data_Analyst", "IT Manager"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_userprofile"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]

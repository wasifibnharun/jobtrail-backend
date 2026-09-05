import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "applications",
            "0003_migrate_existing_companies",
        ),
    ]

    operations = [
        migrations.RemoveField(
            model_name="application",
            name="company",
        ),
        migrations.RenameField(
            model_name="application",
            old_name="company_record",
            new_name="company",
        ),
        migrations.AlterField(
            model_name="application",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="applications",
                to="applications.company",
            ),
        ),
    ]
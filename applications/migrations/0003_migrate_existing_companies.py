from django.db import migrations


def migrate_companies_forward(apps, schema_editor):
    Application = apps.get_model("applications", "Application")
    Company = apps.get_model("applications", "Company")

    for application in Application.objects.all().iterator():
        company_name = application.company.strip()

        company, _ = Company.objects.get_or_create(
            owner_id=application.owner_id,
            name=company_name,
        )

        application.company_record_id = company.id
        application.save(update_fields=["company_record"])


def migrate_companies_backward(apps, schema_editor):
    Application = apps.get_model("applications", "Application")

    for application in (
        Application.objects.select_related("company_record")
        .all()
        .iterator()
    ):
        if application.company_record_id:
            application.company = application.company_record.name
            application.save(update_fields=["company"])


class Migration(migrations.Migration):

    dependencies = [
        (
            "applications",
            "0002_company_application_company_record_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            migrate_companies_forward,
            migrate_companies_backward,
        ),
    ]
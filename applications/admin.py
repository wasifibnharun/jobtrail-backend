from django.contrib import admin

from .models import Application, Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "location",
        "website",
        "created_at",
    )
    search_fields = ("name", "location", "owner__username")
    readonly_fields = ("created_at",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "position",
        "company",
        "owner",
        "status",
        "job_type",
        "applied_on",
        "created_at",
    )
    list_filter = ("status", "job_type", "created_at")
    search_fields = (
        "company__name",
        "position",
        "owner__username",
    )
    readonly_fields = ("created_at", "updated_at")
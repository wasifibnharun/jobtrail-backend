from django.contrib import admin

from .models import Application


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
    search_fields = ("company", "position", "owner__username")
    readonly_fields = ("created_at", "updated_at")
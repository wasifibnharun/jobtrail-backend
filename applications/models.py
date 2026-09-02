from django.conf import settings
from django.db import models


class Application(models.Model):
    class Status(models.TextChoices):
        WISHLIST = "WISHLIST", "Wishlist"
        APPLIED = "APPLIED", "Applied"
        INTERVIEW = "INTERVIEW", "Interview"
        OFFER = "OFFER", "Offer"
        REJECTED = "REJECTED", "Rejected"

    class JobType(models.TextChoices):
        ONSITE = "ONSITE", "Onsite"
        REMOTE = "REMOTE", "Remote"
        HYBRID = "HYBRID", "Hybrid"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    company = models.CharField(max_length=120)
    position = models.CharField(max_length=120)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WISHLIST,
    )
    job_type = models.CharField(
        max_length=20,
        choices=JobType.choices,
        default=JobType.ONSITE,
    )
    applied_on = models.DateField(null=True, blank=True)
    expected_salary = models.PositiveIntegerField(null=True, blank=True)
    job_link = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.position} at {self.company}"
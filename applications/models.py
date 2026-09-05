from django.conf import settings
from django.db import models


class Company(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="companies",
    )
    name = models.CharField(max_length=120)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_company_per_owner",
            )
        ]

    def __str__(self):
        return self.name

class Interview(models.Model):
    class Mode(models.TextChoices):
        ONSITE = "ONSITE", "Onsite"
        VIDEO = "VIDEO", "Video"
        PHONE = "PHONE", "Phone"

    class Result(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"

    application = models.ForeignKey(
        "Application",
        on_delete=models.CASCADE,
        related_name="interviews",
    )
    round_name = models.CharField(max_length=100)
    scheduled_at = models.DateTimeField()
    mode = models.CharField(
        max_length=20,
        choices=Mode.choices,
        default=Mode.VIDEO,
    )
    result = models.CharField(
        max_length=20,
        choices=Result.choices,
        default=Result.PENDING,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return (
            f"{self.round_name}: "
            f"{self.application.position}"
        )

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
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="applications",
    )
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
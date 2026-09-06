from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from rest_framework import serializers

from .models import Application, Company, Interview, validate_cv_size


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class CompanySerializer(serializers.ModelSerializer):
    applications_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "website",
            "location",
            "applications_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "applications_count",
            "created_at",
        ]

    def get_applications_count(self, company) -> int:
        annotated_count = getattr(
            company,
            "applications_count",
            None,
        )

        if annotated_count is not None:
            return annotated_count

        return company.applications.count()

    def validate_name(self, value):
        name = value.strip()
        request = self.context["request"]

        companies = Company.objects.filter(
            owner=request.user,
            name__iexact=name,
        )

        if self.instance:
            companies = companies.exclude(pk=self.instance.pk)

        if companies.exists():
            raise serializers.ValidationError(
                "You already have a company with this name."
            )

        return name

class ApplicationSerializer(serializers.ModelSerializer):
    company = serializers.CharField(max_length=120)
    needs_follow_up = serializers.SerializerMethodField()
    cv = serializers.FileField(
        write_only=True,
        required=False,
        allow_null=True,
        validators=[
            FileExtensionValidator(["pdf", "doc", "docx"]),
            validate_cv_size,
        ],
    )
    has_cv = serializers.SerializerMethodField()
    cv_download_url = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "owner",
            "company",
            "position",
            "status",
            "job_type",
            "applied_on",
            "expected_salary",
            "job_link",
            "notes",
            "cv",
            "has_cv",
            "cv_download_url",
            "needs_follow_up",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "needs_follow_up",
            "has_cv",
            "cv_download_url",
            "created_at",
            "updated_at",
        ]

    def validate_company(self, value):
        company_name = value.strip()

        if not company_name:
            raise serializers.ValidationError(
                "This field may not be blank."
            )

        return company_name

    def resolve_company(self, owner, company_name):
        company = Company.objects.filter(
            owner=owner,
            name__iexact=company_name,
        ).first()

        if company:
            return company

        return Company.objects.create(
            owner=owner,
            name=company_name,
        )

    def create(self, validated_data):
        company_name = validated_data.pop("company")
        owner = validated_data["owner"]
        validated_data["company"] = self.resolve_company(
            owner,
            company_name,
        )

        return super().create(validated_data)

    def update(self, instance, validated_data):
        company_name = validated_data.pop("company", None)
        replacing_cv = "cv" in validated_data
        old_cv_name = instance.cv.name if instance.cv else ""
        old_cv_storage = instance.cv.storage if instance.cv else None

        if company_name is not None:
            validated_data["company"] = self.resolve_company(
                instance.owner,
                company_name,
            )

        updated_application = super().update(instance, validated_data)

        if (
            replacing_cv
            and old_cv_name
            and old_cv_name != updated_application.cv.name
            and old_cv_storage
        ):
            old_cv_storage.delete(old_cv_name)

        return updated_application

    def get_needs_follow_up(self, application) -> bool:
        if (
            application.status != Application.Status.APPLIED
            or application.applied_on is None
        ):
            return False

        follow_up_cutoff = timezone.localdate() - timedelta(days=14)

        return application.applied_on < follow_up_cutoff

    def get_has_cv(self, application) -> bool:
        return bool(application.cv)

    def get_cv_download_url(self, application) -> str | None:
        if not application.cv:
            return None

        request = self.context.get("request")
        path = f"/api/applications/{application.pk}/cv/"

        return request.build_absolute_uri(path) if request else path

class InterviewSerializer(serializers.ModelSerializer):
    position = serializers.CharField(
        source="application.position",
        read_only=True,
    )
    company = serializers.CharField(
        source="application.company.name",
        read_only=True,
    )

    class Meta:
        model = Interview
        fields = [
            "id",
            "application",
            "position",
            "company",
            "round_name",
            "scheduled_at",
            "mode",
            "result",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "position",
            "company",
            "created_at",
            "updated_at",
        ]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")

        if request and request.user.is_authenticated:
            fields["application"].queryset = (
                Application.objects.filter(owner=request.user)
            )
        else:
            fields["application"].queryset = (
                Application.objects.none()
            )

        return fields

class MonthlyApplicationSerializer(serializers.Serializer):
    month = serializers.CharField(read_only=True)
    count = serializers.IntegerField(read_only=True)


class StatsSerializer(serializers.Serializer):
    total = serializers.IntegerField(read_only=True)
    wishlist = serializers.IntegerField(read_only=True)
    applied = serializers.IntegerField(read_only=True)
    interview = serializers.IntegerField(read_only=True)
    offer = serializers.IntegerField(read_only=True)
    rejected = serializers.IntegerField(read_only=True)
    monthly = MonthlyApplicationSerializer(many=True, read_only=True)

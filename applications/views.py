from django.contrib.auth import get_user_model
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from .models import Application, Company, Interview
from .serializers import (
    ApplicationSerializer,
    RegisterSerializer,
    CompanySerializer,
    InterviewSerializer,
    StatsSerializer
)
from django.utils import timezone
from pathlib import Path

from django.http import FileResponse
from django.utils.text import slugify
from rest_framework import status
from rest_framework.exceptions import NotFound
import csv
from django.http import FileResponse, HttpResponse
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema


User = get_user_model()


class LoginView(TokenObtainPairView):
    throttle_scope = "auth"

class RefreshTokenView(TokenRefreshView):
    throttle_scope = "auth"

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "auth"

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.none()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "location"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return (
            Company.objects.filter(owner=self.request.user)
            .annotate(applications_count=Count("applications"))
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise ValidationError(
                {
                    "detail": (
                        "This company cannot be deleted while it has "
                        "applications."
                    )
                }
            ) from error

class InterviewViewSet(viewsets.ModelViewSet):
    queryset = Interview.objects.none()
    serializer_class = InterviewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "application",
        "mode",
        "result",
    ]
    search_fields = [
        "round_name",
        "application__position",
        "application__company__name",
    ]
    ordering_fields = [
        "scheduled_at",
        "created_at",
    ]
    ordering = ["scheduled_at"]

    def get_queryset(self):
        return (
            Interview.objects.filter(
                application__owner=self.request.user
            )
            .select_related(
                "application",
                "application__company",
            )
        )

    @action(detail=False, methods=["get"])
    def upcoming(self, request):
        interviews = (
            self.filter_queryset(self.get_queryset())
            .filter(
                scheduled_at__gte=timezone.now(),
                result=Interview.Result.PENDING,
            )
            .order_by("scheduled_at")
        )

        page = self.paginate_queryset(interviews)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(interviews, many=True)
        return Response(serializer.data)

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.none()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "job_type"]
    search_fields = ["company__name", "position"]
    ordering_fields = [
        "created_at",
        "applied_on",
        "expected_salary",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Application.objects.filter(owner=self.request.user)
            .select_related("company")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        cv_name = instance.cv.name if instance.cv else ""
        cv_storage = instance.cv.storage if instance.cv else None

        instance.delete()

        if cv_name and cv_storage:
            cv_storage.delete(cv_name)

    @extend_schema(
        methods=["GET"],
        description="Download the application's private CV attachment.",
        responses={
            (200, "application/octet-stream"): OpenApiTypes.BINARY,
            404: OpenApiResponse(
                description="No CV attachment was found.",
            ),
        },
    )
    @extend_schema(
        methods=["DELETE"],
        description="Delete the application's CV attachment.",
        responses={
            204: None,
            404: OpenApiResponse(
                description="No CV attachment was found.",
            ),
        },
    )
    @action(detail=True, methods=["get", "delete"], url_path="cv")
    def cv(self, request, pk=None):
        application = self.get_object()

        if not application.cv:
            raise NotFound("No CV is attached to this application.")

        if request.method == "DELETE":
            application.cv.delete(save=False)
            application.cv = ""
            application.save(update_fields=["cv"])

            return Response(status=status.HTTP_204_NO_CONTENT)

        extension = Path(application.cv.name).suffix.lower()
        filename = (
            f"{slugify(application.company.name)}-"
            f"{slugify(application.position)}-cv{extension}"
        )

        return FileResponse(
            application.cv.open("rb"),
            as_attachment=True,
            filename=filename,
        )

    @extend_schema(
        description=(
            "Export the authenticated user's applications as CSV. "
            "List filters, search, and ordering are supported."
        ),
        responses={
            (200, "text/csv"): OpenApiTypes.BINARY,
        },
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        applications = self.filter_queryset(self.get_queryset())

        response = HttpResponse(
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            'attachment; filename="jobtrail-applications.csv"'
        )

        # UTF-8 BOM helps Excel display Unicode company names correctly.
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow(
            [
                "Company",
                "Position",
                "Status",
                "Job Type",
                "Applied On",
                "Expected Salary",
                "Job Link",
                "Notes",
                "Created At",
                "Updated At",
            ]
        )

        for application in applications.iterator():
            writer.writerow(
                [
                    application.company.name,
                    application.position,
                    application.get_status_display(),
                    application.get_job_type_display(),
                    application.applied_on or "",
                    (
                        application.expected_salary
                        if application.expected_salary is not None
                        else ""
                    ),
                    application.job_link,
                    application.notes,
                    application.created_at.isoformat(),
                    application.updated_at.isoformat(),
                ]
            )

        return response


class StatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StatsSerializer)
    def get(self, request):
        rows = (
            Application.objects.filter(owner=request.user)
            .values("status")
            .annotate(count=Count("id"))
        )

        counts = {
            status.value.lower(): 0
            for status in Application.Status
        }

        for row in rows:
            counts[row["status"].lower()] = row["count"]

        return Response(
            {
                "total": sum(counts.values()),
                **counts,
            }
        )
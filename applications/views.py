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
    InterviewSerializer
)
from django.utils import timezone


User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

class CompanyViewSet(viewsets.ModelViewSet):
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


class StatsView(APIView):
    permission_classes = [IsAuthenticated]

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
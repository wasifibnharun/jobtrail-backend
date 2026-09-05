from django.contrib.auth import get_user_model
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError
from .models import Application, Company
from .serializers import (
    ApplicationSerializer,
    RegisterSerializer,
    CompanySerializer
)


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
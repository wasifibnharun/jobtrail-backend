from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
  ApplicationViewSet,
  RegisterView,
  StatsView,
  CompanyViewSet,
  InterviewViewSet,
  LoginView,
  RefreshTokenView
)


router = DefaultRouter()
router.register(
    "applications",
    ApplicationViewSet,
    basename="application",
)
router.register(
    "companies",
    CompanyViewSet,
    basename="company",
)
router.register(
    "interviews",
    InterviewViewSet,
    basename="interview",
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path(
        "token/refresh/",
        RefreshTokenView.as_view(),
        name="token-refresh",
    ),
    path("stats/", StatsView.as_view(), name="stats"),
    path("", include(router.urls)),
]
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
  ApplicationViewSet,
  RegisterView,
  StatsView,
  CompanyViewSet
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

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path("stats/", StatsView.as_view(), name="stats"),
    path("", include(router.urls)),
]
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Application


User = get_user_model()


class AuthenticationTests(APITestCase):
    def test_registration_hashes_password(self):
        payload = {
            "username": "wasif",
            "email": "wasif@example.com",
            "password": "strongpass123",
        }

        response = self.client.post(
            reverse("register"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)

        user = User.objects.get(username="wasif")
        self.assertEqual(user.email, payload["email"])
        self.assertTrue(user.check_password(payload["password"]))

    def test_registration_validation(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "wasif",
                "password": "12345",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertIn("password", response.data)

    def test_login_refresh_and_invalid_login(self):
        User.objects.create_user(
            username="wasif",
            email="wasif@example.com",
            password="strongpass123",
        )

        login_response = self.client.post(
            reverse("login"),
            {
                "username": "wasif",
                "password": "strongpass123",
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)

        refresh_response = self.client.post(
            reverse("token-refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

        invalid_response = self.client.post(
            reverse("login"),
            {
                "username": "wasif",
                "password": "wrong-password",
            },
            format="json",
        )

        self.assertEqual(
            invalid_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_duplicate_username_returns_drf_error(self):
        User.objects.create_user(
            username="wasif",
            email="first@example.com",
            password="strongpass123",
        )

        response = self.client.post(
            reverse("register"),
            {
                "username": "wasif",
                "email": "second@example.com",
                "password": "strongpass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertEqual(
            str(response.data["username"][0]),
            "A user with that username already exists.",
        )

    def test_access_token_authenticates_application_endpoint(self):
        User.objects.create_user(
            username="jwt-user",
            email="jwt@example.com",
            password="strongpass123",
        )

        login_response = self.client.post(
            reverse("login"),
            {
                "username": "jwt-user",
                "password": "strongpass123",
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {login_response.data['access']}"
            )
        )

        response = self.client.get(reverse("application-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)


class ApplicationAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="strongpass123",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="strongpass123",
        )
        self.client.force_authenticate(user=self.user)

    def create_application(self, owner=None, **changes):
        data = {
            "owner": owner or self.user,
            "company": "Brain Station 23",
            "position": "Backend Developer",
            "status": Application.Status.WISHLIST,
            "job_type": Application.JobType.ONSITE,
            "expected_salary": 45000,
        }
        data.update(changes)
        return Application.objects.create(**data)

    def test_unauthenticated_requests_return_401(self):
        self.client.force_authenticate(user=None)

        list_response = self.client.get(reverse("application-list"))
        stats_response = self.client.get(reverse("stats"))

        self.assertEqual(
            list_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            stats_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_application_crud_and_automatic_owner(self):
        create_response = self.client.post(
            reverse("application-list"),
            {
                "owner": self.other_user.id,
                "company": "Brain Station 23",
                "position": "Backend Developer",
                "status": "APPLIED",
                "job_type": "REMOTE",
                "expected_salary": 45000,
            },
            format="json",
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )

        application = Application.objects.get(
            id=create_response.data["id"]
        )
        self.assertEqual(application.owner, self.user)

        detail_url = reverse(
            "application-detail",
            args=[application.id],
        )

        retrieve_response = self.client.get(detail_url)
        self.assertEqual(
            retrieve_response.status_code,
            status.HTTP_200_OK,
        )

        update_response = self.client.patch(
            detail_url,
            {
                "company": "Updated Company",
                "owner": self.other_user.id,
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        application.refresh_from_db()
        self.assertEqual(application.company, "Updated Company")
        self.assertEqual(application.owner, self.user)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(
            delete_response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            Application.objects.filter(id=application.id).exists()
        )

    def test_users_can_only_access_their_own_applications(self):
        own_application = self.create_application()
        other_application = self.create_application(
            owner=self.other_user,
            company="Other Company",
        )

        self.client.force_authenticate(user=self.other_user)

        list_response = self.client.get(reverse("application-list"))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(
            list_response.data["results"][0]["id"],
            other_application.id,
        )

        detail_response = self.client.get(
            reverse(
                "application-detail",
                args=[own_application.id],
            )
        )

        self.assertEqual(
            detail_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_filtering_searching_and_ordering(self):
        first = self.create_application(
            company="Brain Station 23",
            status=Application.Status.INTERVIEW,
            job_type=Application.JobType.REMOTE,
            expected_salary=50000,
        )
        second = self.create_application(
            company="Acme Limited",
            status=Application.Status.APPLIED,
            job_type=Application.JobType.ONSITE,
            expected_salary=30000,
        )
        third = self.create_application(
            company="Data Systems",
            status=Application.Status.OFFER,
            job_type=Application.JobType.REMOTE,
            expected_salary=70000,
        )

        status_response = self.client.get(
            reverse("application-list"),
            {"status": "INTERVIEW"},
        )
        self.assertEqual(status_response.data["count"], 1)
        self.assertEqual(
            status_response.data["results"][0]["id"],
            first.id,
        )

        type_response = self.client.get(
            reverse("application-list"),
            {"job_type": "REMOTE"},
        )
        self.assertEqual(type_response.data["count"], 2)

        search_response = self.client.get(
            reverse("application-list"),
            {"search": "brain"},
        )
        self.assertEqual(search_response.data["count"], 1)

        ordering_response = self.client.get(
            reverse("application-list"),
            {"ordering": "expected_salary"},
        )
        ordered_ids = [
            item["id"]
            for item in ordering_response.data["results"]
        ]
        self.assertEqual(
            ordered_ids,
            [second.id, first.id, third.id],
        )

        combined_response = self.client.get(
            reverse("application-list"),
            {
                "status": "INTERVIEW",
                "job_type": "REMOTE",
                "search": "BRAIN",
                "ordering": "-applied_on",
                "page": 1,
            },
        )

        self.assertEqual(combined_response.status_code, status.HTTP_200_OK)
        self.assertEqual(combined_response.data["count"], 1)
        self.assertEqual(
            combined_response.data["results"][0]["id"],
            first.id,
        )

    def test_pagination_and_invalid_page(self):
        for number in range(11):
            self.create_application(company=f"Company {number}")

        first_page = self.client.get(reverse("application-list"))
        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(first_page.data["count"], 11)
        self.assertEqual(len(first_page.data["results"]), 10)
        self.assertIsNotNone(first_page.data["next"])

        second_page = self.client.get(
            reverse("application-list"),
            {"page": 2},
        )
        self.assertEqual(len(second_page.data["results"]), 1)

        invalid_page = self.client.get(
            reverse("application-list"),
            {"page": 999},
        )
        self.assertEqual(
            invalid_page.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_stats_use_one_query_and_include_zero_values(self):
        self.create_application(status=Application.Status.APPLIED)
        self.create_application(status=Application.Status.APPLIED)
        self.create_application(status=Application.Status.INTERVIEW)
        self.create_application(
            owner=self.other_user,
            status=Application.Status.OFFER,
        )

        with self.assertNumQueries(1):
            response = self.client.get(reverse("stats"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "total": 3,
                "wishlist": 0,
                "applied": 2,
                "interview": 1,
                "offer": 0,
                "rejected": 0,
            },
        )
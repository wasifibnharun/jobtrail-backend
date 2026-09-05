from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Application, Company, Interview
from django.utils import timezone
from datetime import timedelta


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
        application_owner = owner or self.user
        company_name = changes.pop("company", "Brain Station 23")

        company, _ = Company.objects.get_or_create(
            owner=application_owner,
            name=company_name,
        )

        data = {
            "owner": application_owner,
            "company": company,
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

        self.assertEqual(
            retrieve_response.data["company"],
            "Brain Station 23",
        )
        self.assertEqual(application.company.name, "Brain Station 23")
        self.assertEqual(
            Company.objects.filter(owner=self.user).count(),
            1,
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
        self.assertEqual(application.company.name, "Updated Company")
        self.assertEqual(application.owner, self.user)
        self.assertEqual(
            Company.objects.filter(owner=self.user).count(),
            2,
        )

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

    def test_needs_follow_up_is_computed_from_status_and_date(self):
        overdue = self.create_application(
            status=Application.Status.APPLIED,
            applied_on=timezone.localdate() - timedelta(days=15),
        )
        exactly_fourteen_days = self.create_application(
            company="Fourteen Day Company",
            status=Application.Status.APPLIED,
            applied_on=timezone.localdate() - timedelta(days=14),
        )
        wishlist = self.create_application(
            company="Wishlist Company",
            status=Application.Status.WISHLIST,
            applied_on=timezone.localdate() - timedelta(days=30),
        )

        responses = {
            application.id: self.client.get(
                reverse("application-detail", args=[application.id])
            ).data
            for application in [
                overdue,
                exactly_fourteen_days,
                wishlist,
            ]
        }

        self.assertTrue(responses[overdue.id]["needs_follow_up"])
        self.assertFalse(
            responses[exactly_fourteen_days.id]["needs_follow_up"]
        )
        self.assertFalse(responses[wishlist.id]["needs_follow_up"])

class CompanyAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="company-owner",
            email="company-owner@example.com",
            password="strongpass123",
        )
        self.other_user = User.objects.create_user(
            username="other-company-owner",
            email="other-company@example.com",
            password="strongpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_companies_are_owner_scoped_with_application_counts(self):
        company = Company.objects.create(
            owner=self.user,
            name="Brain Station 23",
            website="https://brainstation-23.com",
            location="Dhaka",
        )
        Company.objects.create(
            owner=self.other_user,
            name="Private Company",
        )
        Application.objects.create(
            owner=self.user,
            company=company,
            position="Backend Developer",
        )

        response = self.client.get(reverse("company-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            "Brain Station 23",
        )
        self.assertEqual(
            response.data["results"][0]["applications_count"],
            1,
        )

    def test_company_crud_validation_and_protected_deletion(self):
        create_response = self.client.post(
            reverse("company-list"),
            {
                "name": "Chaldal",
                "website": "https://chaldal.com",
                "location": "Dhaka",
                "owner": self.other_user.id,
            },
            format="json",
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )

        company = Company.objects.get(id=create_response.data["id"])
        self.assertEqual(company.owner, self.user)

        duplicate_response = self.client.post(
            reverse("company-list"),
            {"name": "chaldal"},
            format="json",
        )
        self.assertEqual(
            duplicate_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        Application.objects.create(
            owner=self.user,
            company=company,
            position="Python Developer",
        )

        delete_response = self.client.delete(
            reverse("company-detail", args=[company.id])
        )
        self.assertEqual(
            delete_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertTrue(Company.objects.filter(id=company.id).exists())

    def test_other_users_company_returns_404(self):
        company = Company.objects.create(
            owner=self.other_user,
            name="Other Company",
        )

        response = self.client.get(
            reverse("company-detail", args=[company.id])
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

class InterviewAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="interview-owner",
            email="interview-owner@example.com",
            password="strongpass123",
        )
        self.other_user = User.objects.create_user(
            username="other-interview-owner",
            email="other-interview@example.com",
            password="strongpass123",
        )

        self.company = Company.objects.create(
            owner=self.user,
            name="JobTrail Labs",
        )
        self.application = Application.objects.create(
            owner=self.user,
            company=self.company,
            position="Django Developer",
        )

        self.other_company = Company.objects.create(
            owner=self.other_user,
            name="Private Labs",
        )
        self.other_application = Application.objects.create(
            owner=self.other_user,
            company=self.other_company,
            position="Private Position",
        )

        self.client.force_authenticate(user=self.user)

    def create_interview(self, application=None, **changes):
        data = {
            "application": application or self.application,
            "round_name": "Technical Interview",
            "scheduled_at": timezone.now() + timedelta(days=2),
            "mode": Interview.Mode.VIDEO,
            "result": Interview.Result.PENDING,
        }
        data.update(changes)
        return Interview.objects.create(**data)

    def test_interview_crud_and_application_ownership(self):
        create_response = self.client.post(
            reverse("interview-list"),
            {
                "application": self.application.id,
                "round_name": "HR Screening",
                "scheduled_at": (
                    timezone.now() + timedelta(days=1)
                ).isoformat(),
                "mode": "PHONE",
                "result": "PENDING",
                "notes": "Discuss availability.",
            },
            format="json",
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            create_response.data["company"],
            "JobTrail Labs",
        )

        interview_id = create_response.data["id"]
        detail_url = reverse("interview-detail", args=[interview_id])

        update_response = self.client.patch(
            detail_url,
            {"result": "PASSED"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["result"], "PASSED")

        forbidden_create = self.client.post(
            reverse("interview-list"),
            {
                "application": self.other_application.id,
                "round_name": "Private Interview",
                "scheduled_at": (
                    timezone.now() + timedelta(days=1)
                ).isoformat(),
            },
            format="json",
        )
        self.assertEqual(
            forbidden_create.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        delete_response = self.client.delete(detail_url)
        self.assertEqual(
            delete_response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_other_users_interview_returns_404(self):
        interview = self.create_interview(
            application=self.other_application
        )

        response = self.client.get(
            reverse("interview-detail", args=[interview.id])
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_upcoming_returns_only_future_pending_interviews(self):
        upcoming = self.create_interview()

        self.create_interview(
            scheduled_at=timezone.now() - timedelta(days=1)
        )
        self.create_interview(
            scheduled_at=timezone.now() + timedelta(days=3),
            result=Interview.Result.PASSED,
        )
        self.create_interview(
            application=self.other_application,
            scheduled_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(reverse("interview-upcoming"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            upcoming.id,
        )
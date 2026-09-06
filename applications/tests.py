from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import MAX_CV_SIZE, Application, Company, Interview
from django.utils import timezone
from datetime import timedelta

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase,override_settings

import csv
from io import StringIO


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

    def test_auth_endpoints_are_throttled(self):
        url = reverse("register")
        payload = {
            "username": "throttle-user",
            "email": "throttle@example.com",
            "password": "strongpass123",
        }
        client_ip = "192.0.2.25"

        for _ in range(10):
            response = self.client.post(
                url,
                payload,
                format="json",
                REMOTE_ADDR=client_ip,
            )
            self.assertNotEqual(
                response.status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        throttled_response = self.client.post(
            url,
            payload,
            format="json",
            REMOTE_ADDR=client_ip,
        )

        self.assertEqual(
            throttled_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
        self.assertIn("detail", throttled_response.data)


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

        export_response = self.client.get(
            reverse("application-export")
        )

        self.assertEqual(
            export_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
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

    def test_csv_export_respects_filters_ordering_and_owner(self):
            first = self.create_application(
                company="Django Labs",
                position="Junior Django Developer",
                status=Application.Status.APPLIED,
                expected_salary=40000,
            )
            second = self.create_application(
                company="Django Works",
                position="Senior Django Developer",
                status=Application.Status.APPLIED,
                expected_salary=80000,
            )
    
            self.create_application(
                company="Rejected Company",
                position="Django Developer",
                status=Application.Status.REJECTED,
            )
            self.create_application(
                owner=self.other_user,
                company="Private Django Company",
                position="Hidden Django Developer",
                status=Application.Status.APPLIED,
            )
    
            response = self.client.get(
                reverse("application-export"),
                {
                    "status": "APPLIED",
                    "search": "django",
                    "ordering": "expected_salary",
                },
            )
    
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(
                response["Content-Type"].startswith("text/csv")
            )
            self.assertIn(
                "jobtrail-applications.csv",
                response["Content-Disposition"],
            )
    
            content = response.content.decode("utf-8-sig")
            rows = list(csv.reader(StringIO(content)))
    
            self.assertEqual(
                rows[0],
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
                ],
            )
            self.assertEqual(len(rows), 3)
            self.assertEqual(
                [row[1] for row in rows[1:]],
                [first.position, second.position],
            )
            self.assertNotIn("Hidden Django Developer", content)
            self.assertNotIn("Rejected Company", content)

    def test_json_responses_use_consistent_envelope(self):
        application = self.create_application()

        success_response = self.client.get(
            reverse("application-list")
        )
        success_body = success_response.json()

        self.assertEqual(
            set(success_body),
            {"success", "message", "data"},
        )
        self.assertTrue(success_body["success"])
        self.assertEqual(
            success_body["message"],
            "Request successful.",
        )
        self.assertEqual(success_body["data"]["count"], 1)
        self.assertEqual(
            success_body["data"]["results"][0]["id"],
            application.id,
        )

        self.client.force_authenticate(user=None)

        error_response = self.client.get(
            reverse("application-list")
        )
        error_body = error_response.json()

        self.assertEqual(
            set(error_body),
            {"success", "message", "data"},
        )
        self.assertFalse(error_body["success"])
        self.assertEqual(
            error_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertIn("detail", error_body["data"])

    def test_board_returns_all_owner_applications_without_pagination(self):
        for number in range(11):
            self.create_application(
                company=f"Board Company {number}",
                position=f"Developer {number}",
            )

        self.create_application(
            owner=self.other_user,
            company="Hidden Board Company",
        )

        response = self.client.get(reverse("application-board"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 11)
        self.assertNotIn(
            "Hidden Board Company",
            {
                application["company"]
                for application in response.data
            },
        )

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

class CVAttachmentAPITests(APITestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory.name
        )
        self.media_override.enable()

        self.user = User.objects.create_user(
            username="cv-owner",
            email="cv-owner@example.com",
            password="strongpass123",
        )
        self.other_user = User.objects.create_user(
            username="other-cv-owner",
            email="other-cv@example.com",
            password="strongpass123",
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def application_payload(self, cv):
        return {
            "company": "JobTrail Labs",
            "position": "Django Developer",
            "status": "APPLIED",
            "job_type": "REMOTE",
            "cv": cv,
        }

    def test_cv_upload_download_and_owner_protection(self):
        content = b"%PDF-1.4 example CV"
        cv = SimpleUploadedFile(
            "resume.pdf",
            content,
            content_type="application/pdf",
        )

        create_response = self.client.post(
            reverse("application-list"),
            self.application_payload(cv),
            format="multipart",
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertTrue(create_response.data["has_cv"])
        self.assertIsNotNone(
            create_response.data["cv_download_url"]
        )

        application = Application.objects.get(
            id=create_response.data["id"]
        )
        self.assertTrue(application.cv.name.endswith(".pdf"))
        self.assertIn(
            f"cvs/user_{self.user.id}/",
            application.cv.name,
        )

        cv_url = reverse("application-cv", args=[application.id])
        download_response = self.client.get(cv_url)

        self.assertEqual(
            download_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            b"".join(download_response.streaming_content),
            content,
        )
        self.assertIn(
            "attachment;",
            download_response["Content-Disposition"],
        )

        self.client.force_authenticate(user=self.other_user)
        forbidden_response = self.client.get(cv_url)

        self.assertEqual(
            forbidden_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cv_extension_and_size_validation(self):
        invalid_extension = SimpleUploadedFile(
            "resume.exe",
            b"not a CV",
            content_type="application/octet-stream",
        )

        extension_response = self.client.post(
            reverse("application-list"),
            self.application_payload(invalid_extension),
            format="multipart",
        )

        self.assertEqual(
            extension_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("cv", extension_response.data)

        oversized = SimpleUploadedFile(
            "large-resume.pdf",
            b"x" * (MAX_CV_SIZE + 1),
            content_type="application/pdf",
        )

        size_response = self.client.post(
            reverse("application-list"),
            self.application_payload(oversized),
            format="multipart",
        )

        self.assertEqual(
            size_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("cv", size_response.data)

    def test_replacing_and_deleting_cv_removes_stored_files(self):
        first_cv = SimpleUploadedFile(
            "first.pdf",
            b"first CV",
            content_type="application/pdf",
        )
        create_response = self.client.post(
            reverse("application-list"),
            self.application_payload(first_cv),
            format="multipart",
        )

        application = Application.objects.get(
            id=create_response.data["id"]
        )
        first_path = Path(application.cv.path)
        self.assertTrue(first_path.exists())

        second_cv = SimpleUploadedFile(
            "second.pdf",
            b"second CV",
            content_type="application/pdf",
        )
        update_response = self.client.patch(
            reverse("application-detail", args=[application.id]),
            {"cv": second_cv},
            format="multipart",
        )

        self.assertEqual(
            update_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(first_path.exists())

        application.refresh_from_db()
        second_path = Path(application.cv.path)
        self.assertTrue(second_path.exists())

        delete_response = self.client.delete(
            reverse("application-detail", args=[application.id])
        )

        self.assertEqual(
            delete_response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(second_path.exists())

class APIDocumentationTests(APITestCase):
    def test_schema_swagger_and_redoc_are_public(self):
        schema_response = self.client.get(
            reverse("schema"),
            {"format": "json"},
        )
        swagger_response = self.client.get(
            reverse("swagger-ui")
        )
        redoc_response = self.client.get(
            reverse("redoc")
        )

        self.assertEqual(
            schema_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            swagger_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            redoc_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("paths", schema_response.data)
        self.assertIn(
            "/api/applications/",
            schema_response.data["paths"],
        )
        self.assertIn(
            "/api/interviews/upcoming/",
            schema_response.data["paths"],
        )

class APIDocumentationTests(APITestCase):
    def test_schema_swagger_and_redoc_are_public(self):
        schema_response = self.client.get(reverse("schema"))
        swagger_response = self.client.get(reverse("swagger-ui"))
        redoc_response = self.client.get(reverse("redoc"))

        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        self.assertEqual(swagger_response.status_code, status.HTTP_200_OK)
        self.assertEqual(redoc_response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "/api/applications/",
            schema_response.data["paths"],
        )


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_is_complete_and_idempotent(self):
        output = StringIO()
        options = {
            "username": "demo-test",
            "email": "demo-test@example.com",
            "password": "DemoPass123!",
            "stdout": output,
        }

        call_command("seed_demo", **options)

        user = User.objects.get(username="demo-test")

        self.assertTrue(user.check_password("DemoPass123!"))
        self.assertEqual(user.companies.count(), 5)
        self.assertEqual(user.applications.count(), 15)
        self.assertEqual(
            Interview.objects.filter(
                application__owner=user
            ).count(),
            3,
        )
        self.assertIn("Seeded demo-test", output.getvalue())

        call_command("seed_demo", **options)

        self.assertEqual(user.companies.count(), 5)
        self.assertEqual(user.applications.count(), 15)
        self.assertEqual(
            Interview.objects.filter(
                application__owner=user
            ).count(),
            3,
        )
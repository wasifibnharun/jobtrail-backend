# JobTrail Backend

JobTrail is a REST API for tracking job applications. Authenticated users can create, view, update, delete, filter, search, and organize their own applications. Each user can only access their own records.

## Technology Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- Simple JWT
- django-filter
- django-cors-headers
- python-decouple

## Features

- User registration with password hashing
- JWT login and token refresh
- Owner-protected application CRUD
- Status and job-type filtering
- Company and position search
- Application ordering
- Ten records per page
- Owner-specific application statistics
- PostgreSQL database
- Automated API tests

## Local Setup

Clone the repository and enter the backend directory:

```powershell
git clone https://github.com/wasifibnharun/jobtrail-backend.git
cd backend
```

Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

Create a PostgreSQL database named `jobtrail`.

Create your environment file from the example:

```powershell
Copy-Item .env.example .env
```

Fill in the real values inside `.env`, then apply migrations:

```powershell
python manage.py migrate
```

Optionally create an administrator:

```powershell
python manage.py createsuperuser
```

Start the development server:

```powershell
python manage.py runserver
```

The API will be available at:

```text
http://127.0.0.1:8000/api/
```

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Private Django secret key | `replace-with-secure-value` |
| `DEBUG` | Enables development debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated permitted hosts | `127.0.0.1,localhost` |
| `DB_NAME` | PostgreSQL database name | `jobtrail` |
| `DB_USER` | PostgreSQL username | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | `your-password` |
| `DB_HOST` | PostgreSQL server hostname | `localhost` |
| `DB_PORT` | PostgreSQL server port | `5432` |

Never commit the real `.env` file.

## API Endpoints

| Method | Endpoint | Authentication | Purpose |
|---|---|---|---|
| `POST` | `/api/register/` | Public | Register a user |
| `POST` | `/api/login/` | Public | Obtain access and refresh tokens |
| `POST` | `/api/token/refresh/` | Public | Obtain a new access token |
| `GET` | `/api/applications/` | Bearer token | List the user's applications |
| `POST` | `/api/applications/` | Bearer token | Create an application |
| `GET` | `/api/applications/{id}/` | Bearer token | Retrieve an application |
| `PUT` | `/api/applications/{id}/` | Bearer token | Replace an application |
| `PATCH` | `/api/applications/{id}/` | Bearer token | Partially update an application |
| `DELETE` | `/api/applications/{id}/` | Bearer token | Delete an application |
| `GET` | `/api/stats/` | Bearer token | Retrieve status counts |

Send authenticated requests with:

```text
Authorization: Bearer <access-token>
```

## Filtering and Ordering

The application list supports these query parameters:

| Parameter | Supported values |
|---|---|
| `status` | `WISHLIST`, `APPLIED`, `INTERVIEW`, `OFFER`, `REJECTED` |
| `job_type` | `ONSITE`, `REMOTE`, `HYBRID` |
| `search` | Case-insensitive company or position text |
| `ordering` | `created_at`, `applied_on`, `expected_salary` |
| `page` | Page number |

Prefix an ordering field with `-` for descending order:

```text
/api/applications/?status=INTERVIEW&search=developer&ordering=-applied_on
```

## Tests

Run all backend tests with:

```powershell
python manage.py test applications -v 2
```

The tests cover registration, JWT authentication, owner isolation, CRUD, filtering, search, ordering, pagination, and statistics.
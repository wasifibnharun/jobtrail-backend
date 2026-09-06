# JobTrail Backend

JobTrail is a PostgreSQL-backed REST API for managing a private job search. Each authenticated user can track companies, applications, interviews, CV attachments, follow-ups, and reporting data without exposing records owned by another user.

## Live Deployment

- Frontend: [jobtrail-bice.vercel.app](https://jobtrail-bice.vercel.app/)
- Backend API: [jobtrail-ghfp.onrender.com/api/](https://jobtrail-ghfp.onrender.com/api/)
- Demo username: `demo`
- Demo password: `DemoPass123!`

## Related Repository

- [JobTrail Frontend](https://github.com/wasifibnharun/jobtrail-frontend)

## Technology Stack

- Python and Django
- Django REST Framework
- PostgreSQL locally and Neon in production
- Simple JWT authentication
- django-filter
- drf-spectacular OpenAPI documentation
- Cloudflare R2 private file storage in production
- Gunicorn and WhiteNoise

## Features

- Registration, JWT login, token refresh, and scoped authentication throttling
- Owner-protected company, application, and interview CRUD
- Search, status and job-type filters, ordering, and pagination
- Upcoming-interview endpoint and activity timeline data
- Automatic follow-up detection for applications older than 14 days
- Private PDF, DOC, and DOCX CV attachments with a 5 MB limit
- Authenticated CV download and deletion
- Filter-aware CSV export
- Unpaginated Kanban board feed
- Status totals and six-month application analytics
- Consistent `{success, message, data}` JSON response envelopes
- Swagger UI, ReDoc, OpenAPI schema, and an importable Postman collection
- Idempotent demo-data management command
- Automated API tests covering ownership and major workflows

## Local Setup

```powershell
git clone https://github.com/wasifibnharun/jobtrail-backend.git
cd jobtrail-backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Create a PostgreSQL database named `jobtrail`, fill in `.env`, then run:

```powershell
python manage.py migrate
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/api/`.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Private Django secret key |
| `DEBUG` | Enables development debug mode |
| `ALLOWED_HOSTS` | Comma-separated permitted hosts |
| `DATABASE_URL` | Production PostgreSQL connection URL; overrides separate DB fields |
| `DB_NAME` | Local PostgreSQL database name |
| `DB_USER` | Local PostgreSQL username |
| `DB_PASSWORD` | Local PostgreSQL password |
| `DB_HOST` | Local PostgreSQL hostname |
| `DB_PORT` | Local PostgreSQL port |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins |
| `USE_R2` | Enables Cloudflare R2 storage |
| `R2_ACCESS_KEY_ID` | R2 API access-key ID |
| `R2_SECRET_ACCESS_KEY` | R2 API secret access key |
| `R2_BUCKET_NAME` | Private R2 bucket name |
| `R2_ENDPOINT_URL` | Account-specific R2 S3 endpoint |

Never commit the real `.env` file.

## Main API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/register/` | Register a user |
| `POST` | `/api/login/` | Obtain access and refresh tokens |
| `POST` | `/api/token/refresh/` | Refresh the access token |
| `GET, POST` | `/api/companies/` | List or create companies |
| `GET, PUT, PATCH, DELETE` | `/api/companies/{id}/` | Manage one company |
| `GET, POST` | `/api/applications/` | List or create applications |
| `GET, PUT, PATCH, DELETE` | `/api/applications/{id}/` | Manage one application |
| `GET` | `/api/applications/board/` | Load all applications for Kanban |
| `GET` | `/api/applications/export/` | Export the filtered list as CSV |
| `GET, DELETE` | `/api/applications/{id}/cv/` | Download or remove a private CV |
| `GET, POST` | `/api/interviews/` | List or create interviews |
| `GET, PUT, PATCH, DELETE` | `/api/interviews/{id}/` | Manage one interview |
| `GET` | `/api/interviews/upcoming/` | List upcoming pending interviews |
| `GET` | `/api/stats/` | Load status totals and monthly analytics |

Send protected requests with `Authorization: Bearer <access-token>`.

## Filtering and Ordering

`/api/applications/`, `/api/applications/board/`, and `/api/applications/export/` support the applicable list query parameters:

| Parameter | Supported values |
| --- | --- |
| `status` | `WISHLIST`, `APPLIED`, `INTERVIEW`, `OFFER`, `REJECTED` |
| `job_type` | `ONSITE`, `REMOTE`, `HYBRID` |
| `search` | Case-insensitive company or position text |
| `ordering` | `created_at`, `applied_on`, `expected_salary` |
| `page` | Page number for the paginated list |

Prefix an ordering field with `-` for descending order, for example:

```text
/api/applications/?status=INTERVIEW&search=developer&ordering=-applied_on
```

## API Documentation

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`
- Generated schema file: `schema.yml`
- Postman collection: `postman/JobTrail.postman_collection.json`

Regenerate and validate the checked-in schema with:

```powershell
python manage.py spectacular --file schema.yml --validate
```

## Demo Data

Create or refresh a local demo account with 5 companies, 15 applications, and 3 interviews:

```powershell
python manage.py seed_demo --password "choose-a-demo-password" --reset
```

Use `--username` and `--email` to override the defaults. Run this command against production only when you intentionally want demo records in that database.

## Tests

```powershell
python manage.py test
```

The test suite covers authentication, owner isolation, companies, applications, interviews, follow-up calculations, CV validation and access, CSV export, Kanban data, analytics, throttling, response envelopes, and the demo command.

## Deployment

The production service uses Render for Django and Neon for PostgreSQL. Configure Render with the Neon `DATABASE_URL` and run migrations during each build:

```text
pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
```

Start the service with:

```text
gunicorn config.wsgi:application
```

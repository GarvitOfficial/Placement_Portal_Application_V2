"""Shared pytest fixtures for the Placement Portal backend test suite.

The app is pointed at a throwaway SQLite database (via DATABASE_URL) *before*
it is imported, so tests never touch the real instance/placement.db.
"""
import os
import sys
import tempfile

# Must happen before `app` is imported.
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db.name}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ.setdefault("FLASK_ENV", "development")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from app import (  # noqa: E402
    Application,
    Company,
    PlacementDrive,
    Student,
    User,
    app as flask_app,
    cache,
    db,
    hash_password,
)

ADMIN_EMAIL = "admin@placement.local"
ADMIN_PASSWORD = "admin"


def _seed_admin():
    if not User.query.filter_by(role="admin").first():
        db.session.add(
            User(username="admin", email=ADMIN_EMAIL, password=hash_password(ADMIN_PASSWORD), role="admin")
        )
        db.session.commit()


@pytest.fixture()
def app():
    flask_app.config["TESTING"] = True
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        _seed_admin()
        try:
            cache.clear()
        except Exception:
            pass
        yield flask_app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


# ── helpers ──────────────────────────────────────────────────────────


def register_student(
    client,
    username="stud",
    email="stud@test.com",
    password="studpass",
    full_name="Test Student",
    cgpa=8.5,
    branch="CSE",
    year=3,
):
    return client.post(
        "/student/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": full_name,
            "cgpa": cgpa,
            "branch": branch,
            "year": year,
        },
    )


def register_company(
    client,
    username="acme",
    email="acme@test.com",
    password="acmepass",
    company_name="Acme Corp",
    website="acme.com",
    departments=("CSE", "ECE"),
    hr_contact="hr@acme.com",
):
    return client.post(
        "/company/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "company_name": company_name,
            "website": website,
            "departments": list(departments),
            "hr_contact": hr_contact,
        },
    )


def login(client, email, password):
    return client.post("/login", json={"email": email, "password": password})


def auth_headers(client, email, password):
    response = login(client, email, password)
    token = response.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def approve_company(company_id):
    company = Company.query.get(company_id)
    company.approved = True
    db.session.commit()


def make_drive(
    company_id,
    job_title="SDE",
    status="Approved",
    cgpa_required=7.0,
    branch_required="CSE,ECE",
    year_required=3,
    deadline="2099-12-31",
):
    drive = PlacementDrive(
        company_id=company_id,
        job_title=job_title,
        description="Test drive",
        cgpa_required=cgpa_required,
        branch_required=branch_required,
        year_required=year_required,
        deadline=deadline,
        status=status,
    )
    db.session.add(drive)
    db.session.commit()
    return drive


def make_application(student_id, drive_id, status="Applied", application_date="2026-01-01"):
    application = Application(
        student_id=student_id,
        drive_id=drive_id,
        status=status,
        application_date=application_date,
    )
    db.session.add(application)
    db.session.commit()
    return application

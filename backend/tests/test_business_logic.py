"""Business-rule tests: eligibility, duplicates, deadlines, drive workflow, search."""
from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    approve_company,
    auth_headers,
    make_drive,
    register_company,
    register_student,
)


def _setup(client, branch="CSE", cgpa=8.5, year=3):
    """Register + approve a company, register a student, return auth headers."""
    register_company(client)
    approve_company(1)
    register_student(client, branch=branch, cgpa=cgpa, year=year)
    company_headers = auth_headers(client, "acme@test.com", "acmepass")
    student_headers = auth_headers(client, "stud@test.com", "studpass")
    return company_headers, student_headers


def test_unapproved_company_cannot_create_drive(app, client):
    register_company(client)
    headers = auth_headers(client, "acme@test.com", "acmepass")
    response = client.post(
        "/drive/create",
        json={
            "company_id": 1,
            "job_title": "SDE",
            "description": "d",
            "cgpa_required": 7,
            "branch_required": ["CSE"],
            "year_required": 3,
            "deadline": "2099-12-31",
        },
        headers=headers,
    )
    assert response.status_code == 403


def test_approved_company_creates_pending_drive(app, client):
    company_headers, _ = _setup(client)
    response = client.post(
        "/drive/create",
        json={
            "company_id": 1,
            "job_title": "SDE",
            "description": "d",
            "cgpa_required": 7,
            "branch_required": ["CSE", "ECE"],
            "year_required": 3,
            "deadline": "2099-12-31",
        },
        headers=company_headers,
    )
    assert response.status_code == 200
    drive_id = response.get_json()["drive_id"]
    listed = client.get(f"/drives?company_id=1").get_json()
    drive = next(d for d in listed if d["id"] == drive_id)
    assert drive["status"] == "Pending"
    assert drive["branches"] == ["CSE", "ECE"]


def test_drive_requires_departments(app, client):
    company_headers, _ = _setup(client)
    response = client.post(
        "/drive/create",
        json={
            "company_id": 1,
            "job_title": "SDE",
            "description": "d",
            "cgpa_required": 7,
            "branch_required": [],
            "year_required": 3,
            "deadline": "2099-12-31",
        },
        headers=company_headers,
    )
    assert response.status_code == 400


def test_admin_approves_drive(app, client):
    company_headers, _ = _setup(client)
    drive_id = client.post(
        "/drive/create",
        json={
            "company_id": 1,
            "job_title": "SDE",
            "description": "d",
            "cgpa_required": 7,
            "branch_required": ["CSE"],
            "year_required": 3,
            "deadline": "2099-12-31",
        },
        headers=company_headers,
    ).get_json()["drive_id"]
    admin_headers = auth_headers(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.put(f"/admin/drive/approve/{drive_id}", headers=admin_headers).status_code == 200
    listed = client.get("/drives?approved_only=true").get_json()
    assert any(d["id"] == drive_id for d in listed)


def _apply(client, headers, student_id=1, drive_id=1):
    return client.post("/apply", json={"student_id": student_id, "drive_id": drive_id}, headers=headers)


def test_apply_success(app, client):
    _, student_headers = _setup(client)
    make_drive(company_id=1)
    response = _apply(client, student_headers)
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_apply_duplicate_rejected(app, client):
    _, student_headers = _setup(client)
    make_drive(company_id=1)
    assert _apply(client, student_headers).status_code == 200
    response = _apply(client, student_headers)
    assert response.status_code == 400
    assert "Already Applied" in response.get_json()["message"]


def test_apply_cgpa_not_met(app, client):
    _, student_headers = _setup(client, cgpa=6.0)
    make_drive(company_id=1, cgpa_required=7.0)
    response = _apply(client, student_headers)
    assert response.status_code == 400
    assert "CGPA" in response.get_json()["message"]


def test_apply_branch_not_met(app, client):
    _, student_headers = _setup(client, branch="Mechanical")
    make_drive(company_id=1, branch_required="CSE,ECE")
    response = _apply(client, student_headers)
    assert response.status_code == 400
    assert "Branch" in response.get_json()["message"]


def test_apply_multi_branch_drive_accepts_any_eligible(app, client):
    _, student_headers = _setup(client, branch="ECE")
    make_drive(company_id=1, branch_required="CSE,ECE")
    assert _apply(client, student_headers).status_code == 200


def test_apply_year_not_met(app, client):
    _, student_headers = _setup(client, year=2)
    make_drive(company_id=1, year_required=3)
    response = _apply(client, student_headers)
    assert response.status_code == 400
    assert "Year" in response.get_json()["message"]


def test_apply_after_deadline_rejected(app, client):
    _, student_headers = _setup(client)
    make_drive(company_id=1, deadline="2000-01-01")
    response = _apply(client, student_headers)
    assert response.status_code == 400
    assert "deadline" in response.get_json()["message"].lower()


def test_apply_to_unapproved_drive_rejected(app, client):
    _, student_headers = _setup(client)
    make_drive(company_id=1, status="Pending")
    response = _apply(client, student_headers)
    assert response.status_code == 403


def test_company_updates_application_status(app, client):
    company_headers, student_headers = _setup(client)
    drive = make_drive(company_id=1)
    _apply(client, student_headers, drive_id=drive.id)
    response = client.put(
        "/application/update/1",
        json={"status": "Shortlisted", "company_id": 1},
        headers=company_headers,
    )
    assert response.status_code == 200
    history = client.get("/student/history/1").get_json()
    assert history[0]["status"] == "Shortlisted"


def test_invalid_application_status_rejected(app, client):
    company_headers, student_headers = _setup(client)
    drive = make_drive(company_id=1)
    _apply(client, student_headers, drive_id=drive.id)
    response = client.put(
        "/application/update/1",
        json={"status": "Hired", "company_id": 1},
        headers=company_headers,
    )
    assert response.status_code == 400


def test_student_search_filters(app, client):
    register_student(client, username="a", email="a@test.com", full_name="Alice", cgpa=9.0, branch="CSE", year=3)
    register_student(client, username="b", email="b@test.com", full_name="Bob", cgpa=6.0, branch="ECE", year=2)
    admin_headers = auth_headers(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    names = lambda r: [s["full_name"] for s in r.get_json()]  # noqa: E731

    assert names(client.get("/admin/search/students?q=ali", headers=admin_headers)) == ["Alice"]
    assert names(client.get("/admin/search/students?q=@test.com", headers=admin_headers)) == ["Alice", "Bob"]
    assert names(client.get("/admin/search/students?min_cgpa=8", headers=admin_headers)) == ["Alice"]
    assert names(client.get("/admin/search/students?branch=ECE", headers=admin_headers)) == ["Bob"]
    assert names(client.get("/admin/search/students?year=3", headers=admin_headers)) == ["Alice"]


def test_drive_filters(app, client):
    register_company(client)
    approve_company(1)
    make_drive(company_id=1, job_title="SDE", cgpa_required=7.0, branch_required="CSE", deadline="2099-06-01")
    make_drive(company_id=1, job_title="Data Analyst", cgpa_required=9.0, branch_required="ECE", deadline="2099-01-01")

    titles = lambda r: [d["job_title"] for d in r.get_json()]  # noqa: E731

    assert titles(client.get("/drives?q=SDE")) == ["SDE"]
    assert titles(client.get("/drives?branch=ECE")) == ["Data Analyst"]
    assert titles(client.get("/drives?max_cgpa=8")) == ["SDE"]
    assert titles(client.get("/drives?deadline_before=2099-03-01")) == ["Data Analyst"]


def test_admin_stats(app, client):
    company_headers, student_headers = _setup(client)
    drive = make_drive(company_id=1)
    _apply(client, student_headers, drive_id=drive.id)
    client.put("/application/update/1", json={"status": "Selected", "company_id": 1}, headers=company_headers)

    admin_headers = auth_headers(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    stats = client.get("/admin/stats", headers=admin_headers).get_json()
    assert stats["drives_conducted"] == 1
    assert stats["students_applied"] == 1
    assert stats["students_selected"] == 1
    assert stats["selection_rate"] == 100.0
    assert stats["per_company"]["Acme Corp"]["selected"] == 1

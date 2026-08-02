"""Authentication tests: hashing, JWT, role enforcement, blacklist blocking."""
from app import Company, Student, User, db

from conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    auth_headers,
    login,
    register_company,
    register_student,
)


def test_admin_seeded_on_startup(app):
    admin = User.query.filter_by(role="admin").first()
    assert admin is not None
    assert admin.email == ADMIN_EMAIL


def test_register_hashes_password(app, client):
    register_student(client)
    user = User.query.filter_by(email="stud@test.com").first()
    assert user.password != "studpass"
    assert user.password.startswith(("pbkdf2:", "scrypt:", "argon2"))


def test_login_returns_token_and_role(app, client):
    register_student(client)
    response = login(client, "stud@test.com", "studpass")
    assert response.status_code == 200
    data = response.get_json()
    assert data["role"] == "student"
    assert data["token"]
    assert data["student_id"] == 1


def test_login_wrong_password(app, client):
    register_student(client)
    response = login(client, "stud@test.com", "wrongpass")
    assert response.status_code == 401


def test_plaintext_password_upgraded_on_login(app, client):
    """Legacy plaintext passwords are verified once, then upgraded to a hash."""
    db.session.add(User(username="legacy", email="legacy@test.com", password="plainpw", role="student"))
    db.session.commit()
    response = login(client, "legacy@test.com", "plainpw")
    assert response.status_code == 200
    user = User.query.filter_by(email="legacy@test.com").first()
    assert user.password.startswith(("pbkdf2:", "scrypt:", "argon2"))


def test_protected_endpoint_requires_token(app, client):
    response = client.get("/admin/dashboard")
    assert response.status_code == 401


def test_invalid_token_rejected(app, client):
    response = client.get("/admin/dashboard", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_student_cannot_access_admin_endpoints(app, client):
    register_student(client)
    headers = auth_headers(client, "stud@test.com", "studpass")
    assert client.get("/admin/dashboard", headers=headers).status_code == 403
    assert client.get("/admin/stats", headers=headers).status_code == 403


def test_admin_can_access_admin_endpoints(app, client):
    headers = auth_headers(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.get("/admin/dashboard", headers=headers).status_code == 200
    assert client.get("/admin/stats", headers=headers).status_code == 200


def test_company_cannot_access_student_endpoints(app, client):
    register_student(client)
    register_company(client)
    headers = auth_headers(client, "acme@test.com", "acmepass")
    assert client.post("/apply", json={"student_id": 1, "drive_id": 1}, headers=headers).status_code == 403


def test_blacklisted_student_cannot_login(app, client):
    register_student(client)
    Student.query.get(1).blacklisted = True
    db.session.commit()
    response = login(client, "stud@test.com", "studpass")
    assert response.status_code == 403
    assert "blacklisted" in response.get_json()["message"].lower()


def test_blacklisted_company_cannot_login(app, client):
    register_company(client)
    Company.query.get(1).blacklisted = True
    db.session.commit()
    response = login(client, "acme@test.com", "acmepass")
    assert response.status_code == 403

"""Model-level tests: fields, relationships, and constraints."""
import pytest
from sqlalchemy.exc import IntegrityError

from app import Application, Company, PlacementDrive, Student, User, db

from conftest import make_application, make_drive, register_company, register_student


def test_student_linked_to_user(app, client):
    register_student(client)
    student = Student.query.first()
    assert student is not None
    assert isinstance(student.user, User)
    assert student.user.email == "stud@test.com"
    assert student.is_active is True or student.is_active == 1


def test_company_fields_and_relationship(app, client):
    register_company(client)
    company = Company.query.first()
    assert company.company_name == "Acme Corp"
    assert company.hr_contact == "hr@acme.com"
    assert company.departments == "CSE,ECE"
    assert company.approved is False or company.approved == 0
    assert isinstance(company.user, User)


def test_drive_company_relationship(app, client):
    register_company(client)
    drive = make_drive(company_id=1, job_title="Backend Engineer")
    assert drive.company.company_name == "Acme Corp"
    assert drive.status == "Approved"


def test_application_relationships(app, client):
    register_student(client)
    register_company(client)
    drive = make_drive(company_id=1)
    application = make_application(student_id=1, drive_id=drive.id)
    assert application.student.full_name == "Test Student"
    assert application.drive.job_title == "SDE"


def test_duplicate_application_rejected_by_constraint(app, client):
    register_student(client)
    register_company(client)
    drive = make_drive(company_id=1)
    make_application(student_id=1, drive_id=drive.id)
    with pytest.raises(IntegrityError):
        make_application(student_id=1, drive_id=drive.id)
    db.session.rollback()


def test_user_email_unique(app, client):
    register_student(client, username="a", email="same@test.com")
    response = register_student(client, username="b", email="same@test.com")
    assert response.status_code == 400
    assert "already registered" in response.get_json()["message"]

"""Background-job tests: CSV builders, email fallback, scheduled jobs."""
import csv
import os

import tasks

from conftest import make_application, make_drive, register_company, register_student


def _point_tasks_at_test_db(app, monkeypatch, tmp_path):
    """Redirect tasks.py (raw sqlite3) at the test database and a temp export dir."""
    db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    monkeypatch.setattr(tasks, "DB_PATH", db_path)
    monkeypatch.setattr(tasks, "EXPORT_DIR", str(tmp_path))
    return str(tmp_path)


def test_send_email_without_credentials_returns_false(monkeypatch):
    for var in ("SMTP_USER", "SMTP_PASSWORD", "GMAIL_USER", "GMAIL_APP_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    assert tasks.send_email("someone@test.com", "Hi", "<p>Hi</p>") is False


def test_send_email_without_recipient_returns_false(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "u@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    assert tasks.send_email("", "Hi", "<p>Hi</p>") is False


def test_build_student_applications_csv(app, client, monkeypatch, tmp_path):
    export_dir = _point_tasks_at_test_db(app, monkeypatch, tmp_path)
    register_student(client)
    register_company(client)
    drive = make_drive(company_id=1, job_title="SDE")
    make_application(student_id=1, drive_id=drive.id, status="Shortlisted")

    filename = tasks.build_student_applications_csv(1)
    path = os.path.join(export_dir, filename)
    assert os.path.exists(path)

    with open(path, newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))
    assert rows[0] == ["Student ID", "Company Name", "Drive Title", "Application Status", "Application Date"]
    assert rows[1][1] == "Acme Corp"
    assert rows[1][2] == "SDE"
    assert rows[1][3] == "Shortlisted"


def test_build_admin_csv_all_types(app, client, monkeypatch, tmp_path):
    export_dir = _point_tasks_at_test_db(app, monkeypatch, tmp_path)
    register_student(client)
    register_company(client)
    drive = make_drive(company_id=1)
    make_application(student_id=1, drive_id=drive.id)

    for export_type in ("students", "companies", "applications"):
        filename = tasks.build_admin_csv(export_type)
        assert os.path.exists(os.path.join(export_dir, filename))


def test_export_admin_data_without_email(app, client, monkeypatch, tmp_path):
    _point_tasks_at_test_db(app, monkeypatch, tmp_path)
    register_student(client)
    result = tasks.export_admin_data("students")
    assert result["emailed"] is False
    assert result["filename"].startswith("admin_students_")


def test_daily_reminder_job(app, client, monkeypatch, tmp_path):
    """Job A: reminds eligible students whose drive deadline is within the window."""
    _point_tasks_at_test_db(app, monkeypatch, tmp_path)
    register_student(client)
    register_company(client)

    from datetime import date, timedelta

    soon = (date.today() + timedelta(days=1)).isoformat()
    far = (date.today() + timedelta(days=60)).isoformat()
    make_drive(company_id=1, job_title="Soon Drive", deadline=soon)
    make_drive(company_id=1, job_title="Far Drive", deadline=far)

    sent_to = []
    monkeypatch.setattr(tasks, "send_email", lambda to, subject, html, attachment_path=None: sent_to.append(to) or True)

    result = tasks.send_daily_deadline_reminders()
    # Only the drive whose deadline is within the reminder window triggers an email.
    assert result["sent"] == 1
    assert sent_to == ["stud@test.com"]


def test_monthly_report_job(app, client, monkeypatch, tmp_path):
    """Job B: builds an HTML report with totals and emails the admin."""
    export_dir = _point_tasks_at_test_db(app, monkeypatch, tmp_path)
    register_student(client)
    register_company(client)
    drive = make_drive(company_id=1)
    make_application(student_id=1, drive_id=drive.id, status="Selected")

    captured = {}

    def fake_send(to, subject, html, attachment_path=None):
        captured["to"] = to
        captured["subject"] = subject
        return True

    monkeypatch.setattr(tasks, "send_email", fake_send)
    monkeypatch.setenv("ADMIN_EMAIL", "admin@placement.local")

    result = tasks.send_monthly_admin_report()
    assert result["sent"] is True
    assert result["totals"]["Selected Students"] == 1
    assert captured["to"] == "admin@placement.local"
    assert os.path.exists(os.path.join(export_dir, result["filename"]))

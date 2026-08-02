import csv
import os
import smtplib
import sqlite3
from datetime import date, datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from celery_app import celery


BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "instance", "placement.db")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    """Lightweight migration so raw-SQL exports work even before Flask boots."""
    if not os.path.exists(DB_PATH):
        return
    with sqlite3.connect(DB_PATH) as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(companies)")}
        if "departments" not in existing:
            conn.execute("ALTER TABLE companies ADD COLUMN departments VARCHAR(200)")
        conn.commit()


def send_email(to_email, subject, html, attachment_path=None):
    """Send an email over SMTP. Returns True on success.

    Reads SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD (or MAIL_FROM) from
    the environment — see backend/.env.example. Legacy GMAIL_USER /
    GMAIL_APP_PASSWORD variables are still honoured as a fallback.
    Falls back gracefully (returns False) when credentials are not configured.
    """
    smtp_user = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD")
    if not smtp_user or not smtp_password or not to_email:
        return False

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    mail_from = os.environ.get("MAIL_FROM") or smtp_user

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as file:
            part = MIMEApplication(file.read(), Name=os.path.basename(attachment_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(attachment_path)}"'
        msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(mail_from, [to_email], msg.as_string())
        return True
    except (smtplib.SMTPException, OSError):
        return False


@celery.task
def hello():
    print("Hello from Celery")
    return "Done"


def build_student_applications_csv(student_id):
    """Generate the CSV for a student's applications. Callable synchronously."""
    ensure_schema()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    filename = f"student_{student_id}_applications_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    path = os.path.join(EXPORT_DIR, filename)

    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT
                s.id AS student_id,
                c.company_name AS company_name,
                d.job_title AS drive_title,
                a.status AS application_status,
                a.application_date AS application_date
            FROM application a
            JOIN students s ON s.id = a.student_id
            JOIN placement_drive d ON d.id = a.drive_id
            JOIN companies c ON c.id = d.company_id
            WHERE s.id = ?
            ORDER BY a.id DESC
            """,
            (student_id,),
        ).fetchall()

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Student ID", "Company Name", "Drive Title", "Application Status", "Application Date"])
        for row in rows:
            writer.writerow(
                [
                    row["student_id"],
                    row["company_name"],
                    row["drive_title"],
                    row["application_status"],
                    row["application_date"],
                ]
            )
    return filename


@celery.task
def export_student_applications(student_id):
    return build_student_applications_csv(student_id)


ADMIN_EXPORT_QUERIES = {
    "students": (
        ["ID", "Name", "Email", "CGPA", "Branch", "Year", "Blacklisted"],
        """
        SELECT s.id, s.full_name, u.email, s.cgpa, s.branch, s.year, IFNULL(s.blacklisted, 0)
        FROM students s
        LEFT JOIN user u ON u.id = s.user_id
        ORDER BY s.id
        """,
    ),
    "companies": (
        ["ID", "Company Name", "Email", "Website", "Departments", "Approved", "Blacklisted"],
        """
        SELECT c.id, c.company_name, u.email, c.website, c.departments, IFNULL(c.approved, 0), IFNULL(c.blacklisted, 0)
        FROM companies c
        LEFT JOIN user u ON u.id = c.user_id
        ORDER BY c.id
        """,
    ),
    "applications": (
        ["Application ID", "Student", "Email", "Company", "Drive", "Status", "Applied On", "Interview Schedule"],
        """
        SELECT a.id, s.full_name, u.email, co.company_name, d.job_title, a.status, a.application_date, a.interview_schedule
        FROM application a
        JOIN students s ON s.id = a.student_id
        LEFT JOIN user u ON u.id = s.user_id
        JOIN placement_drive d ON d.id = a.drive_id
        JOIN companies co ON co.id = d.company_id
        ORDER BY a.id DESC
        """,
    ),
}


def build_admin_csv(export_type):
    """Generate an admin CSV export. Callable synchronously."""
    if export_type not in ADMIN_EXPORT_QUERIES:
        raise ValueError(f"Unknown export type: {export_type}")
    ensure_schema()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    headers, query = ADMIN_EXPORT_QUERIES[export_type]
    filename = f"admin_{export_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    path = os.path.join(EXPORT_DIR, filename)

    with db_connect() as conn:
        rows = conn.execute(query).fetchall()

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(list(row))
    return filename


def export_admin_data(export_type, email_to=None):
    """Build an admin export and optionally email it with the CSV attached."""
    filename = build_admin_csv(export_type)
    emailed = False
    if email_to:
        path = os.path.join(EXPORT_DIR, filename)
        html = (
            "<p>Hello,</p>"
            f"<p>Please find the requested <strong>{export_type}</strong> export attached.</p>"
            f"<p><strong>Filename:</strong> {filename}</p>"
        )
        emailed = send_email(email_to, f"Placement Portal - {export_type.title()} Export", html, attachment_path=path)
    return {"filename": filename, "emailed": emailed}


@celery.task
def export_admin_data_task(export_type, email_to=None):
    return export_admin_data(export_type, email_to)


@celery.task
def send_daily_deadline_reminders():
    today = date.today()
    soon = today + timedelta(days=int(os.environ.get("REMINDER_DAYS", "2")))
    sent = 0

    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT
                u.email AS email,
                s.full_name AS student_name,
                d.job_title AS drive,
                d.deadline AS deadline
            FROM students s
            JOIN user u ON u.id = s.user_id
            JOIN placement_drive d ON d.status = 'Approved'
            LEFT JOIN application a ON a.student_id = s.id AND a.drive_id = d.id
            WHERE IFNULL(s.blacklisted, 0) = 0
              AND a.id IS NULL
            """
        ).fetchall()

    for row in rows:
        try:
            deadline = datetime.strptime(row["deadline"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if today <= deadline <= soon:
            html = f"""
            <p>Hello {row['student_name']},</p>
            <p>This is a reminder that the placement drive deadline is approaching.</p>
            <p><strong>Drive:</strong> {row['drive']}<br>
            <strong>Deadline:</strong> {row['deadline']}</p>
            """
            if send_email(row["email"], "Placement Drive Deadline Reminder", html):
                sent += 1
    return {"sent": sent}


@celery.task
def send_monthly_admin_report():
    admin_email = os.environ.get("ADMIN_EMAIL")
    os.makedirs(EXPORT_DIR, exist_ok=True)
    with db_connect() as conn:
        totals = {
            "Total Students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "Total Companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
            "Total Drives": conn.execute("SELECT COUNT(*) FROM placement_drive").fetchone()[0],
            "Applications": conn.execute("SELECT COUNT(*) FROM application").fetchone()[0],
            "Selected Students": conn.execute("SELECT COUNT(*) FROM application WHERE status = 'Selected'").fetchone()[0],
            "Shortlisted": conn.execute("SELECT COUNT(*) FROM application WHERE status = 'Shortlisted'").fetchone()[0],
            "Rejected": conn.execute("SELECT COUNT(*) FROM application WHERE status = 'Rejected'").fetchone()[0],
        }

    rows = "".join(f"<tr><th>{key}</th><td>{value}</td></tr>" for key, value in totals.items())
    html = f"""
    <h2>Monthly Placement Portal Report</h2>
    <table border="1" cellpadding="6" cellspacing="0">
      {rows}
    </table>
    """
    filename = f"monthly_report_{datetime.now().strftime('%Y_%m')}.html"
    with open(os.path.join(EXPORT_DIR, filename), "w", encoding="utf-8") as file:
        file.write(html)
    sent = send_email(admin_email, "Monthly Placement Portal Report", html)
    return {"sent": sent, "filename": filename, "totals": totals}

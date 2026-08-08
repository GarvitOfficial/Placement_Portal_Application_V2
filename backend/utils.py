import os
import sqlite3
from datetime import datetime, timezone, timedelta
from functools import wraps
import jwt
from flask import request, jsonify, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, CompanyProfile, PlacementDrive, StudentProfile, Application

# Canonical department list shared by company registration and drive creation.
DEPARTMENTS = ["CSE", "ECE", "EEE", "IT", "Mechanical", "Civil", "Chemical", "Biotechnology"]


def normalize_branches(value):
    """Accept a list or a comma/semicolon separated string; return a clean CSV string."""
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value]
    else:
        items = [item.strip() for item in str(value).replace(";", ",").split(",")]
    return ",".join([item for item in items if item])


def branches_list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def hash_password(raw):
    return generate_password_hash(raw)


def verify_password(user, raw):
    """Check a password against the stored value.

    Supports legacy plaintext passwords by transparently upgrading them to a
    hash on successful verification.
    """
    stored = user.password or ""
    if stored.startswith(("pbkdf2:", "scrypt:", "argon2")):
        return check_password_hash(stored, raw)
    if stored == raw:
        user.password = generate_password_hash(raw)
        db.session.commit()
        return True
    return False


def create_token(user):
    payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"message": "Authentication required"}), 401
        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401
        user = User.query.get(payload.get("user_id"))
        if not user:
            return jsonify({"message": "User not found"}), 401
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def role_required(role):
    def decorator(fn):
        @wraps(fn)
        @token_required
        def wrapper(*args, **kwargs):
            if g.current_user.role != role:
                return jsonify({"message": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


admin_required = role_required("admin")
company_required = role_required("company")
student_required = role_required("student")


def required(data, fields):
    missing = [field for field in fields if data.get(field) in (None, "")]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    return None


def parse_deadline(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def validate_json(fields):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            error = required(data, fields)
            if error:
                return error
            return fn(data, *args, **kwargs)

        return wrapper

    return decorator


def company_can_manage_application(company_id, application):
    company = CompanyProfile.query.get(company_id)
    if not company:
        return False, "Company not found"
    if not company.approved or company.blacklisted:
        return False, "Company is not approved"
    drive = PlacementDrive.query.get(application.drive_id)
    if not drive or drive.company_id != company.id:
        return False, "Application does not belong to this company"
    return True, ""


def student_payload(student):
    user = User.query.get(student.user_id)
    return {
        "id": student.id,
        "user_id": student.user_id,
        "username": user.username if user else "",
        "email": user.email if user else "",
        "full_name": student.full_name,
        "cgpa": student.cgpa,
        "branch": student.branch,
        "year": student.year,
        "resume": student.resume,
        "blacklisted": bool(student.blacklisted),
    }


def company_payload(company):
    user = User.query.get(company.user_id)
    return {
        "id": company.id,
        "user_id": company.user_id,
        "username": user.username if user else "",
        "email": user.email if user else "",
        "company_name": company.company_name,
        "hr_contact": company.hr_contact or "",
        "website": company.website,
        "departments": branches_list(company.departments),
        "approved": bool(company.approved),
        "blacklisted": bool(company.blacklisted),
    }


def drive_payload(drive):
    company = CompanyProfile.query.get(drive.company_id)
    # Parse years: use years_required (CSV) if available, else fall back to year_required (single int)
    if drive.years_required:
        years = [int(y.strip()) for y in drive.years_required.split(",") if y.strip()]
    elif drive.year_required:
        years = [drive.year_required]
    else:
        years = []
    return {
        "id": drive.id,
        "company_id": drive.company_id,
        "company_name": company.company_name if company else "",
        "job_title": drive.job_title,
        "description": drive.description,
        "cgpa_required": drive.cgpa_required,
        "branch_required": drive.branch_required,
        "branches": branches_list(drive.branch_required),
        "year_required": drive.year_required,
        "years": years,
        "deadline": drive.deadline,
        "status": drive.status,
    }


def application_payload(application):
    student = StudentProfile.query.get(application.student_id)
    drive = PlacementDrive.query.get(application.drive_id)
    company = CompanyProfile.query.get(drive.company_id) if drive else None
    return {
        "application_id": application.id,
        "student_id": application.student_id,
        "student_name": student.full_name if student else "",
        "student_cgpa": student.cgpa if student else 0,
        "student_branch": student.branch if student else "",
        "student_year": student.year if student else 0,
        "student_resume": student.resume if student else "",
        "drive_id": application.drive_id,
        "job_title": drive.job_title if drive else "",
        "company_name": company.company_name if company else "",
        "status": application.status,
        "application_date": application.application_date,
        "interview_schedule": application.interview_schedule,
    }

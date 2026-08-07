import os
import sqlite3
import socket
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

import jwt
from flask import Flask, g, jsonify, request, send_from_directory
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import get_config
from tasks import (
    build_student_applications_csv,
    export_admin_data,
    export_student_applications,
)


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


app = Flask(__name__)
app.config.from_object(get_config())

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)


def redis_available():
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=0.25):
            return True
    except OSError:
        return False


app.config["CACHE_TYPE"] = "RedisCache" if redis_available() else "SimpleCache"
cache = Cache(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, index=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(50), index=True)


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    full_name = db.Column(db.String(100), index=True)
    cgpa = db.Column(db.Float, index=True)
    branch = db.Column(db.String(100), index=True)
    year = db.Column(db.Integer, index=True)
    resume = db.Column(db.String(255))
    blacklisted = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship("User")


class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    company_name = db.Column(db.String(100), index=True)
    hr_contact = db.Column(db.String(100))
    website = db.Column(db.String(100))
    departments = db.Column(db.String(200))
    approved = db.Column(db.Boolean, default=False)
    blacklisted = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship("User")


class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), index=True)
    job_title = db.Column(db.String(100), index=True)
    description = db.Column(db.String(500))
    cgpa_required = db.Column(db.Float)
    deadline = db.Column(db.String(50))
    status = db.Column(db.String(50), index=True)
    branch_required = db.Column(db.String(100))
    year_required = db.Column(db.Integer)
    years_required = db.Column(db.String(100))  # CSV of eligible years (e.g., "2,3,4")

    company = db.relationship("Company")


class Application(db.Model):
    __table_args__ = (
        db.UniqueConstraint("student_id", "drive_id", name="uq_student_drive"),
        db.Index("ix_application_student_drive", "student_id", "drive_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), index=True)
    drive_id = db.Column(db.Integer, db.ForeignKey("placement_drive.id"), index=True)
    status = db.Column(db.String(50), index=True)
    application_date = db.Column(db.String(50))
    interview_schedule = db.Column(db.String(100))

    student = db.relationship("Student")
    drive = db.relationship("PlacementDrive")


class Placement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"))
    position = db.Column(db.String(100))
    salary = db.Column(db.Float)
    joining_date = db.Column(db.String(50))


def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response


app.after_request(add_cors)


@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        return "", 204


def clear_cache():
    try:
        cache.clear()
    except Exception:
        pass


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
        "exp": datetime.now(timezone.utc) + timedelta(hours=app.config["JWT_EXPIRY_HOURS"]),
    }
    return jwt.encode(payload, app.config["JWT_SECRET"], algorithm="HS256")


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"message": "Authentication required"}), 401
        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, app.config["JWT_SECRET"], algorithms=["HS256"])
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


def user_exists(email):
    return User.query.filter_by(email=email).first() is not None


def get_company_by_user(user_id):
    return Company.query.filter_by(user_id=user_id).first()


def get_student_by_user(user_id):
    return Student.query.filter_by(user_id=user_id).first()


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
    company = Company.query.get(drive.company_id)
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
    student = Student.query.get(application.student_id)
    drive = PlacementDrive.query.get(application.drive_id)
    company = Company.query.get(drive.company_id) if drive else None
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


def company_can_manage_application(company_id, application):
    company = Company.query.get(company_id)
    if not company:
        return False, "Company not found"
    if not company.approved or company.blacklisted:
        return False, "Company is not approved"
    drive = PlacementDrive.query.get(application.drive_id)
    if not drive or drive.company_id != company.id:
        return False, "Application does not belong to this company"
    return True, ""


def ensure_columns():
    db_path = os.path.join(app.instance_path, "placement.db")
    if not os.path.exists(db_path):
        return
    with sqlite3.connect(db_path) as conn:
        tables = {
            "students": {"resume": "VARCHAR(255)", "blacklisted": "BOOLEAN DEFAULT 0", "is_active": "BOOLEAN DEFAULT 1"},
            "companies": {
                "blacklisted": "BOOLEAN DEFAULT 0",
                "approved": "BOOLEAN DEFAULT 0",
                "departments": "VARCHAR(200)",
                "hr_contact": "VARCHAR(100)",
                "is_active": "BOOLEAN DEFAULT 1",
            },
            "placement_drive": {
                "branch_required": "VARCHAR(100)",
                "year_required": "INTEGER",
                "years_required": "VARCHAR(100)",
            },
            "application": {
                "application_date": "VARCHAR(50)",
                "interview_schedule": "VARCHAR(100)",
            },
        }
        for table, columns in tables.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        # Indexes for frequently queried fields (idempotent).
        indexes = [
            ("ix_students_branch", "students", "branch"),
            ("ix_students_cgpa", "students", "cgpa"),
            ("ix_students_year", "students", "year"),
            ("ix_drive_status", "placement_drive", "status"),
            ("ix_drive_company", "placement_drive", "company_id"),
            ("ix_app_student", "application", "student_id"),
            ("ix_app_drive", "application", "drive_id"),
            ("ix_app_status", "application", "status"),
        ]
        for name, table, column in indexes:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})")
        conn.commit()


with app.app_context():
    db.create_all()
    ensure_columns()
    if not User.query.filter_by(role="admin").first():
        admin_user = User(
            username=app.config["ADMIN_USERNAME"],
            email=app.config["ADMIN_EMAIL"],
            password=hash_password(app.config["ADMIN_PASSWORD"]),
            role="admin",
        )
        db.session.add(admin_user)
        db.session.commit()


@app.route("/")
def home():
    return jsonify({"message": "Placement Portal API"})


@app.route("/departments")
def departments():
    return jsonify(DEPARTMENTS)


@app.route("/login", methods=["POST"])
@validate_json(["email", "password"])
def login(data):
    user = User.query.filter_by(email=data["email"]).first()
    if not user or not verify_password(user, data["password"]):
        return jsonify({"message": "Invalid email or password"}), 401

    student = get_student_by_user(user.id) if user.role == "student" else None
    company = get_company_by_user(user.id) if user.role == "company" else None

    if student and student.blacklisted:
        return jsonify({"message": "Account blacklisted. Contact the administrator."}), 403
    if company and company.blacklisted:
        return jsonify({"message": "Account blacklisted. Contact the administrator."}), 403

    response = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "token": create_token(user),
    }
    if user.role == "student":
        response["student_id"] = student.id if student else None
    if user.role == "company":
        response["company_id"] = company.id if company else None
        response["approved"] = bool(company.approved) if company else False
        response["blacklisted"] = bool(company.blacklisted) if company else False
    return jsonify(response)


@app.route("/student/register", methods=["POST"])
@validate_json(["username", "email", "password", "full_name", "cgpa", "branch", "year"])
def student_register(data):
    if user_exists(data["email"]):
        return jsonify({"message": "Email already registered"}), 400
    user = User(username=data["username"], email=data["email"], password=hash_password(data["password"]), role="student")
    db.session.add(user)
    db.session.commit()
    student = Student(
        user_id=user.id,
        full_name=data["full_name"],
        cgpa=float(data["cgpa"]),
        branch=data["branch"],
        year=int(data["year"]),
        blacklisted=False,
    )
    db.session.add(student)
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Student Registered Successfully", "student_id": student.id})


@app.route("/company/register", methods=["POST"])
@validate_json(["email", "password", "company_name", "website"])
def company_register(data):
    if user_exists(data["email"]):
        return jsonify({"message": "Email already registered"}), 400
    username = data["email"].split("@")[0]
    user = User(username=username, email=data["email"], password=hash_password(data["password"]), role="company")
    db.session.add(user)
    db.session.commit()
    company = Company(
        user_id=user.id,
        company_name=data["company_name"],
        hr_contact=data.get("hr_contact", ""),
        website=data["website"],
        departments=normalize_branches(data.get("departments", "")),
        approved=False,
        blacklisted=False,
    )
    db.session.add(company)
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Company Registered Successfully", "company_id": company.id})


@app.route("/student/profile/<int:student_id>", methods=["GET", "PUT"])
def student_profile(student_id):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404
    if request.method == "GET":
        return jsonify(student_payload(student))

    data = request.get_json(silent=True) or {}
    error = required(data, ["full_name", "cgpa", "branch", "year"])
    if error:
        return error
    student.full_name = data["full_name"]
    student.cgpa = float(data["cgpa"])
    student.branch = data["branch"]
    student.year = int(data["year"])
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Profile updated", "student": student_payload(student)})


@app.route("/student/resume/<int:student_id>", methods=["POST"])
@student_required
def upload_resume(student_id):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404
    if "resume" not in request.files:
        return jsonify({"message": "Resume file is required"}), 400
    file = request.files["resume"]
    if not file.filename:
        return jsonify({"message": "Resume file is required"}), 400
    filename = f"{student_id}_{uuid4().hex}_{secure_filename(file.filename)}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    student.resume = filename
    db.session.commit()
    return jsonify({"message": "Resume uploaded", "filename": filename})


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/companies")
@cache.cached(timeout=60, query_string=True)
def companies():
    return jsonify([company_payload(company) for company in Company.query.all()])


@app.route("/students")
def students():
    return jsonify([student_payload(student) for student in Student.query.all()])


@app.route("/admin/company/approve/<int:company_id>", methods=["PUT", "GET"])
@admin_required
def approve_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    company.approved = True
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Company approved"})


@app.route("/admin/company/reject/<int:company_id>", methods=["PUT", "GET"])
@admin_required
def reject_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    company.approved = False
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Company rejected"})


@app.route("/admin/company/blacklist/<int:company_id>", methods=["PUT"])
@admin_required
def blacklist_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    company.blacklisted = True
    company.approved = False
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Company blacklisted"})


@app.route("/admin/student/blacklist/<int:student_id>", methods=["PUT"])
@admin_required
def blacklist_student(student_id):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404
    student.blacklisted = True
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Student blacklisted"})


@app.route("/drive/create", methods=["POST"])
@company_required
@validate_json(["company_id", "job_title", "description", "cgpa_required", "branch_required", "deadline"])
def create_drive(data):
    company = Company.query.get(data["company_id"])
    if not company:
        return jsonify({"message": "Company not found"}), 404
    if not company.approved or company.blacklisted:
        return jsonify({"message": "Only approved companies may create drives"}), 403
    if not parse_deadline(data["deadline"]):
        return jsonify({"message": "Deadline must be YYYY-MM-DD"}), 400
    branches = normalize_branches(data["branch_required"])
    if not branches:
        return jsonify({"message": "At least one eligible department is required"}), 400
    # Parse years: accept list or single value, save as CSV in years_required
    years_input = data.get("years") or data.get("year_required")
    if not years_input:
        return jsonify({"message": "At least one eligible year is required"}), 400
    if isinstance(years_input, (list, tuple)):
        years_csv = ",".join([str(int(y)) for y in years_input])
    else:
        years_csv = str(int(years_input))
    drive = PlacementDrive(
        company_id=company.id,
        job_title=data["job_title"],
        description=data["description"],
        cgpa_required=float(data["cgpa_required"]),
        branch_required=branches,
        years_required=years_csv,
        deadline=data["deadline"],
        status="Pending",
    )
    db.session.add(drive)
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Drive Created", "drive_id": drive.id})


@app.route("/drives")
@cache.cached(timeout=60, query_string=True)
def drives():
    company_id = request.args.get("company_id")
    approved_only = request.args.get("approved_only") == "true"
    q = request.args.get("q", "").strip()
    branch = request.args.get("branch", "").strip()
    max_cgpa = request.args.get("max_cgpa", "").strip()
    deadline_before = request.args.get("deadline_before", "").strip()

    query = PlacementDrive.query
    # Hide drives from blacklisted companies (except when viewing specific company's drives)
    if not company_id:
        query = query.join(Company).filter(Company.blacklisted != True)
    if company_id:
        query = query.filter_by(company_id=company_id)
    if approved_only:
        query = query.filter(PlacementDrive.status == "Approved")
    if q:
        query = query.filter(PlacementDrive.job_title.ilike(f"%{q}%"))
    if branch:
        # branch_required stores a CSV of eligible departments
        query = query.filter(PlacementDrive.branch_required.ilike(f"%{branch}%"))
    if max_cgpa:
        try:
            query = query.filter(PlacementDrive.cgpa_required <= float(max_cgpa))
        except ValueError:
            pass
    if deadline_before:
        query = query.filter(PlacementDrive.deadline <= deadline_before)
    return jsonify([drive_payload(drive) for drive in query.all()])


@app.route("/admin/drive/approve/<int:drive_id>", methods=["PUT", "GET"])
@admin_required
def approve_drive(drive_id):
    drive = PlacementDrive.query.get(drive_id)
    if not drive:
        return jsonify({"message": "Drive not found"}), 404
    drive.status = "Approved"
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Drive approved"})


@app.route("/admin/drive/reject/<int:drive_id>", methods=["PUT", "GET"])
@admin_required
def reject_drive(drive_id):
    drive = PlacementDrive.query.get(drive_id)
    if not drive:
        return jsonify({"message": "Drive not found"}), 404
    drive.status = "Rejected"
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Drive rejected"})


@app.route("/apply", methods=["POST"])
@student_required
@validate_json(["student_id", "drive_id"])
def apply(data):
    student = Student.query.get(data["student_id"])
    if not student:
        return jsonify({"message": "Student not found"}), 404
    if student.blacklisted:
        return jsonify({"success": False, "message": "Blacklisted students cannot apply"}), 403

    drive = PlacementDrive.query.get(data["drive_id"])
    if not drive:
        return jsonify({"message": "Drive not found"}), 404
    drive_company = Company.query.get(drive.company_id)
    if drive_company and drive_company.blacklisted:
        return jsonify({"success": False, "message": "This company is blacklisted"}), 403
    if drive.status != "Approved":
        return jsonify({"success": False, "message": "Drive is not approved"}), 403
    deadline = parse_deadline(drive.deadline)
    if deadline and deadline < date.today():
        return jsonify({"success": False, "message": "Application deadline has passed"}), 400

    existing = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
    if existing:
        return jsonify({"success": False, "message": "Already Applied"}), 400
    if student.cgpa < drive.cgpa_required:
        return jsonify({"success": False, "message": "CGPA criteria not met"}), 400
    eligible_branches = branches_list(drive.branch_required)
    if eligible_branches and student.branch.strip() not in eligible_branches:
        return jsonify({"success": False, "message": "Branch criteria not met"}), 400
    # Check year eligibility: use years_required (CSV) if available, else fall back to year_required
    if drive.years_required:
        eligible_years = [int(y.strip()) for y in drive.years_required.split(",") if y.strip()]
        if student.year not in eligible_years:
            return jsonify({"success": False, "message": "Year criteria not met"}), 400
    elif drive.year_required and student.year != drive.year_required:
        return jsonify({"success": False, "message": "Year criteria not met"}), 400

    application = Application(
        student_id=student.id,
        drive_id=drive.id,
        status="Applied",
        application_date=date.today().isoformat(),
    )
    db.session.add(application)
    db.session.commit()
    clear_cache()
    return jsonify({"success": True, "message": "Application Submitted"})


@app.route("/application/update/<int:application_id>", methods=["PUT"])
@company_required
def update_application(application_id):
    data = request.get_json(silent=True) or {}
    error = required(data, ["status", "company_id"])
    if error:
        return error
    allowed = {"Applied", "Shortlisted", "Rejected", "Selected"}
    if data["status"] not in allowed:
        return jsonify({"message": "Invalid application status"}), 400
    application = Application.query.get(application_id)
    if not application:
        return jsonify({"message": "Application not found"}), 404
    allowed_company, company_message = company_can_manage_application(data["company_id"], application)
    if not allowed_company:
        return jsonify({"message": company_message}), 403
    application.status = data["status"]
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Status Updated"})


@app.route("/application/schedule/<int:application_id>", methods=["PUT"])
@company_required
def schedule_interview(application_id):
    data = request.get_json(silent=True) or {}
    error = required(data, ["interview_schedule", "company_id"])
    if error:
        return error
    application = Application.query.get(application_id)
    if not application:
        return jsonify({"message": "Application not found"}), 404
    allowed_company, company_message = company_can_manage_application(data["company_id"], application)
    if not allowed_company:
        return jsonify({"message": company_message}), 403
    application.interview_schedule = data["interview_schedule"]
    db.session.commit()
    return jsonify({"message": "Interview scheduled"})


@app.route("/applications")
def applications():
    company_id = request.args.get("company_id")
    drive_id = request.args.get("drive_id")
    query = Application.query
    if drive_id:
        query = query.filter_by(drive_id=drive_id)
    rows = query.all()
    if company_id:
        company_drive_ids = {drive.id for drive in PlacementDrive.query.filter_by(company_id=company_id).all()}
        rows = [row for row in rows if row.drive_id in company_drive_ids]
    return jsonify([application_payload(row) for row in rows])


@app.route("/student/history/<int:student_id>")
def student_history(student_id):
    rows = Application.query.filter_by(student_id=student_id).all()
    return jsonify([application_payload(row) for row in rows])


@app.route("/admin/dashboard")
@admin_required
@cache.cached(timeout=60)
def admin_dashboard():
    return jsonify(
        {
            "students": Student.query.count(),
            "companies": Company.query.count(),
            "drives": PlacementDrive.query.count(),
            "applications": Application.query.count(),
        }
    )


@app.route("/admin/stats")
@admin_required
@cache.cached(timeout=60)
def admin_stats():
    """Placement statistics: drives conducted, applicants, selections, per-company counts."""
    drives = PlacementDrive.query.all()
    applications = Application.query.all()

    conducted = [drive for drive in drives if drive.status in ("Approved", "Closed")]
    selected = [app for app in applications if app.status == "Selected"]
    shortlisted = [app for app in applications if app.status == "Shortlisted"]
    rejected = [app for app in applications if app.status == "Rejected"]

    status_breakdown = {}
    for app in applications:
        status_breakdown[app.status] = status_breakdown.get(app.status, 0) + 1

    per_company = {}
    drive_company = {drive.id: drive.company_id for drive in drives}
    company_names = {company.id: company.company_name for company in Company.query.all()}
    for app in applications:
        name = company_names.get(drive_company.get(app.drive_id), "Unknown")
        bucket = per_company.setdefault(name, {"applications": 0, "shortlisted": 0, "selected": 0})
        bucket["applications"] += 1
        if app.status == "Shortlisted":
            bucket["shortlisted"] += 1
        elif app.status == "Selected":
            bucket["selected"] += 1

    return jsonify(
        {
            "drives_total": len(drives),
            "drives_conducted": len(conducted),
            "drives_pending": len([d for d in drives if d.status == "Pending"]),
            "students_applied": len({app.student_id for app in applications}),
            "applications_total": len(applications),
            "students_shortlisted": len(shortlisted),
            "students_selected": len(selected),
            "students_rejected": len(rejected),
            "selection_rate": round(len(selected) / len(applications) * 100, 1) if applications else 0,
            "status_breakdown": status_breakdown,
            "per_company": per_company,
        }
    )


@app.route("/admin/search/students")
@admin_required
@cache.cached(timeout=60, query_string=True)
def search_students():
    q = request.args.get("q", "").strip()
    branch = request.args.get("branch", "").strip()
    year = request.args.get("year", "").strip()
    min_cgpa = request.args.get("min_cgpa", "").strip()
    max_cgpa = request.args.get("max_cgpa", "").strip()

    query = Student.query.join(User, User.id == Student.user_id, isouter=True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Student.full_name.ilike(like),
                User.email.ilike(like),
                User.username.ilike(like),
            )
        )
    if branch:
        query = query.filter(Student.branch.ilike(f"%{branch}%"))
    if year:
        try:
            query = query.filter(Student.year == int(year))
        except ValueError:
            pass
    if min_cgpa:
        try:
            query = query.filter(Student.cgpa >= float(min_cgpa))
        except ValueError:
            pass
    if max_cgpa:
        try:
            query = query.filter(Student.cgpa <= float(max_cgpa))
        except ValueError:
            pass
    return jsonify([student_payload(student) for student in query.all()])


@app.route("/admin/search/companies")
@admin_required
@cache.cached(timeout=60, query_string=True)
def search_companies():
    q = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()

    query = Company.query.join(User, User.id == Company.user_id, isouter=True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Company.company_name.ilike(like),
                User.email.ilike(like),
                Company.website.ilike(like),
            )
        )
    if department:
        query = query.filter(Company.departments.ilike(f"%{department}%"))
    return jsonify([company_payload(company) for company in query.all()])


@app.route("/export/applications/<int:student_id>", methods=["POST"])
@student_required
def start_export(student_id):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404
    # Prefer the async Celery path when Redis is reachable; otherwise generate the
    # CSV synchronously so the feature still works without a broker/worker running.
    if redis_available():
        try:
            task = export_student_applications.delay(student_id)
            return jsonify({"mode": "async", "status": "Pending", "task_id": task.id})
        except Exception:
            pass
    filename = build_student_applications_csv(student_id)
    return jsonify({"mode": "sync", "status": "Export Completed", "filename": filename})


@app.route("/admin/export", methods=["POST"])
@admin_required
def admin_export():
    data = request.get_json(silent=True) or {}
    export_type = (data.get("type") or "students").strip().lower()
    email_to = (data.get("email") or "").strip()
    if export_type not in ("students", "companies", "applications"):
        return jsonify({"message": "Invalid export type. Use students, companies, or applications"}), 400
    try:
        result = export_admin_data(export_type, email_to or None)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(
        {
            "status": "Export Completed",
            "filename": result["filename"],
            "emailed": result["emailed"],
            "email_to": email_to or None,
        }
    )


@app.route("/export/status/<task_id>")
def export_status(task_id):
    result = export_student_applications.AsyncResult(task_id)
    if result.ready():
        if result.failed():
            return jsonify({"status": "Failed", "message": str(result.result)}), 500
        return jsonify({"status": "Export Completed", "filename": result.result})
    return jsonify({"status": "Pending"})


@app.route("/exports/<path:filename>")
def exported_file(filename):
    return send_from_directory(app.config["EXPORT_FOLDER"], filename)


@app.route("/register", methods=["POST"])
def register():
    return jsonify({"message": "Use /student/register or /company/register"}), 400


@app.route("/users")
@token_required
def users():
    return jsonify(
        [{"id": user.id, "username": user.username, "email": user.email, "role": user.role} for user in User.query.all()]
    )


@app.errorhandler(404)
def not_found(error):
    return jsonify({"message": "Resource not found"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"message": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"message": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], port=8000)

import os
from datetime import date
from uuid import uuid4
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from werkzeug.utils import secure_filename

from models import db, StudentProfile, PlacementDrive, CompanyProfile, Application
from cache import cache, clear_cache, redis_available
from utils import (
    student_required,
    validate_json,
    parse_deadline,
    branches_list,
    student_payload,
    drive_payload,
    application_payload,
    required,
)
from tasks import (
    build_student_applications_csv,
    export_student_applications,
)

student_bp = Blueprint("student", __name__)


@student_bp.route("/student/profile/<int:student_id>", methods=["GET", "PUT"])
def student_profile(student_id):
    student = StudentProfile.query.get(student_id)
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


@student_bp.route("/student/resume/<int:student_id>", methods=["POST"])
@student_required
def upload_resume(student_id):
    student = StudentProfile.query.get(student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404
    if "resume" not in request.files:
        return jsonify({"message": "Resume file is required"}), 400
    file = request.files["resume"]
    if not file.filename:
        return jsonify({"message": "Resume file is required"}), 400
    filename = f"{student_id}_{uuid4().hex}_{secure_filename(file.filename)}"
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
    student.resume = filename
    db.session.commit()
    return jsonify({"message": "Resume uploaded", "filename": filename})


@student_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@student_bp.route("/drives")
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
        query = query.join(CompanyProfile).filter(CompanyProfile.blacklisted != True)
    if company_id:
        query = query.filter_by(company_id=company_id)
    if approved_only:
        query = query.filter(PlacementDrive.status == "Approved")
    if q:
        query = query.filter(PlacementDrive.job_title.ilike(f"%{q}%"))
    if branch:
        query = query.filter(PlacementDrive.branch_required.ilike(f"%{branch}%"))
    if max_cgpa:
        try:
            query = query.filter(PlacementDrive.cgpa_required <= float(max_cgpa))
        except ValueError:
            pass
    if deadline_before:
        query = query.filter(PlacementDrive.deadline <= deadline_before)
    return jsonify([drive_payload(drive) for drive in query.all()])


@student_bp.route("/apply", methods=["POST"])
@student_required
@validate_json(["student_id", "drive_id"])
def apply(data):
    student = StudentProfile.query.get(data["student_id"])
    if not student:
        return jsonify({"message": "Student not found"}), 404
    if student.blacklisted:
        return jsonify({"success": False, "message": "Blacklisted students cannot apply"}), 403

    drive = PlacementDrive.query.get(data["drive_id"])
    if not drive:
        return jsonify({"message": "Drive not found"}), 404
    drive_company = CompanyProfile.query.get(drive.company_id)
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
    # Check year eligibility
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


@student_bp.route("/applications")
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


@student_bp.route("/student/history/<int:student_id>")
def student_history(student_id):
    rows = Application.query.filter_by(student_id=student_id).all()
    return jsonify([application_payload(row) for row in rows])


@student_bp.route("/export/applications/<int:student_id>", methods=["POST"])
@student_required
def start_export(student_id):
    student = StudentProfile.query.get(student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404
    if redis_available():
        try:
            task = export_student_applications.delay(student_id)
            return jsonify({"mode": "async", "status": "Pending", "task_id": task.id})
        except Exception:
            pass
    filename = build_student_applications_csv(student_id)
    return jsonify({"mode": "sync", "status": "Export Completed", "filename": filename})


@student_bp.route("/export/status/<task_id>")
def export_status(task_id):
    result = export_student_applications.AsyncResult(task_id)
    if result.ready():
        if result.failed():
            return jsonify({"status": "Failed", "message": str(result.result)}), 500
        return jsonify({"status": "Export Completed", "filename": result.result})
    return jsonify({"status": "Pending"})


@student_bp.route("/exports/<path:filename>")
def exported_file(filename):
    return send_from_directory(current_app.config["EXPORT_FOLDER"], filename)

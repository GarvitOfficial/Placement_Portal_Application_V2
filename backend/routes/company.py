from flask import Blueprint, jsonify, request

from models import db, CompanyProfile, PlacementDrive, Application
from cache import clear_cache
from utils import (
    company_required,
    validate_json,
    normalize_branches,
    parse_deadline,
    required,
    company_can_manage_application,
)

company_bp = Blueprint("company", __name__)


@company_bp.route("/drive/create", methods=["POST"])
@company_required
@validate_json(["company_id", "job_title", "description", "cgpa_required", "branch_required", "deadline"])
def create_drive(data):
    company = CompanyProfile.query.get(data["company_id"])
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


@company_bp.route("/application/update/<int:application_id>", methods=["PUT"])
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


@company_bp.route("/application/schedule/<int:application_id>", methods=["PUT"])
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

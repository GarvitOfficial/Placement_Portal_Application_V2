from flask import Blueprint, jsonify, request

from models import db, User, StudentProfile, CompanyProfile, PlacementDrive, Application
from cache import cache, clear_cache
from utils import (
    admin_required,
    student_payload,
    company_payload,
    drive_payload,
)
from tasks import export_admin_data

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/companies")
def companies():
    return jsonify([company_payload(company) for company in CompanyProfile.query.all()])


@admin_bp.route("/students")
def students():
    return jsonify([student_payload(student) for student in StudentProfile.query.all()])


@admin_bp.route("/admin/company/approve/<int:company_id>", methods=["PUT", "GET"])
@admin_required
def approve_company(company_id):
    company = CompanyProfile.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    company.approved = True
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Company approved"})


@admin_bp.route("/admin/company/reject/<int:company_id>", methods=["PUT", "GET"])
@admin_required
def reject_company(company_id):
    company = CompanyProfile.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    company.approved = False
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Company rejected"})


@admin_bp.route("/admin/company/blacklist/<int:company_id>", methods=["PUT"])
@admin_required
def blacklist_company(company_id):
    company = CompanyProfile.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    company.blacklisted = True
    company.approved = False
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Company blacklisted"})


@admin_bp.route("/admin/student/blacklist/<int:student_id>", methods=["PUT"])
@admin_required
def blacklist_student(student_id):
    student = StudentProfile.query.get(student_id)
    if not student:
        return jsonify({"message": "Student not found"}), 404
    student.blacklisted = True
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Student blacklisted"})


@admin_bp.route("/admin/drive/approve/<int:drive_id>", methods=["PUT", "GET"])
@admin_required
def approve_drive(drive_id):
    drive = PlacementDrive.query.get(drive_id)
    if not drive:
        return jsonify({"message": "Drive not found"}), 404
    drive.status = "Approved"
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Drive approved"})


@admin_bp.route("/admin/drive/reject/<int:drive_id>", methods=["PUT", "GET"])
@admin_required
def reject_drive(drive_id):
    drive = PlacementDrive.query.get(drive_id)
    if not drive:
        return jsonify({"message": "Drive not found"}), 404
    drive.status = "Rejected"
    db.session.commit()
    clear_cache()
    return jsonify({"message": "Drive rejected"})


@admin_bp.route("/admin/dashboard")
@admin_required
@cache.cached(timeout=60)
def admin_dashboard():
    return jsonify(
        {
            "students": StudentProfile.query.count(),
            "companies": CompanyProfile.query.count(),
            "drives": PlacementDrive.query.count(),
            "applications": Application.query.count(),
        }
    )


@admin_bp.route("/admin/stats")
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
    company_names = {company.id: company.company_name for company in CompanyProfile.query.all()}
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


@admin_bp.route("/admin/search/students")
@admin_required
@cache.cached(timeout=60, query_string=True)
def search_students():
    q = request.args.get("q", "").strip()
    branch = request.args.get("branch", "").strip()
    year = request.args.get("year", "").strip()
    min_cgpa = request.args.get("min_cgpa", "").strip()
    max_cgpa = request.args.get("max_cgpa", "").strip()

    query = StudentProfile.query.join(User, User.id == StudentProfile.user_id, isouter=True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                StudentProfile.full_name.ilike(like),
                User.email.ilike(like),
                User.username.ilike(like),
            )
        )
    if branch:
        query = query.filter(StudentProfile.branch.ilike(f"%{branch}%"))
    if year:
        try:
            query = query.filter(StudentProfile.year == int(year))
        except ValueError:
            pass
    if min_cgpa:
        try:
            query = query.filter(StudentProfile.cgpa >= float(min_cgpa))
        except ValueError:
            pass
    if max_cgpa:
        try:
            query = query.filter(StudentProfile.cgpa <= float(max_cgpa))
        except ValueError:
            pass
    return jsonify([student_payload(student) for student in query.all()])


@admin_bp.route("/admin/search/companies")
@admin_required
@cache.cached(timeout=60, query_string=True)
def search_companies():
    q = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()

    query = CompanyProfile.query.join(User, User.id == CompanyProfile.user_id, isouter=True)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                CompanyProfile.company_name.ilike(like),
                User.email.ilike(like),
                CompanyProfile.website.ilike(like),
            )
        )
    if department:
        query = query.filter(CompanyProfile.departments.ilike(f"%{department}%"))
    return jsonify([company_payload(company) for company in query.all()])


@admin_bp.route("/admin/export", methods=["POST"])
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

from flask import Blueprint, jsonify, request

from models import db, User, StudentProfile, CompanyProfile
from cache import clear_cache
from utils import (
    hash_password,
    verify_password,
    create_token,
    token_required,
    validate_json,
    normalize_branches,
)

auth_bp = Blueprint("auth", __name__)


def user_exists(email):
    return User.query.filter_by(email=email).first() is not None


def get_company_by_user(user_id):
    return CompanyProfile.query.filter_by(user_id=user_id).first()


def get_student_by_user(user_id):
    return StudentProfile.query.filter_by(user_id=user_id).first()


@auth_bp.route("/login", methods=["POST"])
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


@auth_bp.route("/student/register", methods=["POST"])
@validate_json(["username", "email", "password", "full_name", "cgpa", "branch", "year"])
def student_register(data):
    if user_exists(data["email"]):
        return jsonify({"message": "Email already registered"}), 400
    user = User(username=data["username"], email=data["email"], password=hash_password(data["password"]), role="student")
    db.session.add(user)
    db.session.commit()
    student = StudentProfile(
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


@auth_bp.route("/company/register", methods=["POST"])
@validate_json(["email", "password", "company_name", "website"])
def company_register(data):
    if user_exists(data["email"]):
        return jsonify({"message": "Email already registered"}), 400
    username = data["email"].split("@")[0]
    user = User(username=username, email=data["email"], password=hash_password(data["password"]), role="company")
    db.session.add(user)
    db.session.commit()
    company = CompanyProfile(
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


@auth_bp.route("/register", methods=["POST"])
def register():
    return jsonify({"message": "Use /student/register or /company/register"}), 400


@auth_bp.route("/users")
@token_required
def users():
    return jsonify(
        [{"id": user.id, "username": user.username, "email": user.email, "role": user.role} for user in User.query.all()]
    )

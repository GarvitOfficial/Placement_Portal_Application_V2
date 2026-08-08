from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, index=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(50), index=True)


class StudentProfile(db.Model):
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


class CompanyProfile(db.Model):
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

    company = db.relationship("CompanyProfile")


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

    student = db.relationship("StudentProfile")
    drive = db.relationship("PlacementDrive")


class Placement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"))
    position = db.Column(db.String(100))
    salary = db.Column(db.Float)
    joining_date = db.Column(db.String(50))

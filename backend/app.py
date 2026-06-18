from flask import Flask
from flask import jsonify
from flask import request
from flask_caching import Cache

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["CACHE_TYPE"] = "RedisCache"
app.config["CACHE_REDIS_URL"] = "redis://localhost:6379/0"

cache = Cache(app)
#=========Database ka kr rha kuch=============

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///placement.db"
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password = db.Column(db.String(100))
    role = db.Column(db.String(50))

class Student(db.Model):
    __tablename__ = "students"    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    full_name = db.Column(db.String(100))
    cgpa = db.Column(db.Float)
    branch = db.Column(db.String(100))
    year = db.Column(db.Integer)
    resume = db.Column(db.String(255))
    blacklisted = db.Column(db.Boolean, default=False)

class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    company_name = db.Column(db.String(100))
    website = db.Column(db.String(100))
    approved = db.Column(db.Boolean)
    blacklisted = db.Column(db.Boolean, default=False)

class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer)
    job_title = db.Column(db.String(100))
    description = db.Column(db.String(500))
    cgpa_required = db.Column(db.Float)
    deadline = db.Column(db.String(50))
    status = db.Column(db.String(50))
    branch_required = db.Column(db.String(100))
    year_required = db.Column(db.Integer)
    
class Application(db.Model):
       id = db.Column(db.Integer, primary_key=True)
       student_id = db.Column(db.Integer)
       drive_id = db.Column(db.Integer)
       status = db.Column(db.String(50))
       application_date = db.Column(db.String(50))

class Placement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id")
    )
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id")
    )
    position = db.Column(db.String(100))
    salary = db.Column(db.Float)
    joining_date = db.Column(db.String(50))

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return "Database Created!"

# @app.route("/")
# def home():
#     data = { "message" : "Hello, This is Placement Portal"}
#     return jsonify(data)

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(
        email = data["email"]
    ).first()
    if not user:
        return jsonify({
            "message":"User not Found"
        }),404
    if user.password != data['password']:
        return jsonify({
            'message':"Invalid Password"
        })
    return jsonify({
         "id": user.id,
         "username": user.username,
         "role": user.role
    })

@app.route("/register", methods = ["POST"])
def register():
    data = request.json

    return jsonify({

        "message": "Registration successful",

        "user": data
    })

@app.route("/addUser")
def addUser():
    user = User(
        username = "golden",
        role = "student"
    )
    db.session.add(user)
    db.session.commit()
    return "User added"

@app.route("/users")
def users():
    users = User.query.all()
    result = []
    for i in users:
        result.append({
            "id": i.id,
            "username": i.username,
            "role": i.role
        })
    return jsonify(result)

@app.route("/company")
def company():
     return jsonify([

        {"id":1,"name":"Google"},

        {"id":2,"name":"Amazon"}

    ])


@app.route("/company/register", methods=["POST"])
def company_register():

    data = request.json

    user = User(
        username=data["username"],
        email=data["email"],
        password=data["password"],
        role="company"
    )

    db.session.add(user)
    db.session.commit()

    company = Company(
        user_id=user.id,
        company_name=data["company_name"],
        website=data["website"],
        approved=False
    )

    db.session.add(company)
    db.session.commit()

    return jsonify({
        "message": "Company Registered Successfully"
    })

@app.route("/companies")
def companies():

    companies = Company.query.all()

    result = []

    for c in companies:
        result.append({
            "id": c.id,
            "company_name": c.company_name,
            "website": c.website,
            "approved": c.approved
        })

    return jsonify(result)

@app.route("/admin/company/approve/<int:company_id>")
def approve_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({
            "message": "Company not found"
        }), 404
    company.approved = True
    db.session.commit()
    return jsonify({
        "message": "Company approved"
    })

@app.route("/admin/company/reject/<int:company_id>")
def reject_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({
            "message": "Company not found"
        }), 404
    company.approved = False
    db.session.commit()
    return jsonify({
        "message": "Company rejected"
    })


@app.route("/student/register", methods=["POST"])
def student_register():

    data = request.json

    user = User(
        username=data["username"],
        email=data["email"],
        password=data["password"],
        role="student"
    )

    db.session.add(user)
    db.session.commit()

    student = Student(
        user_id=user.id,
        full_name=data["full_name"],
        cgpa=data["cgpa"],
        branch=data["branch"],
        year=data["year"]
    )

    db.session.add(student)
    db.session.commit()

    return jsonify({
        "message": "Student Registered Successfully"
    })

@app.route("/student")
def student():
    return jsonify({
        "id":0,
        "name": "Golden",
        "cgpa": 10
    },
    { "id":1,
        "name": "Garv",
        "cgpa": 9})

@app.route("/students")
def students():

    students = Student.query.all()

    result = []

    for s in students:
        result.append({
            "id": s.id,
            "name": s.full_name,
            "cgpa": s.cgpa
        })

    return jsonify(result)

@app.route("/admin")
def admin():
    return "Admin Dashboard"

@app.route("/drive/create", methods=["POST"])
def create_drive():
    data = request.json
    drive = PlacementDrive(
       company_id=data["company_id"],
       job_title=data["job_title"],
       description=data["description"],
       cgpa_required=data["cgpa_required"],
       branch_required=data["branch_required"],
       year_required=data["year_required"],
       deadline=data["deadline"],
       status="Open"
    )
    db.session.add(drive)
    db.session.commit()
    return jsonify({
        "message": "Drive Created"
    })

@app.route("/drives")
def drives():
    drives = PlacementDrive.query.all()
    result = []
    for d in drives:
        result.append({
            "id": d.id,
            "job_title": d.job_title,
            "cgpa_required": d.cgpa_required,
            "status": d.status
        })
    return jsonify(result)

@app.route("/apply" , methods=["POST"])
def apply():
    data = request.json
    student = Student.query.get(data["student_id"])

    if not student:
        return jsonify({
            "message": "Student not found"
        }), 404

    drive = PlacementDrive.query.get(data["drive_id"])

    if not drive:
        return jsonify({
            "message": "Drive not found"
        }), 404

    existing = Application.query.filter_by(
        student_id=data["student_id"],
        drive_id=data["drive_id"]
    ).first()

    if existing:
        return jsonify({
            "success": False,
            "message": "Already Applied"
        }), 400

    if student.cgpa < drive.cgpa_required:
        return jsonify({
            "success": False,
            "message": "CGPA criteria not met"
        }), 400

    if student.branch != drive.branch_required:
        return jsonify({
            "success": False,
            "message": "Branch criteria not met"
        }), 400

    if student.year != drive.year_required:
        return jsonify({
            "success": False,
            "message": "Year criteria not met"
        }), 400
    # Create application
    application = Application(
        student_id=student.id,
        drive_id=drive.id,
        status="Applied"
    )

    db.session.add(application)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Application Submitted"
    })

@app.route("/application/update/<int:application_id>", methods=["PUT"])
def update_application(application_id):
    data = request.json
    application = Application.query.get(application_id)
    if not application:
        return jsonify({
            "message": "Application not found"
        }), 404
    application.status = data["status"]
    db.session.commit()
    return jsonify({
        "message": "Status Updated"
    })

@app.route("/applications")
def applications():

    applications = Application.query.all()

    result = []

    for app in applications:

        student = Student.query.get(app.student_id)

        drive = PlacementDrive.query.get(app.drive_id)

        result.append({
            "application_id": app.id,
            "student_name": student.full_name,
            "job_title": drive.job_title,
            "status": app.status
        })

    return jsonify(result)

@app.route("/admin/dashboard")
@cache.cached(timeout=300)
def admin_dashboard():
    total_students = Student.query.count()
    total_companies = Company.query.count()
    total_drives = PlacementDrive.query.count()
    total_applications = Application.query.count()
    return jsonify({
        "students": total_students,
        "companies": total_companies,
        "drives": total_drives,
        "applications": total_applications
    })

@app.route("/student/history/<int:student_id>")
def student_history(student_id):
    applications = Application.query.filter_by(
        student_id=student_id
    ).all()
    result = []
    for app in applications:
        drive = PlacementDrive.query.get(app.drive_id)
        result.append({
            "job_title": drive.job_title,
            "status": app.status
        })
    return jsonify(result)

# =============== learning ===========================
@app.route("/test")
def test():
    return "this is testing area"
# http://127.0.0.1:5000/test comes here

@app.route("/printing/<string:n>")
def printing(n):
    return f"{n}"




app.run(debug=True, port=8000)


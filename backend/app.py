import os
import sqlite3
from flask import Flask, jsonify

from config import get_config
from cache import cache, redis_available
from models import db, User
from utils import hash_password
from routes import auth_bp, admin_bp, company_bp, student_bp

app = Flask(__name__)
app.config.from_object(get_config())

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)

# Initialize SQLAlchemy
db.init_app(app)

# Configure Cache
app.config["CACHE_TYPE"] = "RedisCache" if redis_available() else "SimpleCache"
cache.init_app(app)


def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response


app.after_request(add_cors)


@app.before_request
def handle_options():
    from flask import request
    if request.method == "OPTIONS":
        return "", 204


# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(company_bp)
app.register_blueprint(student_bp)


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


@app.route("/")
def home():
    return jsonify({"message": "Placement Portal API"})


@app.route("/departments")
def departments():
    from utils import DEPARTMENTS
    return jsonify(DEPARTMENTS)


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

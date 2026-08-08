
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:


    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "12"))

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///placement.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CACHE_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

    # Celery broker / result backend (see celery_app.py)
    CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    EXPORT_FOLDER = os.path.join(BASE_DIR, "exports")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB resume upload limit

    # SMTP settings used by tasks.send_email()
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER)

    # Admin account created by the seed routine on first boot
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@placement.local")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")


class DevelopmentConfig(Config):
    DEBUG = True
    # In-memory cache works without Redis; RedisCache is used when reachable.
    CACHE_DEFAULT_TIMEOUT = 300


class ProductionConfig(Config):
    DEBUG = False
    CACHE_DEFAULT_TIMEOUT = 600


CONFIG_BY_ENV = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    return CONFIG_BY_ENV.get(env, DevelopmentConfig)

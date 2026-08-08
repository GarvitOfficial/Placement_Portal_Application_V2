# Placement Portal Application (PPA)

This is a Placement Portal Application built for campus recruitment workflows. The core flow is kept simple:

Companies register -> Admin approves
Companies create drives -> Admin approves
Students apply -> Company shortlists/selects + schedules interviews

## Roles of each user

### Admin (Institute Placement Cell)

- Approve/reject company registrations
- Approve/reject/close placement drives
- Activate/deactivate students
- View students, companies, drives, and applications
- Dashboard statistics (counts)

### Company

- Create/update company profile
- Create placement drives (only after Admin approval)
- View applicants per drive
- Update application status (Shortlisted / Selected / Rejected)
- Schedule interviews (time + mode + notes)

### Student

- Create/update student profile (branch, CGPA, graduation year, resume link)
- Browse approved drives (search supported)
- Eligibility is checked before applying (branch/CGPA/year/deadline)
- Apply only once (duplicate applications prevented)
- Export application history as CSV (async job)

## Tech Stack (as per rubric)

- Flask (API)
- VueJS (UI) + Bootstrap (styling)
- SQLite (database)
- Redis (caching + Celery broker)
- Celery (scheduled jobs + async export)

## Project Structure

```
Placement_Portal_Application_V2/
├── backend/
│   ├── app.py                  # Flask app entry + DB init + default admin + Blueprint registration
│   ├── config.py               # Environment-driven configuration (DB path, Redis, Webhook)
│   ├── cache.py                # Redis cache helpers with safe fallback
│   ├── utils.py                # Shared decorators (auth, role, JSON) and payload serializers
│   ├── celery_app.py           # Celery configuration
│   ├── tasks.py                # Celery tasks (export, email reminders)
│   ├── requirements.txt        # Python dependencies
│   ├── instance/
│   │   └── placement.db        # SQLite database (auto-created)
│   ├── uploads/                # Student resume uploads
│   ├── exports/                # CSV export files
│   ├── models/                 # SQLAlchemy Database models
│   │   └── __init__.py         # Centralized models (User, StudentProfile, CompanyProfile, etc.)
│   ├── routes/                 # Flask blueprints for modular endpoint handling
│   │   ├── __init__.py         # Exposes blueprints
│   │   ├── auth.py             # Auth blueprints (/login, registrations, /users)
│   │   ├── admin.py            # Admin blueprints (approvals, blacklisting, stats, export)
│   │   ├── company.py          # Company blueprints (drives, application management)
│   │   └── student.py          # Student blueprints (profile, apply, history, downloads)
├── frontend/
│   ├── src/
│   │   ├── App.vue             # Main app component (router)
│   │   ├── main.js             # Vue entry point
│   │   └── components/
│   │       ├── LoginView.vue
│   │       ├── AdminDashboard.vue
│   │       ├── CompanyDashboard.vue
│   │       ├── CompanyRegister.vue
│   │       ├── StudentDashboard.vue
│   │       └── StudentRegister.vue
│   ├── index.html              # HTML entry
│   ├── package.json            # Node dependencies
│   └── vite.config.js          # Vite configuration
└── README.md                   # You are here
```

## Local Setup

### 1) Start Redis

Redis is required for caching and Celery task queues.

**Option A: Use local Redis (recommended)**

If you have Redis installed locally:
```bash
# Check if Redis is running
redis-cli ping
# If it responds with PONG, you're good to go!

# If not running, start it:
# macOS (with Homebrew):
brew services start redis

# Or manually:
redis-server
```

**Option B: Use Docker**

If you prefer Docker (make sure local Redis is stopped first):
```bash
docker run -d -p 6379:6379 --name ppa-redis redis:7
```

The app connects to Redis at `redis://localhost:6379/0` by default. If Redis is unavailable, the app falls back to in-memory caching (but Celery tasks won't work).

### 2) Backend (Flask)

```bash
cd backend
python -m pip install -r requirements.txt
```

#### Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `backend/.env` and update the following:

```bash
# SMTP Configuration (for email reminders, monthly reports, export emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com          # Your Gmail address
SMTP_PASSWORD=your-app-password          # Gmail App Password (not regular password)
MAIL_FROM=your-email@gmail.com

# Admin credentials (used on first boot to create admin account)
ADMIN_EMAIL=admin@admin.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin

# Security (change these in production!)
SECRET_KEY=change-me-to-a-long-random-string
JWT_SECRET=change-me-to-a-long-random-string
```

**Important:** 
- For Gmail, you need to generate an [App Password](https://myaccount.google.com/apppasswords) (requires 2FA enabled)
- The `.env` file is git-ignored and contains sensitive credentials

#### Start the Backend

```bash
python app.py
```

The SQLite DB file is created programmatically inside `backend/instance/placement.db`.

#### Default Admin

- Email: `admin@admin.com`
- Password: `admin`

You can override these using environment variables:

```bash
export ADMIN_EMAIL="admin@admin.com"
export ADMIN_PASSWORD="admin"
```

### 3) Celery Worker + Scheduler (Beat)

In a new terminal:

```bash
cd backend
celery -A celery_app.celery worker -B --loglevel=info
```

### 4) Frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at:

```
http://localhost:5173/
```

Backend API runs at:

```
http://localhost:8000/
```


### Email (monthly report)

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your_email"
export SMTP_PASSWORD="your_app_password"
export MAIL_FROM="your_email"
```

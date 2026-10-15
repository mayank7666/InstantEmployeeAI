"""Instant Employee API MVP: accounts, profiles, jobs, and applications."""
import os, hashlib, secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, inspect, text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./instant_employee.db")
# Some hosting providers supply PostgreSQL URLs using the legacy postgres:// scheme.
# SQLAlchemy 2.x expects postgresql://; explicitly select psycopg 3 for predictable deployment.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_SECRET_KEY_BEFORE_DEPLOYING")
ALGORITHM = "HS256"
TOKEN_MINUTES = 720
engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="talent")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    profile: Mapped[Optional["Profile"]] = relationship(back_populates="user", uselist=False)
    jobs: Mapped[list["Job"]] = relationship(back_populates="company")
    applications: Mapped[list["Application"]] = relationship(back_populates="talent")
class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    headline: Mapped[str] = mapped_column(String(200), default="")
    skills: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    availability: Mapped[str] = mapped_column(String(80), default="Available")
    portfolio_url: Mapped[str] = mapped_column(String(500), default="")
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    picture_data: Mapped[str] = mapped_column(Text, default="")
    resume_text: Mapped[str] = mapped_column(Text, default="")
    resume_data: Mapped[str] = mapped_column(Text, default="")
    user: Mapped["User"] = relationship(back_populates="profile")
class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    department: Mapped[str] = mapped_column(String(120), default="Other")
    description: Mapped[str] = mapped_column(Text)
    required_skills: Mapped[str] = mapped_column(Text, default="")
    min_budget: Mapped[int] = mapped_column(Integer, default=0)
    max_budget: Mapped[int] = mapped_column(Integer, default=0)
    work_mode: Mapped[str] = mapped_column(String(40), default="Remote")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped["User"] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(back_populates="job")
class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="Applied")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["Job"] = relationship(back_populates="applications")
    talent: Mapped["User"] = relationship(back_populates="applications")
class ExternalApplication(Base):
    """Persist applications for jobs still managed in the legacy jobs.csv workflow."""
    __tablename__ = "external_applications"
    __table_args__ = (UniqueConstraint("job_key", "talent_id", name="uq_external_application_job_talent"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_key: Mapped[str] = mapped_column(String(120), index=True)
    job_title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200), default="Company not specified")
    talent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="Applied")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    talent: Mapped["User"] = relationship()
Base.metadata.create_all(bind=engine)
# Lightweight migration for existing deployments.
if "picture_data" not in {col["name"] for col in inspect(engine).get_columns("profiles")}:
    with engine.begin() as connection:
        connection.execute(sql_text("ALTER TABLE profiles ADD COLUMN picture_data TEXT NOT NULL DEFAULT ''"))

if "company_id" not in {col["name"] for col in inspect(engine).get_columns("users")}:
    with engine.begin() as connection:
        connection.execute(sql_text("ALTER TABLE users ADD COLUMN company_id INTEGER"))

# Add saved-resume fields to existing profiles without losing current profile data.
profile_columns = {col["name"] for col in inspect(engine).get_columns("profiles")}
with engine.begin() as connection:
    if "resume_filename" not in profile_columns:
        connection.execute(sql_text("ALTER TABLE profiles ADD COLUMN resume_filename VARCHAR(255) NOT NULL DEFAULT ''"))
    if "resume_text" not in profile_columns:
        connection.execute(sql_text("ALTER TABLE profiles ADD COLUMN resume_text TEXT NOT NULL DEFAULT ''"))
    if "resume_data" not in profile_columns:
        connection.execute(sql_text("ALTER TABLE profiles ADD COLUMN resume_data TEXT NOT NULL DEFAULT ''"))

app = FastAPI(title="Instant Employee API", version="0.1.0", description="MVP API for talent profiles, jobs, and applications.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=160)

class BootstrapAdminIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    setup_key: str = Field(min_length=1, max_length=256)

class AdminPasswordResetIn(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)

class BulkCompanyUsersIn(BaseModel):
    employees: list[dict] = Field(min_length=1, max_length=100)

class LegacyJobsImportIn(BaseModel):
    jobs: list[dict] = Field(min_length=1, max_length=200)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
class ProfileIn(BaseModel):
    full_name: str = Field(default="", max_length=160)
    headline: str = Field(default="", max_length=200)
    skills: str = ""
    timezone: str = "Asia/Kolkata"
    availability: str = "Available"
    portfolio_url: str = ""
    picture_data: str = Field(default="", max_length=2800000)
    resume_filename: Optional[str] = Field(default=None, max_length=255)
    resume_text: Optional[str] = Field(default=None, max_length=1000000)
    resume_data: Optional[str] = Field(default=None, max_length=7000000)
class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    department: str = "Other"
    description: str = Field(min_length=10)
    required_skills: str = ""
    min_budget: int = Field(default=0, ge=0)
    max_budget: int = Field(default=0, ge=0)
    work_mode: str = "Remote"
    timezone: str = "Asia/Kolkata"
class ApplicationIn(BaseModel):
    resume_filename: str = ""
class ExternalApplicationIn(BaseModel):
    job_key: str = Field(min_length=1, max_length=120)
    job_title: str = Field(min_length=1, max_length=200)
    company_name: str = Field(default="Company not specified", max_length=200)
    resume_filename: str = Field(default="", max_length=255)
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310000).hex()
    return salt + "$" + digest
def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], digest)
    except ValueError: return False
def make_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(minutes=TOKEN_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)
def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]); user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="Account not found or disabled")
    return user
def organization_id(user: User) -> int:
    return user.company_id or user.id
def require_role(role: str):
    def role_checker(user: User = Depends(current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail=role + " account required")
        return user
    return role_checker
def profile_to_dict(p: Profile):
    return {"full_name":p.full_name,"headline":p.headline,"skills":p.skills,"timezone":p.timezone,"availability":p.availability,"portfolio_url":p.portfolio_url,"resume_filename":p.resume_filename or "","resume_text":p.resume_text or "","resume_uploaded":bool(p.resume_text),"picture_data":p.picture_data or ""}
@app.post("/auth/company/bulk-create")
def bulk_create_company_users(data: BulkCompanyUsersIn, admin: User = Depends(require_role("company")), db: Session = Depends(get_db)):
    """Create up to 100 company-role login accounts in one request."""
    if admin.company_id is not None:
        raise HTTPException(status_code=403, detail="Only the primary company admin can create employee accounts")
    created = []
    errors = []
    seen = set()
    for index, item in enumerate(data.employees, start=1):
        if not isinstance(item, dict):
            errors.append({"row": index, "error": "Expected an object with name and email"})
            continue
        name = str(item.get("name") or item.get("full_name") or "").strip()[:160]
        email = str(item.get("email", "")).strip().lower()
        password = str(item.get("password", "")).strip()
        if not name or not email or "@" not in email:
            errors.append({"row": index, "email": email, "error": "Valid name and email are required"})
            continue
        if email in seen:
            errors.append({"row": index, "email": email, "error": "Duplicate email in this batch"})
            continue
        seen.add(email)
        if db.query(User).filter(User.email == email).first():
            errors.append({"row": index, "email": email, "error": "Email already registered"})
            continue
        if not password:
            password = secrets.token_urlsafe(10)
        if len(password) < 8 or len(password) > 128:
            errors.append({"row": index, "email": email, "error": "Password must be 8-128 characters"})
            continue
        user = User(email=email, password_hash=hash_password(password), role="company", company_id=admin.id)
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id, full_name=name))
        created.append({"name": name, "email": email, "temporary_password": password, "role": "company"})
    if created:
        db.commit()
    else:
        db.rollback()
    return {"created_count": len(created), "created": created, "errors": errors}

@app.get("/health")
def health(): return {"status":"ok","service":"instant-employee-api","version":"0.1.0"}

@app.get("/health/database")
def database_health():
    """Check database connectivity and required schema without exposing credentials or data."""
    required_tables = {"users", "profiles", "jobs", "applications"}
    try:
        with engine.connect() as connection:
            connection.execute(sql_text("SELECT 1"))
        existing_tables = set(inspect(engine).get_table_names())
        missing_tables = sorted(required_tables - existing_tables)
        if missing_tables:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "schema_incomplete",
                    "database_dialect": engine.dialect.name,
                    "missing_required_tables": missing_tables,
                },
            )
        return {
            "status": "connected",
            "database_dialect": engine.dialect.name,
            "required_tables_present": True,
        }
    except HTTPException:
        raise
    except Exception:
        # Do not return database URLs, usernames, passwords, or raw driver errors.
        raise HTTPException(
            status_code=503,
            detail={"status": "connection_failed", "message": "Database connection check failed"},
        )
@app.post("/auth/company/status")
def company_admin_status(
    setup_key: str = Header(default="", alias="X-Admin-Setup-Key"),
    db: Session = Depends(get_db),
):
    """Reveal the primary admin email only to a caller with the private setup key."""
    expected_key = os.getenv("ADMIN_SETUP_KEY", "")
    if not expected_key:
        raise HTTPException(status_code=503, detail="Admin setup is not configured")
    if not setup_key or not secrets.compare_digest(setup_key, expected_key):
        raise HTTPException(status_code=403, detail="Invalid admin setup key")
    admin = db.query(User).filter(User.role == "company", User.company_id.is_(None)).first()
    if not admin:
        return {"admin_exists": False, "email": None}
    return {"admin_exists": True, "email": admin.email}


@app.post("/auth/company/reset-password")
def reset_company_admin_password(
    data: AdminPasswordResetIn,
    setup_key: str = Header(default="", alias="X-Admin-Setup-Key"),
    db: Session = Depends(get_db),
):
    """Reset the existing primary company admin password using the private setup key."""
    expected_key = os.getenv("ADMIN_SETUP_KEY", "")
    if not expected_key:
        raise HTTPException(status_code=503, detail="Admin password reset is not configured")
    if not setup_key or not secrets.compare_digest(setup_key, expected_key):
        raise HTTPException(status_code=403, detail="Invalid admin setup key")
    admin = db.query(User).filter(
        User.role == "company",
        User.company_id.is_(None),
        User.email == data.email.lower(),
    ).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Primary company admin not found for this email")
    admin.password_hash = hash_password(data.new_password)
    db.commit()
    return {"status": "password_reset", "email": admin.email}


@app.post("/auth/company/bootstrap", response_model=TokenOut, status_code=201)
def bootstrap_company_admin(data: BootstrapAdminIn, db: Session = Depends(get_db)):
    """Create the first company admin only with a private Render environment setup key."""
    setup_key = os.getenv("ADMIN_SETUP_KEY", "")
    if not setup_key:
        raise HTTPException(status_code=503, detail="Initial admin setup is not enabled. Configure ADMIN_SETUP_KEY on the API host.")
    if not secrets.compare_digest(data.setup_key, setup_key):
        raise HTTPException(status_code=403, detail="Invalid admin setup key")
    if db.query(User).filter(User.role == "company", User.company_id.is_(None)).first():
        raise HTTPException(status_code=409, detail="A primary company admin already exists")
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(data.password), role="company", company_id=None)
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, full_name=data.full_name.strip()))
    db.commit()
    db.refresh(user)
    return {"access_token": make_token(user)}

@app.post("/auth/signup", response_model=TokenOut, status_code=201)
def signup(data: SignupIn, db: Session = Depends(get_db)):
    """Public self-service signup is restricted to talent accounts."""
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(data.password), role="talent")
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, full_name=data.full_name))
    db.commit()
    db.refresh(user)
    return {"access_token": make_token(user)}
@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username.strip().lower()).first()
    # Disabled accounts must not receive fresh access tokens.
    if not user or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": make_token(user)}
@app.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p=db.query(Profile).filter(Profile.user_id==user.id).first()
    return {"id":user.id,"email":user.email,"role":user.role,"company_id":user.company_id,"profile":profile_to_dict(p) if p else None}
@app.get("/profiles/me")
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p=db.query(Profile).filter(Profile.user_id==user.id).first()
    if not p: raise HTTPException(status_code=404,detail="Profile not found")
    result=profile_to_dict(p); keys=["full_name","headline","skills","timezone","availability","portfolio_url","resume_filename"]
    result["completion_percent"]=round(sum(bool(result[k]) for k in keys)/len(keys)*100); return result
@app.put("/profiles/me")
def update_profile(data: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p=db.query(Profile).filter(Profile.user_id==user.id).first()
    if not p: p=Profile(user_id=user.id); db.add(p)
    values = data.model_dump()
    # Optional resume fields are only changed when explicitly supplied.
    for k, v in values.items():
        if k in {"resume_text", "resume_data", "resume_filename"}:
            if v is not None:
                setattr(p, k, v)
        else:
            setattr(p, k, v)
    db.commit(); db.refresh(p); result=profile_to_dict(p); keys=["full_name","headline","skills","timezone","availability","portfolio_url","resume_filename"]
    result["completion_percent"]=round(sum(bool(result[k]) for k in keys)/len(keys)*100); return result
@app.get("/jobs")
def list_jobs(q: str="", department: str="", work_mode: str="", db: Session=Depends(get_db)):
    query=db.query(Job).filter(Job.is_active.is_(True))
    if q: query=query.filter((Job.title.ilike("%"+q+"%"))|(Job.description.ilike("%"+q+"%"))|(Job.required_skills.ilike("%"+q+"%")))
    if department: query=query.filter(Job.department==department)
    if work_mode: query=query.filter(Job.work_mode==work_mode)
    return [{"id":j.id,"title":j.title,"department":j.department,"description":j.description,"required_skills":j.required_skills,"min_budget":j.min_budget,"max_budget":j.max_budget,"work_mode":j.work_mode,"timezone":j.timezone,"created_at":j.created_at.isoformat(),"company_name":j.company.email} for j in query.order_by(Job.created_at.desc()).all()]
@app.post("/jobs", status_code=201)
def create_job(data: JobIn, user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    if data.max_budget and data.min_budget>data.max_budget: raise HTTPException(status_code=422,detail="Minimum budget cannot exceed maximum budget")
    job=Job(company_id=organization_id(user),**data.model_dump()); db.add(job); db.commit(); db.refresh(job)
    return {"id":job.id,"title":job.title,"status":"active"}
@app.get("/jobs/mine")
def my_jobs(user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    jobs=db.query(Job).filter(Job.company_id==organization_id(user)).order_by(Job.created_at.desc()).all()
    return [{
        "id": j.id,
        "title": j.title,
        "department": j.department,
        "description": j.description,
        "required_skills": j.required_skills,
        "min_budget": j.min_budget,
        "max_budget": j.max_budget,
        "work_mode": j.work_mode,
        "timezone": j.timezone,
        "applications_count": len(j.applications),
        "is_active": j.is_active,
    } for j in jobs]

@app.put("/jobs/{job_id}")
def update_job(job_id: int, data: JobIn, user: User = Depends(require_role("company")), db: Session = Depends(get_db)):
    """Update a job owned by the authenticated company organization."""
    if data.max_budget and data.min_budget > data.max_budget:
        raise HTTPException(status_code=422, detail="Minimum budget cannot exceed maximum budget")
    job = db.get(Job, job_id)
    if not job or job.company_id != organization_id(user):
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in data.model_dump().items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "title": job.title, "status": "active" if job.is_active else "closed"}


@app.patch("/jobs/{job_id}/status")
def update_job_status(job_id: int, is_active: bool, user: User = Depends(require_role("company")), db: Session = Depends(get_db)):
    """Activate or close a job without deleting its application history."""
    job = db.get(Job, job_id)
    if not job or job.company_id != organization_id(user):
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = is_active
    db.commit()
    return {"id": job.id, "is_active": job.is_active, "status": "active" if job.is_active else "closed"}


@app.delete("/jobs/{job_id}", status_code=200)
def close_job(job_id: int, user: User = Depends(require_role("company")), db: Session = Depends(get_db)):
    """Soft-delete a job by closing it, preserving application history."""
    job = db.get(Job, job_id)
    if not job or job.company_id != organization_id(user):
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = False
    db.commit()
    return {"id": job.id, "status": "closed"}


@app.post("/jobs/import-legacy")
def import_legacy_jobs(data: LegacyJobsImportIn, user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    """Import legacy CSV jobs into the signed-in primary company's database account."""
    if user.company_id is not None:
        raise HTTPException(status_code=403, detail="Only the primary company admin can import legacy jobs")
    imported = []
    skipped = []
    existing = {
        (job.title.strip().casefold(), job.department.strip().casefold())
        for job in db.query(Job).filter(Job.company_id == user.id).all()
    }
    for index, item in enumerate(data.jobs, start=1):
        title = str(item.get("title") or item.get("Job Title") or "").strip()[:200]
        department = str(item.get("department") or item.get("Department") or "Other").strip()[:120] or "Other"
        description = str(item.get("description") or item.get("Description") or "").strip()
        skills = str(item.get("required_skills") or item.get("Required Skills") or "").strip()
        try:
            min_budget = max(0, int(float(item.get("min_budget", item.get("Minimum Budget", 0)) or 0)))
            max_budget = max(0, int(float(item.get("max_budget", item.get("Maximum Budget", 0)) or 0)))
        except (TypeError, ValueError):
            skipped.append({"row": index, "title": title, "reason": "Budget values are invalid"})
            continue
        work_mode = str(item.get("work_mode") or item.get("Work Mode") or "Remote").strip()[:40] or "Remote"
        timezone_name = str(item.get("timezone") or item.get("Timezone") or "Asia/Kolkata").strip()[:80] or "Asia/Kolkata"
        if len(title) < 2 or len(description) < 10:
            skipped.append({"row": index, "title": title, "reason": "Job title or description is missing/too short"})
            continue
        if max_budget and min_budget > max_budget:
            skipped.append({"row": index, "title": title, "reason": "Minimum budget exceeds maximum budget"})
            continue
        dedupe_key = (title.casefold(), department.casefold())
        if dedupe_key in existing:
            skipped.append({"row": index, "title": title, "reason": "This job already exists for your company"})
            continue
        job = Job(company_id=user.id, title=title, department=department, description=description,
                  required_skills=skills, min_budget=min_budget, max_budget=max_budget,
                  work_mode=work_mode, timezone=timezone_name, is_active=True)
        db.add(job)
        db.flush()
        imported.append({"id": job.id, "title": title})
        existing.add(dedupe_key)
    if imported:
        db.commit()
    else:
        db.rollback()
    return {"imported_count": len(imported), "imported": imported, "skipped": skipped}
@app.post("/jobs/{job_id}/apply", status_code=201)
def apply(job_id: int, data: ApplicationIn, user: User=Depends(require_role("talent")), db: Session=Depends(get_db)):
    job=db.get(Job,job_id)
    if not job or not job.is_active: raise HTTPException(status_code=404,detail="Active job not found")
    profile=db.query(Profile).filter(Profile.user_id==user.id).first()
    if not profile or not profile.resume_text.strip():
        raise HTTPException(status_code=400,detail="Upload a resume to your candidate profile before applying")
    if db.query(Application).filter(Application.job_id==job_id,Application.talent_id==user.id).first(): raise HTTPException(status_code=409,detail="Already applied to this job")
    a=Application(job_id=job_id,talent_id=user.id,resume_filename=profile.resume_filename); db.add(a); db.commit(); db.refresh(a)
    return {"id":a.id,"job_id":job_id,"job_title":job.title,"status":a.status,"applied_at":a.created_at.isoformat()}
@app.get("/applications/me")
def my_applications(user: User=Depends(require_role("talent")), db: Session=Depends(get_db)):
    rows=db.query(Application).filter(Application.talent_id==user.id).order_by(Application.created_at.desc()).all()
    return [{"id":a.id,"job_id":a.job_id,"job_title":a.job.title,"company_id":a.job.company_id,"company_name":a.job.company.email,"applied_at":a.created_at.isoformat(),"status":a.status,"resume_filename":a.resume_filename} for a in rows]
@app.post("/applications/external", status_code=201)
def apply_to_csv_job(data: ExternalApplicationIn, user: User=Depends(require_role("talent")), db: Session=Depends(get_db)):
    """Save an application for a job currently stored in the Streamlit jobs.csv file."""
    job_key = data.job_key.strip()
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile or not profile.resume_text.strip():
        raise HTTPException(status_code=400, detail="Upload a resume to your candidate profile before applying")
    if db.query(ExternalApplication).filter(
        ExternalApplication.job_key == job_key,
        ExternalApplication.talent_id == user.id,
    ).first():
        raise HTTPException(status_code=409, detail="Already applied to this job")
    application = ExternalApplication(
        job_key=job_key,
        job_title=data.job_title.strip(),
        company_name=data.company_name.strip() or "Company not specified",
        talent_id=user.id,
        resume_filename=profile.resume_filename,
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        # The database constraint is the final guard against simultaneous duplicate requests.
        db.rollback()
        raise HTTPException(status_code=409, detail="Already applied to this job")
    db.refresh(application)
    return {
        "id": application.id,
        "job_key": application.job_key,
        "job_title": application.job_title,
        "company_name": application.company_name,
        "status": application.status,
        "applied_at": application.created_at.isoformat(),
        "resume_filename": application.resume_filename,
    }

@app.get("/applications/external/me")
def my_external_applications(user: User=Depends(require_role("talent")), db: Session=Depends(get_db)):
    rows = db.query(ExternalApplication).filter(
        ExternalApplication.talent_id == user.id
    ).order_by(ExternalApplication.created_at.desc()).all()
    return [{
        "id": a.id,
        "job_key": a.job_key,
        "job_title": a.job_title,
        "company_name": a.company_name,
        "applied_at": a.created_at.isoformat(),
        "status": a.status,
        "resume_filename": a.resume_filename,
    } for a in rows]
@app.get("/applications/company")
def company_applications(user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    """Return applications only for jobs owned by the authenticated company."""
    rows = (
        db.query(Application)
        .join(Job, Application.job_id == Job.id)
        .filter(Job.company_id == organization_id(user))
        .order_by(Application.created_at.desc())
        .all()
    )
    return [{
        "id": a.id,
        "job_id": a.job_id,
        "job_title": a.job.title,
        "candidate_id": a.talent_id,
        "candidate_email": a.talent.email,
        "candidate_name": a.talent.profile.full_name if a.talent.profile else "",
        "status": a.status,
        "applied_at": a.created_at.isoformat(),
        "resume_filename": a.resume_filename,
        "resume_text": a.talent.profile.resume_text if a.talent.profile else "",
        "job_description": a.job.description,
        "candidate_skills": a.talent.profile.skills if a.talent.profile else "",
    } for a in rows]

@app.get("/jobs/{job_id}/applications")
def job_applications(job_id: int, user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    job=db.get(Job,job_id)
    if not job or job.company_id!=organization_id(user): raise HTTPException(status_code=404,detail="Job not found")
    return [{"id":a.id,"talent_id":a.talent_id,"email":a.talent.email,"full_name":a.talent.profile.full_name if a.talent.profile else "","status":a.status,"applied_at":a.created_at.isoformat(),"resume_filename":a.resume_filename} for a in job.applications]
@app.get("/applications/{application_id}/resume")
def download_application_resume(application_id: int, user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    """Return a saved PDF only to the company that owns the job application."""
    application = db.get(Application, application_id)
    if not application or application.job.company_id != organization_id(user):
        raise HTTPException(status_code=404, detail="Application not found")
    profile = application.talent.profile
    if not profile or not profile.resume_data:
        raise HTTPException(status_code=404, detail="Candidate has not saved a downloadable resume")
    return {
        "filename": profile.resume_filename or "candidate_resume.pdf",
        "content_type": "application/pdf",
        "resume_data": profile.resume_data,
    }

@app.patch("/applications/{application_id}/status")
def update_status(application_id: int, new_status: str="Under Review", user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    allowed={"Applied","Under Review","Shortlisted","Rejected","Selected"}
    if new_status not in allowed: raise HTTPException(status_code=422,detail="Invalid application status")
    a=db.get(Application,application_id)
    if not a or a.job.company_id!=organization_id(user): raise HTTPException(status_code=404,detail="Application not found")
    a.status=new_status; db.commit(); return {"id":a.id,"status":a.status}

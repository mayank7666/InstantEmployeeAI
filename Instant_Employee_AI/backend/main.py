"""Instant Employee API MVP: accounts, profiles, jobs, and applications."""
import os, hashlib, secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./instant_employee.db")
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_SECRET_KEY_BEFORE_DEPLOYING")
ALGORITHM = "HS256"
TOKEN_MINUTES = 720
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="talent")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
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
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Instant Employee API", version="0.1.0", description="MVP API for talent profiles, jobs, and applications.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="talent", pattern="^(talent|company)$")
    full_name: str = Field(default="", max_length=160)
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
    resume_filename: str = ""
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
def require_role(role: str, user: User = Depends(current_user)) -> User:
    if user.role != role: raise HTTPException(status_code=403, detail=role + " account required")
    return user
def profile_to_dict(p: Profile):
    return {"full_name":p.full_name,"headline":p.headline,"skills":p.skills,"timezone":p.timezone,"availability":p.availability,"portfolio_url":p.portfolio_url,"resume_filename":p.resume_filename}
@app.get("/health")
def health(): return {"status":"ok","service":"instant-employee-api","version":"0.1.0"}
@app.post("/auth/signup", response_model=TokenOut, status_code=201)
def signup(data: SignupIn, db: Session = Depends(get_db)):
    email=data.email.lower()
    if db.query(User).filter(User.email==email).first(): raise HTTPException(status_code=409,detail="Email already registered")
    user=User(email=email,password_hash=hash_password(data.password),role=data.role); db.add(user); db.flush()
    db.add(Profile(user_id=user.id,full_name=data.full_name)); db.commit(); db.refresh(user)
    return {"access_token":make_token(user)}
@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user=db.query(User).filter(User.email==form.username.lower()).first()
    if not user or not verify_password(form.password,user.password_hash): raise HTTPException(status_code=401,detail="Incorrect email or password")
    return {"access_token":make_token(user)}
@app.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p=db.query(Profile).filter(Profile.user_id==user.id).first()
    return {"id":user.id,"email":user.email,"role":user.role,"profile":profile_to_dict(p) if p else None}
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
    for k,v in data.model_dump().items(): setattr(p,k,v)
    db.commit(); db.refresh(p); result=profile_to_dict(p); keys=["full_name","headline","skills","timezone","availability","portfolio_url","resume_filename"]
    result["completion_percent"]=round(sum(bool(result[k]) for k in keys)/len(keys)*100); return result
@app.get("/jobs")
def list_jobs(q: str="", department: str="", work_mode: str="", db: Session=Depends(get_db)):
    query=db.query(Job).filter(Job.is_active.is_(True))
    if q: query=query.filter((Job.title.ilike("%"+q+"%"))|(Job.description.ilike("%"+q+"%"))|(Job.required_skills.ilike("%"+q+"%")))
    if department: query=query.filter(Job.department==department)
    if work_mode: query=query.filter(Job.work_mode==work_mode)
    return [{"id":j.id,"title":j.title,"department":j.department,"description":j.description,"required_skills":j.required_skills,"min_budget":j.min_budget,"max_budget":j.max_budget,"work_mode":j.work_mode,"timezone":j.timezone,"created_at":j.created_at.isoformat()} for j in query.order_by(Job.created_at.desc()).all()]
@app.post("/jobs", status_code=201)
def create_job(data: JobIn, user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    if data.max_budget and data.min_budget>data.max_budget: raise HTTPException(status_code=422,detail="Minimum budget cannot exceed maximum budget")
    job=Job(company_id=user.id,**data.model_dump()); db.add(job); db.commit(); db.refresh(job)
    return {"id":job.id,"title":job.title,"status":"active"}
@app.get("/jobs/mine")
def my_jobs(user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    jobs=db.query(Job).filter(Job.company_id==user.id).order_by(Job.created_at.desc()).all()
    return [{"id":j.id,"title":j.title,"department":j.department,"applications_count":len(j.applications),"is_active":j.is_active} for j in jobs]
@app.post("/jobs/{job_id}/apply", status_code=201)
def apply(job_id: int, data: ApplicationIn, user: User=Depends(require_role("talent")), db: Session=Depends(get_db)):
    job=db.get(Job,job_id)
    if not job or not job.is_active: raise HTTPException(status_code=404,detail="Active job not found")
    if db.query(Application).filter(Application.job_id==job_id,Application.talent_id==user.id).first(): raise HTTPException(status_code=409,detail="Already applied to this job")
    a=Application(job_id=job_id,talent_id=user.id,resume_filename=data.resume_filename); db.add(a); db.commit(); db.refresh(a)
    return {"id":a.id,"job_id":job_id,"job_title":job.title,"status":a.status,"applied_at":a.created_at.isoformat()}
@app.get("/applications/me")
def my_applications(user: User=Depends(require_role("talent")), db: Session=Depends(get_db)):
    rows=db.query(Application).filter(Application.talent_id==user.id).order_by(Application.created_at.desc()).all()
    return [{"id":a.id,"job_id":a.job_id,"job_title":a.job.title,"company_id":a.job.company_id,"applied_at":a.created_at.isoformat(),"status":a.status,"resume_filename":a.resume_filename} for a in rows]
@app.get("/jobs/{job_id}/applications")
def job_applications(job_id: int, user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    job=db.get(Job,job_id)
    if not job or job.company_id!=user.id: raise HTTPException(status_code=404,detail="Job not found")
    return [{"id":a.id,"talent_id":a.talent_id,"email":a.talent.email,"full_name":a.talent.profile.full_name if a.talent.profile else "","status":a.status,"applied_at":a.created_at.isoformat(),"resume_filename":a.resume_filename} for a in job.applications]
@app.patch("/applications/{application_id}/status")
def update_status(application_id: int, new_status: str="Under Review", user: User=Depends(require_role("company")), db: Session=Depends(get_db)):
    allowed={"Applied","Under Review","Shortlisted","Rejected","Selected"}
    if new_status not in allowed: raise HTTPException(status_code=422,detail="Invalid application status")
    a=db.get(Application,application_id)
    if not a or a.job.company_id!=user.id: raise HTTPException(status_code=404,detail="Application not found")
    a.status=new_status; db.commit(); return {"id":a.id,"status":a.status}

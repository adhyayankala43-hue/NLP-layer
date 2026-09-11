import os
from dotenv import load_dotenv

# MUST BE AT THE TOP: Load environment variables from .env file for local testing
load_dotenv("credential keys.env")

import json
import random
import secrets
import hashlib
import threading
import urllib.request
import urllib.error
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

# --- Database & AI Imports ---
import pymongo
try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
EMAIL_API_KEY = os.getenv("EMAIL_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
ADMIN_STATIC_PASSWORD = os.getenv("ADMIN_PASSWORD", "1!")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
MONGO_URI = os.getenv("MONGO_URI")

app = FastAPI(title="Ai Registration Portal - MongoDB Integrated", version="24.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# --- AI Setup ---
# --- AI Setup ---
try:
    # 1. Primary: The smartest model
    llm_primary = ChatGroq(
        model="openai/gpt-oss-120b", 
        groq_api_key=GROQ_API_KEY, 
        temperature=0, 
        max_tokens=600
    )
    
    # 2. Fallback 1: Fast & reliable 27B model
    llm_backup_1 = ChatGroq(
        model="qwen/qwen3.8-27b", 
        groq_api_key=GROQ_API_KEY, 
        temperature=0, 
        max_tokens=600
    )
    
    # 3. Fallback 2: The slightly older Qwen architecture
    llm_backup_2 = ChatGroq(
        model="qwen/qwen3.6-27b", 
        groq_api_key=GROQ_API_KEY, 
        temperature=0, 
        max_tokens=600
    )
    
    # 4. Fallback 3: The fast 20B OpenAI model
    llm_backup_3 = ChatGroq(
        model="openai/gpt-oss-20b", 
        groq_api_key=GROQ_API_KEY, 
        temperature=0, 
        max_tokens=600
    )

    # Standard LLM fallback chain (used for final synthesis without tools)
    llm = llm_primary.with_fallbacks([llm_backup_1, llm_backup_2, llm_backup_3])
    
    print("✅ AI Models configured with 4-layer deep automatic fallbacks!")
except Exception as e:
    print(f"AI Setup Error: {e}")
    llm = None
    llm_primary = None

# --- MongoDB Setup ---
try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client["university_portal"]
    mongo_collection = mongo_db["system_data"]
    # Ping to test connection on startup
    mongo_client.admin.command('ping')
    print("✅ Successfully connected to MongoDB!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

FILE_LOCK = threading.Lock()

DEFAULT_DATA = {
    "courses": {
        "CS101": {"title": "Intro to Computer Science", "dept": "CS", "credits": 3, "seats": 5, "days": "Mon/Wed", "start_time": "10:00 AM", "end_time": "11:30 AM"},
        "CS301": {"title": "Data Structures & Algorithms", "dept": "CS", "credits": 4, "seats": 2, "days": "Tue/Thu", "start_time": "02:00 PM", "end_time": ""}, 
        "MATH101": {"title": "Calculus I", "dept": "MATH", "credits": 4, "seats": 8, "days": "Mon/Wed/Fri", "start_time": "09:00 AM", "end_time": "10:00 AM"},
        "MATH202": {"title": "Linear Algebra", "dept": "MATH", "credits": 3, "seats": 12, "days": "Tue/Thu", "start_time": "11:00 AM", "end_time": "12:30 PM"},
        "BIO101": {"title": "General Biology", "dept": "BIO", "credits": 4, "seats": 3, "days": "Mon/Wed", "start_time": "01:00 PM", "end_time": ""},
        "ENG101": {"title": "English Composition", "dept": "ENG", "credits": 3, "seats": 20, "days": "Tue/Thu", "start_time": "09:30 AM", "end_time": "11:00 AM"},
        "PHY201": {"title": "General Physics", "dept": "PHY", "credits": 4, "seats": 15, "days": "Mon/Wed/Fri", "start_time": "11:00 AM", "end_time": "12:00 PM"},
        "CHEM101": {"title": "Intro to Chemistry", "dept": "CHEM", "credits": 4, "seats": 18, "days": "Tue/Thu", "start_time": "01:00 PM", "end_time": "03:00 PM"},
        "HIST101": {"title": "World History", "dept": "HIST", "credits": 3, "seats": 25, "days": "Mon/Wed", "start_time": "03:00 PM", "end_time": ""},
        "ECON101": {"title": "Microeconomics", "dept": "ECON", "credits": 3, "seats": 30, "days": "Tue/Thu", "start_time": "03:30 PM", "end_time": "05:00 PM"},
        "PSY101": {"title": "Intro to Psychology", "dept": "PSY", "credits": 3, "seats": 40, "days": "Mon/Wed", "start_time": "04:00 PM", "end_time": ""},
        "ART101": {"title": "Art History", "dept": "ART", "credits": 3, "seats": 15, "days": "Fri", "start_time": "10:00 AM", "end_time": "01:00 PM"},
        "PHIL101": {"title": "Intro to Philosophy", "dept": "PHIL", "credits": 3, "seats": 20, "days": "Tue/Thu", "start_time": "10:00 AM", "end_time": ""},
        "SOC101": {"title": "Intro to Sociology", "dept": "SOC", "credits": 3, "seats": 35, "days": "Mon/Wed", "start_time": "02:00 PM", "end_time": "03:30 PM"},
        "STAT201": {"title": "Applied Statistics", "dept": "STAT", "credits": 3, "seats": 25, "days": "Tue/Thu", "start_time": "04:00 PM", "end_time": "05:30 PM"}
    },
    "students": {},
    "analytics": {
        "total_logins": 0,
        "registrations": 0
    },
    "chat_logs": []
}

ACTIVE_ADMIN_SESSIONS: Dict[str, datetime] = {}
OTP_STORE: Dict[str, Dict[str, Any]] = {}
CHAT_HISTORY: Dict[str, List[Any]] = {}

# ============================================================
# CRYPTOGRAPHIC & STORAGE HELPERS
# ============================================================

def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}:{hashed.hex()}"

def verify_password(password: str, hashed_str: str) -> bool:
    try:
        salt, stored_hash = hashed_str.split(":")
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return secrets.compare_digest(computed.hex(), stored_hash)
    except Exception:
        return False

def load_database() -> Dict[str, Any]:
    with FILE_LOCK:
        doc = mongo_collection.find_one({"_id": "main_data"})
        if not doc:
            # Initialize with default data if the database is empty
            mongo_collection.insert_one({"_id": "main_data", **DEFAULT_DATA})
            return DEFAULT_DATA
        
        # Remove the internal MongoDB ID before returning the dictionary
        doc.pop("_id", None)
        
        if "analytics" not in doc:
            doc["analytics"] = {"total_logins": 0, "registrations": 0}
        if "chat_logs" not in doc:
            doc["chat_logs"] = []
            
        return doc

def save_database(data: Dict[str, Any]) -> None:
    with FILE_LOCK:
        mongo_collection.update_one(
            {"_id": "main_data"},
            {"$set": data},
            upsert=True
        )

def require_admin(auth: HTTPAuthorizationCredentials = Security(security)):
    token = auth.credentials
    expiry = ACTIVE_ADMIN_SESSIONS.get(token)
    if not expiry or datetime.now(timezone.utc) > expiry:
        ACTIVE_ADMIN_SESSIONS.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired or invalid token.")
    return True

# ============================================================
# REAL EMAIL DISPATCH (BREVO REST API)
# ============================================================

def send_real_verification_email(recipient_email: str, otp_code: str, verify_link: str):
    if not EMAIL_API_KEY or "YOUR_BREVO" in EMAIL_API_KEY:
        raise RuntimeError("Brevo API key is not configured in backend.")

    payload = {
        "sender": {"name": "CampusAI Portal", "email": SENDER_EMAIL},
        "to": [{"email": recipient_email}],
        "subject": "AI Registration Assistant Portal: Verify Your Registration",
        "htmlContent": f"""
        <div style="font-family: Arial, sans-serif; padding: 24px; color: #1e293b; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #4f46e5; margin-bottom: 8px;">Registration Verification</h2>
            <p style="font-size: 14px; color: #64748b;">Enter this single-use code on the registration screen:</p>
            <div style="font-size: 28px; font-weight: bold; letter-spacing: 6px; padding: 12px 18px; background: #f8fafc; border: 1px dashed #cbd5e1; display: inline-block; border-radius: 8px; margin: 12px 0; color: #0f172a;">
                {otp_code}
            </div>
            <p style="font-size: 13px; color: #64748b; margin-top: 16px;">Or verify automatically with a single tap:</p>
            <p>
                <a href="{verify_link}" style="background: #4f46e5; color: #ffffff; padding: 10px 18px; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 500; display: inline-block;">
                    Verify Email Address
                </a>
            </p>
        </div>
        """
    }

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": EMAIL_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status not in (200, 201, 202):
                raise RuntimeError(f"Brevo responded with status {resp.status}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        raise RuntimeError(f"Brevo API error: {err_body}")

def send_password_reset_email(recipient_email: str, new_pass: str):
    if not EMAIL_API_KEY or "YOUR_BREVO" in EMAIL_API_KEY:
        raise RuntimeError("Brevo API key is not configured in backend.")

    payload = {
        "sender": {"name": "CampusAI Portal", "email": SENDER_EMAIL},
        "to": [{"email": recipient_email}],
        "subject": "CampusAI Portal: Temporary Password",
        "htmlContent": f"""
        <div style="font-family: Arial, sans-serif; padding: 24px; color: #1e293b; max-width: 500px; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #4f46e5; margin-bottom: 8px;">Password Reset Request</h2>
            <p style="font-size: 14px; color: #64748b;">Your new permanent password is:</p>
            <div style="font-size: 24px; font-weight: bold; padding: 12px 18px; background: #f8fafc; border: 1px dashed #cbd5e1; display: inline-block; border-radius: 8px; margin: 12px 0; color: #0f172a;">
                {new_pass}
            </div>
            <p style="font-size: 13px; color: #64748b; margin-top: 16px;">Please use this password to log in. You can update it manually by server handler or token access.</p>
        </div>
        """
    }

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": EMAIL_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status not in (200, 201, 202):
                raise RuntimeError(f"Brevo responded with status {resp.status}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        raise RuntimeError(f"Brevo API error: {err_body}")

# ============================================================
# SCHEMAS WITH STRICT VALIDATION
# ============================================================

TIME_PATTERN = r"^(1[0-2]|0?[1-9]):[0-5][0-9] (AM|PM)$"
DAYS_PATTERN = r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)(/(Mon|Tue|Wed|Thu|Fri|Sat|Sun))*$"

class AdminLoginRequest(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=100)

class StudentUpdateRequest(BaseModel):
    student_id: str
    name: str = Field(..., max_length=100, pattern=r"^[a-zA-Z\s]+$")
    email: str = Field(..., max_length=100)
    field: str = Field(..., max_length=100)

class CourseCreateRequest(BaseModel):
    code: str = Field(..., max_length=10, pattern=r"^[A-Za-z]{2,4}\d{2,4}$")
    title: str = Field(..., max_length=100, pattern=r"^[0-9\s\-\&,]*[a-zA-Z][a-zA-Z0-9\s\-\&,]*$")
    dept: str = Field(..., max_length=10, pattern=r"^[A-Za-z]+$")
    credits: int = Field(..., ge=1, le=10)
    seats: int = Field(..., ge=0)
    days: str = Field(..., max_length=50, pattern=DAYS_PATTERN)
    start_time: str = Field(..., pattern=TIME_PATTERN)
    end_time: str = Field(default="", max_length=20)

    @model_validator(mode='after')
    def validate_time_bounds(self) -> 'CourseCreateRequest':
        if self.end_time:
            if not re.match(TIME_PATTERN, self.end_time):
                raise ValueError("end_time must match 'HH:MM AM/PM' format")
            start_dt = datetime.strptime(self.start_time, "%I:%M %p")
            end_dt = datetime.strptime(self.end_time, "%I:%M %p")
            if start_dt >= end_dt:
                raise ValueError("Strict Time Bound Error: end_time must be strictly after start_time.")
        return self

class CourseUpdateRequest(BaseModel):
    title: str = Field(..., max_length=100, pattern=r"^[0-9\s\-\&,]*[a-zA-Z][a-zA-Z0-9\s\-\&,]*$")
    dept: str = Field(..., max_length=10, pattern=r"^[A-Za-z]+$")
    credits: int = Field(..., ge=1, le=10)
    seats: int = Field(..., ge=0)
    days: str = Field(..., max_length=50, pattern=DAYS_PATTERN)
    start_time: str = Field(..., pattern=TIME_PATTERN)
    end_time: str = Field(default="", max_length=20)

    @model_validator(mode='after')
    def validate_time_bounds(self) -> 'CourseUpdateRequest':
        if self.end_time:
            if not re.match(TIME_PATTERN, self.end_time):
                raise ValueError("end_time must match 'HH:MM AM/PM' format")
            start_dt = datetime.strptime(self.start_time, "%I:%M %p")
            end_dt = datetime.strptime(self.end_time, "%I:%M %p")
            if start_dt >= end_dt:
                raise ValueError("Strict Time Bound Error: end_time must be strictly after start_time.")
        return self

class SendOTPRequest(BaseModel):
    target: str = Field(..., max_length=100)

class VerifyOTPRequest(BaseModel):
    target: str = Field(..., max_length=100)
    otp: str = Field(..., min_length=6, max_length=6)

class StudentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=60, pattern=r"^[a-zA-Z\s]+$")
    email: str = Field(..., max_length=100)
    phone: str = Field(..., pattern=r"^\+91[6-9]\d{9}$")
    password: str = Field(..., min_length=8, max_length=64)
    course: str = Field(..., max_length=50)

    @model_validator(mode='after')
    def validate_phone_not_dummy(self) -> 'StudentRegisterRequest':
        local_num = self.phone[3:]
        # Reject if all local digits are identically repeated (e.g. 9999999999)
        if len(set(local_num)) == 1:
            raise ValueError("Dummy phone numbers with repeated digits are not allowed.")
        # Reject purely sequential numbers
        if local_num in "9876543210" or local_num in "6789012345":
            raise ValueError("Sequential dummy phone numbers are not allowed.")
        return self

class StudentLoginRequest(BaseModel):
    email: str = Field(..., max_length=100)
    password: str = Field(..., max_length=64)

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=100)

class ChatRequest(BaseModel):
    student_id: str
    message: str = Field(..., max_length=500)

# ============================================================
# AUTHENTICATION & VERIFICATION ENDPOINTS
# ============================================================

@app.post("/api/auth/send-otp")
async def handle_send_otp(req: SendOTPRequest):
    recipient_email = req.target.lower().strip()
    if not recipient_email or "@" not in recipient_email:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    otp_val = f"{secrets.randbelow(900000) + 100000}"
    link_token = secrets.token_urlsafe(32)
    verify_link = f"{APP_BASE_URL}/verify-email-link?email={recipient_email}&token={link_token}"

    OTP_STORE[recipient_email] = {
        "otp": otp_val,
        "token": link_token,
        "verified": False,
        "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)
    }

    try:
        send_real_verification_email(recipient_email, otp_val, verify_link)
    except Exception as e:
        OTP_STORE.pop(recipient_email, None)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "message": f"Verification code successfully sent to {recipient_email}. Check your inbox and spam folder."
    }

@app.get("/verify-email-link", response_class=HTMLResponse)
async def verify_email_link(email: str, token: str):
    clean_email = email.lower().strip()
    record = OTP_STORE.get(clean_email)

    if not record or datetime.now(timezone.utc) > record["expires_at"]:
        raise HTTPException(status_code=400, detail="Verification link expired or invalid.")

    if not secrets.compare_digest(record.get("token", ""), token):
        raise HTTPException(status_code=400, detail="Invalid verification token.")

    record["verified"] = True
    return """
    <html><body style="font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 80vh; background: #f8fafc;">
        <div style="border: 1px solid #e2e8f0; background: white; padding: 32px; border-radius: 16px; text-align: center;">
            <h2 style="color: #16a34a; margin-bottom: 8px;">Email Verified Successfully ✅</h2>
            <p style="color: #64748b;">You can return to the registration window to finish account setup.</p>
        </div>
    </body></html>
    """

@app.get("/api/auth/check-status")
async def check_status(target: str):
    clean_target = target.lower().strip()
    return {"verified": OTP_STORE.get(clean_target, {}).get("verified", False)}

@app.post("/api/auth/verify-otp")
async def handle_verify_otp(req: VerifyOTPRequest):
    recipient_email = req.target.lower().strip()
    record = OTP_STORE.get(recipient_email)

    if not record:
        raise HTTPException(status_code=400, detail="No pending verification found. Request a new code.")
    if datetime.now(timezone.utc) > record["expires_at"]:
        OTP_STORE.pop(recipient_email, None)
        raise HTTPException(status_code=400, detail="Code expired. Request a new one.")
    if record["attempts"] >= 5:
        OTP_STORE.pop(recipient_email, None)
        raise HTTPException(status_code=429, detail="Too many invalid attempts. Session revoked.")

    record["attempts"] += 1

    if not secrets.compare_digest(record["otp"], req.otp.strip()):
        raise HTTPException(status_code=400, detail="Invalid passcode.")

    record["verified"] = True
    return {"status": "success", "message": "Email successfully verified."}

@app.post("/api/auth/register-student")
async def register_student(req: StudentRegisterRequest):
    clean_email = req.email.lower().strip()

    if not OTP_STORE.get(clean_email, {}).get("verified", False):
        raise HTTPException(status_code=403, detail="Email verification is required before registration.")

    db = load_database()
    for sdata in db["students"].values():
        if sdata.get("email") == clean_email:
            raise HTTPException(status_code=409, detail="An account with this email address already exists.")

    new_id = str(int(max(db["students"].keys(), key=lambda x: int(x) if x.isdigit() else 10000)) + 1) if db["students"] else "10001"

    db["students"][new_id] = {
        "name": req.name.strip(),
        "email": clean_email,
        "phone": req.phone.strip(),
        "password_hash": hash_password(req.password),
        "field": req.course.strip(),
        "enrolled_courses": [],
    }
    db["analytics"]["registrations"] = db.get("analytics", {}).get("registrations", 0) + 1
    db["analytics"]["total_logins"] = db.get("analytics", {}).get("total_logins", 0) + 1
    
    save_database(db)
    OTP_STORE.pop(clean_email, None)
    return {"status": "success", "student_id": new_id, "name": req.name.strip()}

@app.post("/api/auth/student-login")
async def student_login(req: StudentLoginRequest):
    clean_email = req.email.lower().strip()
    db = load_database()

    for sid, sdata in db["students"].items():
        if sdata.get("email") == clean_email:
            if verify_password(req.password, sdata.get("password_hash", "")):
                db["analytics"]["total_logins"] = db.get("analytics", {}).get("total_logins", 0) + 1
                save_database(db)
                return {"status": "success", "student_id": sid, "student": {"name": sdata["name"], "email": sdata["email"]}}
            raise HTTPException(status_code=401, detail="Invalid credentials.")

    raise HTTPException(status_code=401, detail="Invalid credentials.")

@app.post("/api/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    clean_email = req.email.lower().strip()
    db = load_database()
    
    target_sid = None
    for sid, sdata in db["students"].items():
        if sdata.get("email") == clean_email:
            target_sid = sid
            break
            
    if not target_sid:
        raise HTTPException(status_code=404, detail="This email is not registered in our system.")
        
    temp_pass = secrets.token_urlsafe(8)
    db["students"][target_sid]["password_hash"] = hash_password(temp_pass)
    save_database(db)
    
    try:
        send_password_reset_email(clean_email, temp_pass)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send the email. Please try again.")
        
    return {"status": "success", "message": "Temporary password dispatched successfully."}

# ============================================================
# ADMIN, MASTER CONTROL & ANALYTICS ENDPOINTS
# ============================================================

@app.post("/api/auth/admin-login")
async def admin_login(req: AdminLoginRequest):
    if req.username == "admin" and secrets.compare_digest(req.password, ADMIN_STATIC_PASSWORD):
        session_token = secrets.token_hex(32)
        ACTIVE_ADMIN_SESSIONS[session_token] = datetime.now(timezone.utc) + timedelta(hours=2)
        return {"status": "success", "token": session_token}
    raise HTTPException(status_code=401, detail="Unauthorized.")

@app.get("/api/admin/data")
async def admin_get_data(authorized: bool = Depends(require_admin)):
    db = load_database()
    sanitized = json.loads(json.dumps(db))
    for s in sanitized.get("students", {}).values():
        s.pop("password_hash", None)
    return sanitized

@app.post("/api/admin/hard-reset")
async def admin_hard_reset(authorized: bool = Depends(require_admin)):
    global CHAT_HISTORY, OTP_STORE
    db = load_database()
    db.clear()
    db.update(json.loads(json.dumps(DEFAULT_DATA)))
    save_database(db)
    CHAT_HISTORY.clear()
    OTP_STORE.clear()
    return {"status": "success", "message": "System factory reset complete."}

@app.post("/api/admin/add-course")
async def admin_add_course(req: CourseCreateRequest, authorized: bool = Depends(require_admin)):
    db = load_database()
    code = req.code.upper().strip()
    if code in db.get("courses", {}):
        raise HTTPException(status_code=400, detail=f"Course code {code} already exists.")
    
    db["courses"][code] = {
        "title": req.title.strip(),
        "dept": req.dept.upper().strip(),
        "credits": req.credits,
        "seats": req.seats,
        "days": req.days.strip(),
        "start_time": req.start_time.strip(),
        "end_time": req.end_time.strip()
    }
    save_database(db)
    return {"status": "success", "message": f"Course {code} added successfully."}

@app.put("/api/admin/update-course/{course_code}")
async def admin_update_course(course_code: str, req: CourseUpdateRequest, authorized: bool = Depends(require_admin)):
    db = load_database()
    code = course_code.upper().strip()
    if code not in db.get("courses", {}):
        raise HTTPException(status_code=404, detail="Course not found.")
    
    db["courses"][code].update({
        "title": req.title.strip(),
        "dept": req.dept.upper().strip(),
        "credits": req.credits,
        "seats": req.seats,
        "days": req.days.strip(),
        "start_time": req.start_time.strip(),
        "end_time": req.end_time.strip()
    })
    save_database(db)
    return {"status": "success", "message": f"Course {code} updated successfully."}

@app.delete("/api/admin/delete-course/{course_code}")
async def admin_delete_course(course_code: str, authorized: bool = Depends(require_admin)):
    db = load_database()
    code = course_code.upper().strip()
    if code not in db.get("courses", {}):
        raise HTTPException(status_code=404, detail="Course not found.")
    
    del db["courses"][code]
    for s in db.get("students", {}).values():
        enrolled = s.get("enrolled_courses", [])
        if code in enrolled:
            enrolled.remove(code)
            
    save_database(db)
    return {"status": "success", "message": f"Course {code} permanently deleted."}

@app.post("/api/admin/reset-catalog")
async def admin_reset_catalog(authorized: bool = Depends(require_admin)):
    db = load_database()
    db["courses"] = DEFAULT_DATA["courses"]
    save_database(db)
    return {"status": "success", "message": "Catalog restored to defaults."}

@app.get("/api/admin/analytics")
async def admin_get_analytics(authorized: bool = Depends(require_admin)):
    db = load_database()
    students = db.get("students", {})
    analytics = db.get("analytics", {})
    
    field_distribution = {}
    for s in students.values():
        field = s.get("field", "Unspecified").strip()
        if not field: field = "Unspecified"
        field_distribution[field] = field_distribution.get(field, 0) + 1

    return {
        "total_students": len(students),
        "total_logins": analytics.get("total_logins", 0),
        "total_registrations": analytics.get("registrations", 0),
        "field_distribution": field_distribution
    }

@app.post("/api/admin/update-student")
async def admin_update_student(req: StudentUpdateRequest, authorized: bool = Depends(require_admin)):
    db = load_database()
    sid = req.student_id.strip()
    if sid not in db["students"]:
        raise HTTPException(status_code=404, detail="Student record not found.")
    db["students"][sid].update({
        "name": req.name.strip(),
        "email": req.email.lower().strip(),
        "field": req.field.strip()
    })
    save_database(db)
    return {"status": "success"}

@app.delete("/api/admin/delete-student/{student_id}")
async def admin_delete_student(student_id: str, authorized: bool = Depends(require_admin)):
    db = load_database()
    sid = student_id.strip()
    if sid in db["students"]:
        del db["students"][sid]
        save_database(db)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Record not found.")

@app.post("/api/admin/clear-all-students")
async def admin_clear_all(authorized: bool = Depends(require_admin)):
    db = load_database()
    db["students"] = {}
    save_database(db)
    return {"status": "success"}

# ============================================================
# LLM TOOLS & AGENT ENGINE (WITH ANTI-HALLUCINATION)
# ============================================================

def format_schedule_string(info):
    days = info.get("days", "")
    start = info.get("start_time", "").strip()
    end = info.get("end_time", "").strip()
    
    if start and end:
        time_str = f"{start} to {end}"
    elif start:
        time_str = f"{start} onwards"
    else:
        time_str = "TBA"
        
    return f"{days} | {time_str}" if days else time_str

from langchain_core.tools import StructuredTool

def get_course_catalog_fn(course_code: Optional[str] = None, department: Optional[str] = None) -> str:
    """Retrieve catalog courses and their schedules. Filter by course_code or department."""
    db = load_database()
    results = []
    
    courses = db.get("courses", {})
    if course_code:
        code_clean = course_code.upper().strip()
        if code_clean in courses:
            info = courses[code_clean]
            status = "OPEN" if info.get("seats", 0) > 0 else "FULL"
            schedule_str = format_schedule_string(info)
            return f"• {code_clean}: {info.get('title')} ({info.get('credits')} Cr) | {schedule_str} | Seats: {info.get('seats')} ({status})"
        return f"Course {code_clean} not found in catalog."

    for code, info in courses.items():
        if department and info.get("dept", "").upper() != department.upper().strip():
            continue
        status = "OPEN" if info.get("seats", 0) > 0 else "FULL"
        schedule_str = format_schedule_string(info)
        results.append(f"• {code}: {info.get('title')} ({info.get('credits')} Cr) | {schedule_str} | Seats: {info.get('seats')} ({status})")
        
    return "\n".join(results) if results else "No courses found."

def view_student_schedule_fn(student_id: str) -> str:
    """View registered courses and meeting times for the student."""
    db = load_database()
    student = db.get("students", {}).get(student_id)
    if not student:
        return "Student record not found."
    enrolled = student.get("enrolled_courses", [])
    lines = []
    for c in enrolled:
        if c in db.get("courses", {}):
            c_info = db["courses"][c]
            schedule_str = format_schedule_string(c_info)
            lines.append(f"• {c}: {c_info.get('title')} - {schedule_str}")
    return f"Schedule for {student.get('name')}:\n" + ("\n".join(lines) if lines else "No active enrollments.")

def register_for_course_fn(student_id: str, course_code: str) -> str:
    """Register the student for a course code."""
    code = course_code.upper().strip()
    db = load_database()
    student = db.get("students", {}).get(student_id)
    if not student:
        return "Student authentication failed."
    course = db.get("courses", {}).get(code)
    if not course:
        return f"Course {code} does not exist."
    if course.get("seats", 0) <= 0:
        return f"{code} is currently full."
    if code in student.get("enrolled_courses", []):
        return f"Already enrolled in {code}."

    course["seats"] -= 1
    student["enrolled_courses"].append(code)
    save_database(db)
    return f"Successfully enrolled in {code} ({course.get('title')})."

def unregister_course_fn(student_id: str, course_code: str) -> str:
    """Drop/unregister a course for the student."""
    code = course_code.upper().strip()
    db = load_database()
    student = db.get("students", {}).get(student_id)
    if not student:
        return "Student authentication failed."
    if code not in student.get("enrolled_courses", []):
        return f"You are not currently enrolled in {code}."

    course = db.get("courses", {}).get(code)
    student["enrolled_courses"].remove(code)
    if course:
        course["seats"] += 1
        
    save_database(db)
    return f"Successfully unregistered from {code}. Your seat has been freed."

# Explicit StructuredTool instances guarantee valid names and metadata for Harmony
tools = [
    StructuredTool.from_function(
        func=view_student_schedule_fn,
        name="view_student_schedule",
        description="View the current registered class schedule for a student."
    ),
    StructuredTool.from_function(
        func=register_for_course_fn,
        name="register_for_course",
        description="Enroll the student into a specific course using its course code."
    ),
    StructuredTool.from_function(
        func=unregister_course_fn,
        name="unregister_course",
        description="Drop or unregister a student from a course using its course code."
    ),
    StructuredTool.from_function(
        func=get_course_catalog_fn,
        name="get_course_catalog",
        description="Retrieve courses, schedules, and seat availability. Can filter by course_code (e.g. CS101) or department (e.g. CS)."
    ),
]

tools_by_name = {t.name: t for t in tools}

if llm_primary:
    # Bind tools to every single model individually
    primary_with_tools = llm_primary.bind_tools(tools, tool_choice="auto")
    b1_with_tools = llm_backup_1.bind_tools(tools, tool_choice="auto")
    b2_with_tools = llm_backup_2.bind_tools(tools, tool_choice="auto")
    b3_with_tools = llm_backup_3.bind_tools(tools, tool_choice="auto")

    # Chain them all together in order of execution for the main chat agent
    llm_with_tools = primary_with_tools.with_fallbacks([
        b1_with_tools, 
        b2_with_tools, 
        b3_with_tools
    ])
else:
    llm_with_tools = None


from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not llm_with_tools:
        return {"reply": "Chat service unavailable."}
    
    sid = request.student_id
    db = load_database()
    student_profile = db.get("students", {}).get(sid, {})
    student_name = student_profile.get("name", "Student")
    student_major = student_profile.get("field", "Undecided")

    # 1. Initialize system prompt if new session
    if sid not in CHAT_HISTORY:
        system_prompt = f"""You are a strict, helpful AI Registration Assistant and academic advisor for {student_name} (Student ID: {sid}).
        STUDENT PROFILE:
        - Major / Degree Program: {student_major}
        
        CRITICAL RULES:
        1. Be helpful, respectful, kind, and professional.
        2. HANDLING SHORT OR VAGUE INPUTS: If the user replies with short fillers, agreements, or single words like "OK", "Sure", "Hi", or "Thanks", do NOT dump a long, unprompted essay, course list, or opinion. Keep your response short, conversational, and ask a single clarifying question.
        3. Use your tools to check the course catalog, view schedules, and register or unregister the student from classes.
        4. NEVER invent, guess, or simulate any information outside of these tools.
        5. Ask as an expert mentor and guide for every subject listed in the course catalog.
        6. You MUST wrap ALL mathematical variables, formulas, and equations in standard LaTeX delimiters ($ for inline, $$ for block).
        7. Detect the language the user is speaking and reply in that EXACT same language.
        8. If asked for administrative data outside your tools, reply EXACTLY with: "I do not have access to that irrelevent information in the registration database."
        9. Use appropriate spaces if mathematically or grammatically incorrect.
        CRITICAL ANTI-HALLUCINATION RULES:
        1. ONLY recommend, suggest, or mention course codes and course titles that exist in the official registration catalog tool output.
        2. NEVER make up, guess, or synthesize course numbers (e.g., NEVER say "CS 210" or "CS 201"). 
        3. If the user asks for an elective, advice, or suggestions, you MUST call the `get_course_catalog` tool FIRST before answering.
        4. If a subject or department has no available courses in the tool output, state clearly that no such courses are offered.
        5. If the user asks for anything not in the catalog tool, reply EXACTLY: "I do not have access to that irrelevent information in the registration database."
        Keep answers concise and short."""
        
        CHAT_HISTORY[sid] = [SystemMessage(content=system_prompt)]

    # 2. Append current user message
    CHAT_HISTORY[sid].append(HumanMessage(content=request.message))

    # Sliding context window: keep system prompt + last 6 conversational turns
    if len(CHAT_HISTORY[sid]) > 7:
        CHAT_HISTORY[sid] = [CHAT_HISTORY[sid][0]] + CHAT_HISTORY[sid][-6:]

    try:
        # 3. Invoke LLM with conversational history
        ai_msg = await llm_with_tools.ainvoke(CHAT_HISTORY[sid])

        # 4. If tools were called, execute them and let the LLM generate the final answer
        if ai_msg.tool_calls:
            tool_outputs = []
            for call in ai_msg.tool_calls:
                t_name = call.get("name")
                if not t_name or t_name not in tools_by_name:
                    continue
                t_args = dict(call.get("args") or {})
                if "student_id" in tools_by_name[t_name].args:
                    t_args["student_id"] = sid
                res = tools_by_name[t_name].invoke(t_args)
                tool_outputs.append(f"Result from {t_name}: {res}")

            # Second pass: feed tool output back to the model for an exact answer
            synthesis_prompt = (
                f"User asked: '{request.message}'\n"
                f"Data retrieved:\n" + "\n".join(tool_outputs) + "\n\n"
                f"Answer the user's question directly, accurately, and concisely based ONLY on this data."
            )
            final_res = await llm.ainvoke(CHAT_HISTORY[sid] + [HumanMessage(content=synthesis_prompt)])
            reply = final_res.content
        else:
            reply = ai_msg.content or "How can I assist you with your courses?"

        # 5. Store clean text in conversation history
        CHAT_HISTORY[sid].append(AIMessage(content=reply))

    except Exception as e:
        CHAT_HISTORY.pop(sid, None)
        return {"reply": f"⚠️ **System Alert:** AI connection failed. Reason: {str(e)}"}

    # 6. Sentiment Analysis & Logging
    sentiment_label = "N/A (TextBlob missing)"
    if TextBlob:
        polarity = TextBlob(request.message).sentiment.polarity
        if polarity > 0.1:
            sentiment_label = "Positive 🟢"
        elif polarity < -0.1:
            sentiment_label = "Negative 🔴"
        else:
            sentiment_label = "Neutral ⚪"

    # CRITICAL FIX: Re-load the db here to avoid overwriting changes made by tools!
    fresh_db = load_database() 

    if "chat_logs" not in fresh_db:
        fresh_db["chat_logs"] = []
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    fresh_db["chat_logs"].append({
        "timestamp": timestamp,
        "student_id": sid,
        "message": request.message,
        "reply": reply,
        "sentiment": sentiment_label
    })
    
    # Save the fresh database containing both the tool updates and the new chat log
    save_database(fresh_db)

    return {"reply": reply}

# ============================================================
# USER INTERFACE
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Ai Registration Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    
    <!-- Markdown Parser -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    
    <!-- MathJax for LaTeX Rendering -->
    <script>
      window.MathJax = {
        tex: { inlineMath: [['\\\\(', '\\\\)'], ['$', '$']], displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']] }
      };
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

    <!-- Multi-language Support via Google Translate Widget -->
    <script type="text/javascript">
        function googleTranslateElementInit() {
            new google.translate.TranslateElement({
                pageLanguage: 'en'
            }, 'google_translate_element');
        }
    </script>
    <script type="text/javascript" src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>

    <style>
        #chat-box { scroll-behavior: smooth; }
        body {
            font-size: 16px; 
        }
        /* Hide the annoying Google Translate top banner pushing the page down */
        .goog-te-banner-frame.skiptranslate { display: none !important; }
        body { top: 0px !important; }
        
        /* Style the native select box */
        #google_translate_element select {
            padding: 8px;
            border-radius: 8px;
            border: 1px solid #cbd5e1;
            background-color: white;
            font-size: 12px;
            color: #1e293b;
            font-weight: 500;
            cursor: pointer;
            outline: none;
        }
    </style>
</head>
<body class="bg-slate-100 min-h-screen flex items-center justify-center p-4">

<!-- Google Translate Widget Container -->
<div id="google_translate_element" class="fixed top-4 right-4 z-[200]"></div>

<!-- Reload Notification Overlay -->
<div id="reload-notification" class="hidden fixed inset-0 bg-slate-900/80 z-[100] flex flex-col items-center justify-center backdrop-blur-md transition-opacity duration-300">
    <div class="bg-white rounded-3xl p-8 max-w-sm w-full text-center shadow-2xl border-t-4 border-amber-500 animate-pulse">
        <div class="w-16 h-16 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-4 text-3xl font-bold">!</div>
        <h3 class="text-xl font-bold text-slate-800 mb-2">Session Reloaded</h3>
        <p class="text-sm text-slate-600">Please Wait!!!, a browser refresh was detected. For your security, your session has been temporarily disconnected.</p>
    </div>
</div>

<!-- Export Loading Animation Popup -->
<div id="export-loader" class="hidden fixed inset-0 bg-slate-900/60 z-[300] flex flex-col items-center justify-center backdrop-blur-sm transition-all duration-300">
    <div class="bg-white rounded-2xl p-6 max-w-xs w-full text-center shadow-2xl flex flex-col items-center space-y-4">
        <div class="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
        <div>
            <h3 class="text-base font-bold text-slate-800" id="export-loader-title">Preparing Export</h3>
            <p class="text-xs text-slate-500 mt-1">Please wait while your file is generated...</p>
        </div>
    </div>
</div>

<div class="max-w-[1300px] w-full bg-white rounded-3xl shadow-xl overflow-hidden border border-slate-200 relative mt-10 text-lg">
    
    <!-- Edit Course Modal Overlay -->
    <div id="modal-edit-course" class="hidden absolute inset-0 bg-black/60 z-50 flex items-center justify-center p-4 rounded-3xl backdrop-blur-sm">
        <div class="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h3 class="text-lg font-bold text-slate-800 mb-4" id="edit-course-header">Edit Course</h3>
            <input type="hidden" id="edit-course-code">
            <div class="space-y-3">
                <div><label class="text-xs font-bold text-slate-500">Course Title</label><input type="text" id="edit-course-title" class="w-full border p-2.5 rounded-xl text-sm mt-1"></div>
                <div><label class="text-xs font-bold text-slate-500">Department</label><input type="text" id="edit-course-dept" class="w-full border p-2.5 rounded-xl text-sm mt-1"></div>
                
                <div class="grid grid-cols-3 gap-2">
                    <div><label class="text-xs font-bold text-slate-500">Days</label><input type="text" id="edit-course-days" placeholder="Mon/Wed" class="w-full border p-2.5 rounded-xl text-sm mt-1"></div>
                    <div><label class="text-xs font-bold text-slate-500">Start Time</label><input type="text" id="edit-course-start" placeholder="10:00 AM" class="w-full border p-2.5 rounded-xl text-sm mt-1"></div>
                    <div><label class="text-xs font-bold text-slate-500">End Time (Opt)</label><input type="text" id="edit-course-end" placeholder="11:30 AM" class="w-full border p-2.5 rounded-xl text-sm mt-1"></div>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div><label class="text-xs font-bold text-slate-500">Credits</label><input type="number" id="edit-course-credits" class="w-full border p-2.5 rounded-xl text-sm mt-1"></div>
                    <div><label class="text-xs font-bold text-slate-500">Seats</label><input type="number" id="edit-course-seats" class="w-full border p-2.5 rounded-xl text-sm mt-1"></div>
                </div>
            </div>
            <div class="flex gap-2 mt-6">
                <button onclick="closeEditModal()" class="w-1/2 bg-slate-200 text-slate-700 hover:bg-slate-300 p-2.5 rounded-xl text-sm font-semibold transition">Cancel</button>
                <button onclick="saveCourseEdit()" class="w-1/2 bg-indigo-600 text-white hover:bg-indigo-700 p-2.5 rounded-xl text-sm font-semibold transition">Save Changes</button>
            </div>
        </div>
    </div>

    <div class="bg-indigo-600 p-6 text-white text-center">
        <h1 class="text-2xl font-bold">🎓 AI Registration Assistant</h1>
        <p class="text-sm text-indigo-100 mt-1">Data Alcott Systems || Build by AD</p>
    </div>

    <!-- Role Selection -->
    <div id="view-role-select" class="p-8 space-y-4 max-w-2xl mx-auto">
        <button onclick="showAdminLogin()" class="w-full bg-slate-900 hover:bg-black text-white p-4 rounded-2xl font-semibold flex items-center justify-between">
            <span>🛡️ Control Portal (Admin/Server Handler)</span>
            <span>&rarr;</span>
        </button>
        <button onclick="showStudentOptions()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-4 rounded-2xl font-semibold flex items-center justify-between">
            <span>🎒 Student Portal</span>
            <span>&rarr;</span>
        </button>
    </div>

    <!-- Admin Login -->
    <div id="view-admin-login" class="hidden p-8 space-y-4 max-w-2xl mx-auto">
        <h2 class="text-xl font-bold text-slate-800">Admin Authentication</h2>
        <input type="text" id="admin-user" placeholder="Username (admin)" class="w-full border p-3 rounded-xl text-sm" />
        <input type="password" id="admin-pass" placeholder="Password (StrongAdminPassword123!)" class="w-full border p-3 rounded-xl text-sm" />
        <div class="flex gap-2">
            <button onclick="backToRole()" class="w-1/3 bg-slate-200 p-3 rounded-xl text-sm font-medium">Back</button>
            <button onclick="handleAdminLogin()" class="w-2/3 bg-indigo-600 text-white p-3 rounded-xl text-sm font-semibold">Login</button>
        </div>
    </div>

    <!-- Admin Dashboard -->
    <div id="view-admin-dashboard" class="hidden p-6">
        <div class="flex justify-between items-start border-b pb-4 mb-4">
            <div>
                <h2 class="text-xl font-bold text-slate-800">Administrator Console</h2>
                <div class="flex gap-4 mt-2">
                    <button onclick="switchAdminTab('records')" id="tab-records" class="text-sm font-bold text-indigo-600 pb-1 border-b-2 border-indigo-600 transition">Student Records</button>
                    <button onclick="switchAdminTab('courses')" id="tab-courses" class="text-sm font-semibold text-slate-500 pb-1 border-b-2 border-transparent transition">Course Catalog</button>
                    <button onclick="switchAdminTab('analytics')" id="tab-analytics" class="text-sm font-semibold text-slate-500 pb-1 border-b-2 border-transparent transition">Analytics Dashboard</button>
                    <button onclick="switchAdminTab('chatlogs')" id="tab-chatlogs" class="text-sm font-semibold text-slate-500 pb-1 border-b-2 border-transparent transition">Chat Logs</button>
                </div>
            </div>
            <div class="flex flex-col items-end gap-2">
                <button onclick="logoutAdmin()" class="bg-slate-200 text-slate-700 hover:bg-slate-300 text-xs px-4 py-2 rounded-lg font-semibold transition w-full">Logout</button>
                <button onclick="hardResetSystem()" class="bg-red-600 text-white hover:bg-red-700 text-xs px-4 py-2 rounded-lg font-semibold transition shadow-sm w-full">Factory Reset</button>
            </div>
        </div>
        
        <!-- Tab: Student Records -->
        <div id="admin-section-records" class="space-y-4">
            <div class="flex justify-end gap-2">
                <button onclick="exportStudentsCSV()" class="bg-green-50 text-green-600 hover:bg-green-100 text-xs px-3 py-1.5 rounded-lg border border-green-200 font-semibold transition flex items-center gap-1">📊 Export CSV</button>
                <button onclick="clearAllStudents()" class="bg-red-50 text-red-600 hover:bg-red-100 text-xs px-3 py-1.5 rounded-lg border border-red-200 font-semibold transition">Clear All Students</button>
            </div>
            <div class="border rounded-xl overflow-hidden max-h-72 overflow-y-auto">
                <table class="w-full text-xs text-left text-slate-600">
                    <thead class="bg-slate-100 text-slate-700 uppercase sticky top-0">
                        <tr><th class="p-3">ID</th><th class="p-3">Name</th><th class="p-3">Email</th><th class="p-3">Phone</th><th class="p-3">Field</th><th class="p-3 text-center">Action</th></tr>
                    </thead>
                    <tbody id="admin-students-tbody"></tbody>
                </table>
            </div>
        </div>

        <!-- Tab: Chat Logs -->
        <div id="admin-section-chatlogs" class="hidden space-y-4">
            <div class="flex justify-end">
                <button onclick="exportChatLogsPDF()" class="bg-red-50 text-red-600 hover:bg-red-100 text-xs px-3 py-1.5 rounded-lg border border-red-200 font-semibold transition flex items-center gap-1">📄 Export PDF</button>
            </div>
            <div id="chatlogs-export-area" class="border rounded-xl overflow-hidden max-h-72 overflow-y-auto bg-white">
                <table class="w-full text-xs text-left text-slate-600">
                    <thead class="bg-slate-100 text-slate-700 uppercase sticky top-0">
                        <tr><th class="p-3">Timestamp</th><th class="p-3">Student ID</th><th class="p-3 w-1/4">Message</th><th class="p-3">Sentiment</th><th class="p-3 w-1/3">AI Reply</th></tr>
                    </thead>
                    <tbody id="admin-chatlogs-tbody"></tbody>
                </table>
            </div>
        </div>

        <!-- Tab: Course Catalog (Master Control) -->
        <div id="admin-section-courses" class="hidden space-y-4">
            <div class="bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-wrap gap-2 items-start">
                <div class="w-20">
                    <label class="text-[10px] font-bold text-slate-500">CODE</label>
                    <input type="text" id="new-course-code" placeholder="CS101" class="w-full border p-2 rounded-lg text-xs" oninput="validateCourseFieldLive(this, 'code')">
                    <span id="err-new-course-code" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">2-4 letters + 2-4 digits</span>
                </div>
                <div class="flex-1 min-w-[140px]">
                    <label class="text-[10px] font-bold text-slate-500">TITLE</label>
                    <input type="text" id="new-course-title" placeholder="Course Title" class="w-full border p-2 rounded-lg text-xs" oninput="validateCourseFieldLive(this, 'title')">
                    <span id="err-new-course-title" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">Must contain letters</span>
                </div>
                <div class="w-16">
                    <label class="text-[10px] font-bold text-slate-500">DEPT</label>
                    <input type="text" id="new-course-dept" placeholder="CS" class="w-full border p-2 rounded-lg text-xs" oninput="validateCourseFieldLive(this, 'dept')">
                    <span id="err-new-course-dept" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">Letters only</span>
                </div>
                <div class="w-24">
                    <label class="text-[10px] font-bold text-slate-500">DAYS</label>
                    <input type="text" id="new-course-days" placeholder="Mon/Wed" class="w-full border p-2 rounded-lg text-xs" oninput="validateCourseFieldLive(this, 'days')">
                    <span id="err-new-course-days" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">e.g. Mon/Wed</span>
                </div>
                <div class="w-24">
                    <label class="text-[10px] font-bold text-slate-500">START</label>
                    <input type="text" id="new-course-start" placeholder="10:00 AM" class="w-full border p-2 rounded-lg text-xs" oninput="validateCourseFieldLive(this, 'time')">
                    <span id="err-new-course-start" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">HH:MM AM/PM</span>
                </div>
                <div class="w-24">
                    <label class="text-[10px] font-bold text-slate-500">END (Opt)</label>
                    <input type="text" id="new-course-end" placeholder="11:30 AM" class="w-full border p-2 rounded-lg text-xs" oninput="validateCourseFieldLive(this, 'timeOpt')">
                    <span id="err-new-course-end" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">HH:MM AM/PM</span>
                </div>
                <div class="w-16">
                    <label class="text-[10px] font-bold text-slate-500">CRDTS</label>
                    <input type="number" id="new-course-credits" class="w-full border p-2 rounded-lg text-xs" value="3" oninput="validateCourseFieldLive(this, 'credits')">
                    <span id="err-new-course-credits" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">1 to 10</span>
                </div>
                <div class="w-16">
                    <label class="text-[10px] font-bold text-slate-500">SEATS</label>
                    <input type="number" id="new-course-seats" class="w-full border p-2 rounded-lg text-xs" value="30" oninput="validateCourseFieldLive(this, 'seats')">
                    <span id="err-new-course-seats" class="text-[9px] text-red-500 hidden leading-tight block mt-0.5">&ge; 0</span>
                </div>
                <button onclick="addCourse()" class="bg-indigo-600 text-white hover:bg-indigo-700 px-4 py-2 rounded-lg text-xs font-bold h-[34px] mt-4 transition">Add</button>
            </div>
            
            <div class="flex justify-between items-center">
                <span class="text-xs text-slate-500 font-bold text-red-500">⚠️ MUST CLICK "RESTORE" TO APPLY NEW TIME FORMAT TO OLD DB!</span>
                <button onclick="resetCatalog()" class="text-indigo-600 hover:underline text-xs font-semibold">Restore Default 15 Courses</button>
            </div>
            
            <div class="border rounded-xl overflow-hidden max-h-60 overflow-y-auto">
                <table class="w-full text-xs text-left text-slate-600">
                    <thead class="bg-slate-100 text-slate-700 uppercase sticky top-0">
                        <tr><th class="p-3">Code</th><th class="p-3">Title</th><th class="p-3">Dept</th><th class="p-3 min-w-[150px]">Schedule</th><th class="p-3">Credits</th><th class="p-3">Seats</th><th class="p-3 text-center">Actions</th></tr>
                    </thead>
                    <tbody id="admin-courses-tbody"></tbody>
                </table>
            </div>
        </div>

        <!-- Tab: Analytics -->
        <div id="admin-section-analytics" class="hidden space-y-6">
            <div class="flex justify-end">
                <button onclick="exportAnalyticsPDF()" class="bg-red-50 text-red-600 hover:bg-red-100 text-xs px-3 py-1.5 rounded-lg border border-red-200 font-semibold transition flex items-center gap-1">📄 Export PDF</button>
            </div>
            <div id="analytics-export-area" class="space-y-6 bg-white p-4 rounded-xl border border-transparent">
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-indigo-50 p-4 rounded-xl border border-indigo-100">
                        <p class="text-xs text-indigo-600 font-bold uppercase tracking-wider mb-1">Registered Students</p>
                        <p class="text-3xl font-black text-indigo-900" id="stat-students">0</p>
                    </div>
                    <div class="bg-green-50 p-4 rounded-xl border border-green-100">
                        <p class="text-xs text-green-600 font-bold uppercase tracking-wider mb-1">Total Registrations</p>
                        <p class="text-3xl font-black text-green-900" id="stat-regs">0</p>
                    </div>
                    <div class="bg-amber-50 p-4 rounded-xl border border-amber-100">
                        <p class="text-xs text-amber-600 font-bold uppercase tracking-wider mb-1">Total Student Logins</p>
                        <p class="text-3xl font-black text-amber-900" id="stat-logins">0</p>
                    </div>
                </div>
                <div class="border rounded-xl p-4 bg-white shadow-sm">
                    <h3 class="text-sm font-bold text-slate-700 mb-4">Student Distribution by Field of Study</h3>
                    <canvas id="analyticsChart" height="100"></canvas>
                </div>
            </div>
        </div>
    </div>

    <!-- Student Options -->
    <div id="view-student-options" class="hidden p-8 space-y-4 max-w-2xl mx-auto">
        <h2 class="text-xl font-bold text-slate-800">Student Access</h2>
        <button onclick="showStudentRegister()" class="w-full bg-indigo-600 text-white p-3.5 rounded-xl font-semibold text-sm">Create New Account</button>
        <button onclick="showStudentLogin()" class="w-full border border-indigo-600 text-indigo-600 p-3.5 rounded-xl font-semibold text-sm">Log In</button>
        <button onclick="backToRole()" class="w-full text-slate-400 text-sm">Back</button>
    </div>

    <!-- Student Login -->
    <div id="view-student-login" class="hidden p-8 space-y-4 max-w-2xl mx-auto">
        <h2 class="text-xl font-bold text-slate-800">Student Sign In</h2>
        <input type="email" id="student-login-email" placeholder="Registered Email" class="w-full border p-3 rounded-xl text-sm" />
        <input type="password" id="student-login-pass" placeholder="Account Password" class="w-full border p-3 rounded-xl text-sm" />
        
        <div class="text-right">
            <button type="button" onclick="showForgotPassword()" class="text-xs font-semibold text-indigo-600 hover:underline">Forgot Password?</button>
        </div>
        
        <div class="flex gap-2">
            <button onclick="showStudentOptions()" class="w-1/3 bg-slate-200 p-3 rounded-xl text-sm">Back</button>
            <button onclick="handleStudentLogin()" class="w-2/3 bg-indigo-600 text-white p-3 rounded-xl font-semibold text-sm">Sign In</button>
        </div>
    </div>
    
    <!-- Forgot Password View -->
    <div id="view-forgot-password" class="hidden p-8 space-y-4 max-w-2xl mx-auto">
        <h2 class="text-xl font-bold text-slate-800">Recover Password</h2>
        <p class="text-xs text-slate-500 mb-4">Enter your email to receive a secure temporary password.</p>
        
        <div class="flex gap-2">
            <input type="email" id="forgot-email" placeholder="Registered Email Address" class="w-full border p-3 rounded-xl text-sm" />
            <button type="button" id="btn-send-pass" onclick="handleForgotPasswordSend()" class="bg-slate-800 text-white px-4 text-xs rounded-xl whitespace-nowrap font-medium transition">Get Password</button>
        </div>
        
        <input type="password" id="forgot-temp-pass" placeholder="Enter Emailed Password Here" class="w-full border p-3 rounded-xl text-sm mt-4" />
        
        <div class="flex gap-2 pt-4">
            <button onclick="showStudentLogin()" class="w-1/3 bg-slate-200 p-3 rounded-xl text-sm">Cancel</button>
            <button onclick="handleForgotPasswordLogin()" class="w-2/3 bg-indigo-600 text-white p-3 rounded-xl font-semibold text-sm">Login with New Password</button>
        </div>
    </div>

    <!-- Student Registration Fields with Live Bounding -->
    <div id="view-student-register" class="hidden p-8 space-y-4 max-w-2xl mx-auto">
        <h2 class="text-xl font-bold text-slate-800">Create Account</h2>
        
        <!-- Name -->
        <div>
            <input type="text" id="reg-name" placeholder="Full Name (Letters and spaces only)" class="w-full border p-3 rounded-xl text-sm transition" oninput="validateFieldLive(this, 'name')" />
            <p id="err-reg-name" class="text-xs text-red-500 mt-1 hidden">⚠️ Letters and spaces only.</p>
        </div>
        
        <!-- Phone Feature -->
        <div>
            <div class="flex gap-2">
                <div class="flex-1">
                    <input type="text" id="reg-phone" placeholder="Phone Number (e.g. +919876543210)" maxlength="13" class="w-full border p-3 rounded-xl text-sm transition" oninput="validateFieldLive(this, 'phone'); handlePhoneChange(this);" />
                    <p id="err-reg-phone" class="text-xs text-red-500 mt-1 hidden">⚠️ Valid Indian +91 number required (no dummies).</p>
                </div>
                <button type="button" id="btn-verify-phone" onclick="verifyPhoneAnimation()" class="bg-slate-800 text-white px-3 text-xs rounded-xl whitespace-nowrap font-medium h-[45px] transition">Verify Phone</button>
            </div>
            
            <!-- Phone Verification Animation Container -->
            <div id="phone-verify-container" class="hidden mt-3 p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-3 transition-all duration-300">
                <div class="flex items-center gap-3">
                    <div class="w-4 h-4 flex items-center justify-center">
                        <span id="pv-spin-1" class="w-3 h-3 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin hidden"></span>
                        <span id="pv-icon-1" class="hidden text-green-600 text-sm">✅</span>
                    </div>
                    <span class="text-slate-500 font-bold uppercase tracking-wide w-28">Country Code:</span>
                    <span id="pv-val-1" class="text-slate-800 font-bold text-sm">Pending...</span>
                </div>
                <div class="flex items-center gap-3">
                    <div class="w-4 h-4 flex items-center justify-center">
                        <span id="pv-spin-2" class="w-3 h-3 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin hidden"></span>
                        <span id="pv-icon-2" class="hidden text-green-600 text-sm">✅</span>
                    </div>
                    <span class="text-slate-500 font-bold uppercase tracking-wide w-28">Server:</span>
                    <span id="pv-val-2" class="text-slate-800 font-bold text-sm">Pending...</span>
                </div>
                <div class="flex items-center gap-3">
                    <div class="w-4 h-4 flex items-center justify-center">
                        <span id="pv-spin-3" class="w-3 h-3 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin hidden"></span>
                        <span id="pv-icon-3" class="hidden text-green-600 text-sm">✅</span>
                    </div>
                    <span class="text-slate-500 font-bold uppercase tracking-wide w-28">Relay:</span>
                    <span id="pv-val-3" class="text-slate-800 font-bold text-sm">Pending...</span>
                </div>
            </div>
        </div>

        <!-- Restored Email Feature -->
        <div class="space-y-2 border-t mt-4 pt-4">
            <div class="flex gap-2">
                <div class="w-full">
                    <input type="email" id="reg-email" placeholder="Your Email Address" class="w-full border p-3 rounded-xl text-sm transition" oninput="validateFieldLive(this, 'email')" />
                    <p id="err-reg-email" class="text-xs text-red-500 mt-1 hidden">⚠️ Valid email required.</p>
                </div>
                <button type="button" id="btn-send" onclick="sendOtp()" class="bg-slate-800 text-white px-3 text-xs rounded-xl whitespace-nowrap font-medium h-[45px]">Send Code</button>
            </div>
            <div class="flex gap-2">
                <div class="w-full">
                    <input type="text" id="otp-email-val" placeholder="6-Digit Code" class="w-full border p-2.5 rounded-xl text-sm transition" oninput="validateFieldLive(this, 'otp')" maxlength="6" />
                    <p id="err-otp-email-val" class="text-xs text-red-500 mt-1 hidden">⚠️ Must be exactly 6 digits.</p>
                </div>
                <button type="button" onclick="verifyOtp()" class="bg-indigo-600 text-white px-3 text-xs rounded-xl whitespace-nowrap font-medium h-[42px]">Verify</button>
            </div>
            <p id="email-status" class="text-xs text-slate-400">Status: Unverified</p>
        </div>

        <!-- Password -->
        <div>
            <input type="password" id="reg-pass" placeholder="Create Password (min. 8 characters, suggest a strong combination for password)" class="w-full border p-3 rounded-xl text-sm transition" oninput="validateFieldLive(this, 'password')" />
            <p id="err-reg-pass" class="text-xs text-red-500 mt-1 hidden">⚠️ Minimum 8 characters required.</p>
        </div>
    
        <!-- Course -->
        <input type="text" id="reg-course" placeholder="Subject / Degree Program (eg. Computer Science, Science, Biology)" class="w-full border p-3 rounded-xl text-sm" />

        <div class="flex gap-2 pt-4">
            <button onclick="showStudentOptions()" class="w-1/3 bg-slate-200 p-3 rounded-xl text-sm">Back</button>
            <button onclick="handleStudentRegister()" class="w-2/3 bg-indigo-600 text-white p-3 rounded-xl font-semibold text-sm">Chat</button>
        </div>
    </div>

    <!-- Chat Console (With Suggestive Chat UI) -->
    <div id="view-chat" class="hidden flex flex-col h-[560px]">
        <div class="p-4 bg-indigo-50 border-b flex justify-between items-center text-xs">
            <span id="chat-user-banner" class="font-medium text-indigo-900"></span>
            <button onclick="backToRole()" class="text-red-500 font-bold hover:underline">Sign Out</button>
        </div>
        
        <div id="chat-box" class="flex-1 overflow-y-auto p-5 space-y-4 text-sm bg-slate-50"></div>
        
        <form id="chat-form" class="p-3 border-t flex gap-2 bg-white rounded-b-3xl">
            <input type="text" id="chat-input" placeholder="Type a message or select a suggestion above..." class="flex-1 border p-3 rounded-xl text-sm focus:outline-none focus:border-indigo-400 transition" required />
            <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 rounded-xl text-sm font-semibold transition shadow-sm">Send</button>
        </form>
    </div>
</div>

<script>
let adminToken = null;
let currentStudentId = null;
let emailPoller = null;
let chartInstance = null;
let lastVerifiedPhone = null;

function resetPhoneVerificationUI() {
    const phoneContainer = document.getElementById('phone-verify-container');
    if (phoneContainer) phoneContainer.classList.add('hidden');
    
    const phoneBtn = document.getElementById('btn-verify-phone');
    if (phoneBtn) {
        phoneBtn.disabled = false;
        phoneBtn.innerText = 'Verify Phone';
        phoneBtn.className = 'bg-slate-800 text-white px-3 text-xs rounded-xl whitespace-nowrap font-medium h-[45px] transition';
    }
    
    for(let i=1; i<=3; i++) {
        const spin = document.getElementById(`pv-spin-${i}`);
        const icon = document.getElementById(`pv-icon-${i}`);
        const val = document.getElementById(`pv-val-${i}`);
        if(spin) spin.classList.add('hidden');
        if(icon) icon.classList.add('hidden');
        if(val) val.innerText = 'Pending...';
    }
    
    lastVerifiedPhone = null;
}

function handlePhoneChange(inputElement) {
    const currentValue = inputElement.value.trim();
    if (lastVerifiedPhone !== null && currentValue !== lastVerifiedPhone) {
        resetPhoneVerificationUI();
    }
}

function validateFieldLive(inputElement, type) {
    const val = inputElement.value;
    const errorSpan = document.getElementById('err-' + inputElement.id);
    let isValid = true;

    switch (type) {
        case 'name':
            isValid = /^[A-Za-z\\s]*$/.test(val);
            break;
        case 'phone':
            const phoneRegex = /^\\+91[6-9]\\d{9}$/;
            if (!phoneRegex.test(val)) {
                isValid = false;
            } else {
                const localNum = val.substring(3);
                // Reject repeated digits (e.g. 9999999999) or sequential numbers
                const isRepeated = /^(\\d)\\1{9}$/.test(localNum);
                const isSequential = localNum === "9876543210" || localNum === "6789012345";
                if (isRepeated || isSequential) {
                    isValid = false;
                }
            }
            break;
        case 'email':
            isValid = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]*$/.test(val) || val === "";
            break;
        case 'otp':
            isValid = /^\\d{0,6}$/.test(val);
            break;
        case 'password':
            isValid = val.length >= 8 || val === "";
            break;
        case 'courseCode':
            isValid = /^[A-Za-z]{0,4}\\d{0,4}$/.test(val);
            break;
    }

    if (!isValid && val !== "") {
        inputElement.classList.add('border-red-500', 'bg-red-50');
        inputElement.classList.remove('border-slate-300');
        if (errorSpan) errorSpan.classList.remove('hidden');
    } else {
        inputElement.classList.remove('border-red-500', 'bg-red-50');
        inputElement.classList.add('border-slate-300');
        if (errorSpan) errorSpan.classList.add('hidden');
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const navEntries = performance.getEntriesByType("navigation");
    if (navEntries.length > 0 && navEntries[0].type === "reload") {
        const reloadPopup = document.getElementById('reload-notification');
        reloadPopup.classList.remove('hidden');
        setTimeout(() => {
            reloadPopup.classList.add('hidden');
        }, 5000);
    }
});

function hideAllViews() {
    ['role-select', 'admin-login', 'admin-dashboard', 'student-options', 'student-login', 'student-register', 'forgot-password', 'chat']
        .forEach(id => document.getElementById('view-' + id).classList.add('hidden'));
}

function clearFormInputs() {
    document.querySelectorAll('input').forEach(input => {
        if (input.type !== 'hidden' && input.type !== 'submit' && input.type !== 'button') {
            input.value = '';
            input.classList.remove('border-red-500', 'bg-red-50');
            input.classList.add('border-slate-300');
        }
    });
    document.querySelectorAll('[id^="err-"], #name-error').forEach(el => {
        el.classList.add('hidden');
    });
    const emailStatus = document.getElementById('email-status');
    if (emailStatus) {
        emailStatus.innerText = 'Status: Unverified';
        emailStatus.className = 'text-xs text-slate-400';
    }
    resetPhoneVerificationUI();
}

function backToRole() { 
    hideAllViews(); 
    if (emailPoller) clearInterval(emailPoller);
    clearFormInputs();
    document.getElementById('view-role-select').classList.remove('hidden'); 
}

function showStudentLogin() { 
    hideAllViews(); 
    clearFormInputs();
    document.getElementById('view-student-login').classList.remove('hidden'); 
}

function showStudentRegister() { 
    hideAllViews(); 
    clearFormInputs();
    document.getElementById('view-student-register').classList.remove('hidden'); 
}
function showAdminLogin() { hideAllViews(); document.getElementById('view-admin-login').classList.remove('hidden'); }
function showStudentOptions() { hideAllViews(); document.getElementById('view-student-options').classList.remove('hidden'); }
function showForgotPassword() { hideAllViews(); document.getElementById('view-forgot-password').classList.remove('hidden'); }

async function handleAdminLogin() {
    const u = document.getElementById('admin-user').value;
    const p = document.getElementById('admin-pass').value;
    const res = await fetch('/api/auth/admin-login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: u, password: p})
    });
    const d = await res.json();
    if (!res.ok) return alert(d.detail || 'Access Denied');
    adminToken = d.token;
    hideAllViews();
    document.getElementById('view-admin-dashboard').classList.remove('hidden');
    switchAdminTab('records');
}

function logoutAdmin() {
    adminToken = null;
    backToRole();
}

async function hardResetSystem() {
    if (!confirm('WARNING: This will erase ALL students, courses, analytics, and chat logs. The system will be restored to its initial factory state. Are you sure?')) return;
    const res = await fetch('/api/admin/hard-reset', {
        method: 'POST',
        headers: {'Authorization': 'Bearer ' + adminToken}
    });
    if (res.ok) {
        alert('System successfully reset.');
        logoutAdmin(); 
    } else {
        alert('Reset failed.');
    }
}

function validateCourseFieldLive(el, type) {
    const val = el.value.trim();
    const errSpan = document.getElementById('err-' + el.id);
    let valid = true;

    if (val !== "") {
        switch (type) {
            case 'code':
                valid = /^[A-Z]{2,4}\\d{2,4}$/.test(val);
                break;
            case 'title':
                valid = /^[0-9\\s\\-&,]*[a-zA-Z][a-zA-Z0-9\\s\\-&,]*$/.test(val);
                break;
            case 'dept':
                valid = /^[A-Z]+$/.test(val);
                break;
            case 'days':
                valid = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)(\\/(Mon|Tue|Wed|Thu|Fri|Sat|Sun))*$/.test(val);
                break;
            case 'time':
                valid = /^(1[0-2]|0?[1-9]):[0-5][0-9] (AM|PM)$/.test(val);
                break;
            case 'timeOpt':
                valid = val === "" || /^(1[0-2]|0?[1-9]):[0-5][0-9] (AM|PM)$/.test(val);
                break;
            case 'credits':
                const num = parseInt(val, 15);
                valid = !isNaN(num) && num >= 1 && num <= 15;
                break;
            case 'seats':
                const s = parseInt(val, 10);
                valid = !isNaN(s) && s >= 0;
                break;
        }
    }

    if (!valid && val !== "") {
        el.classList.add('border-red-500', 'bg-red-50');
        el.classList.remove('border-slate-300');
        if (errSpan) errSpan.classList.remove('hidden');
    } else {
        el.classList.remove('border-red-500', 'bg-red-50');
        el.classList.add('border-slate-300');
        if (errSpan) errSpan.classList.add('hidden');
    }
}

function switchAdminTab(tab) {
    const tabs = ['records', 'courses', 'analytics', 'chatlogs'];
    tabs.forEach(t => {
        document.getElementById('admin-section-' + t).classList.add('hidden');
        document.getElementById('tab-' + t).className = 'text-sm font-semibold text-slate-500 pb-1 border-b-2 border-transparent transition';
    });
    
    document.getElementById('admin-section-' + tab).classList.remove('hidden');
    document.getElementById('tab-' + tab).className = 'text-sm font-bold text-indigo-600 pb-1 border-b-2 border-indigo-600 transition';
    
    if (tab === 'records') loadAdminTable();
    if (tab === 'courses') loadAdminCourses();
    if (tab === 'analytics') loadAnalytics();
    if (tab === 'chatlogs') loadChatLogs();
}

function showExportLoader(title = "Preparing Export") {
    document.getElementById('export-loader-title').innerText = title;
    document.getElementById('export-loader').classList.remove('hidden');
}

function hideExportLoader() {
    document.getElementById('export-loader').classList.add('hidden');
}

async function exportStudentsCSV() {
    showExportLoader("Generating CSV...");
    await new Promise(r => setTimeout(r, 600));

    try {
        const res = await fetch('/api/admin/data', { headers: {'Authorization': 'Bearer ' + adminToken} });
        if (!res.ok) throw new Error('Failed to fetch data');
        const data = await res.json();
        const students = data.students || {};

        if (Object.keys(students).length === 0) {
            hideExportLoader();
            return alert("Error: No student records available to export.");
        }

        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "ID,Name,Email,Phone,Field\\n";

        for (const [sid, s] of Object.entries(students)) {
            const name = `"${(s.name || '').replace(/"/g, '""')}"`;
            const email = `"${(s.email || '').replace(/"/g, '""')}"`;
            const phone = `"${(s.phone || '').replace(/"/g, '""')}"`;
            const field = `"${(s.field || '').replace(/"/g, '""')}"`;
            csvContent += `${sid},${name},${email},${phone},${field}\\n`;
        }

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "student_records.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } finally {
        hideExportLoader();
    }
}

function exportAnalyticsPDF() {
    showExportLoader("Compiling Analytics PDF...");
    const element = document.getElementById('analytics-export-area');
    
    if(!element) {
        hideExportLoader();
        return alert("Error finding analytics content.");
    }
    
    const opt = {
        margin:       0.3,
        filename:     'analytics_dashboard.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true },
        jsPDF:        { unit: 'in', format: 'letter', orientation: 'landscape' }
    };
    
    html2pdf().set(opt).from(element).save().then(() => {
        hideExportLoader();
    }).catch(() => {
        hideExportLoader();
        alert("Failed to generate PDF.");
    });
}

function exportChatLogsPDF() {
    showExportLoader("Rendering Chat Logs PDF...");
    const element = document.getElementById('chatlogs-export-area');
    
    if(!element) {
        hideExportLoader();
        return alert("Error finding chat logs content.");
    }
    
    element.classList.remove('max-h-72', 'overflow-y-auto');
    
    const opt = {
        margin:       0.3,
        filename:     'student_chat_logs.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true },
        jsPDF:        { unit: 'in', format: 'letter', orientation: 'landscape' }
    };
    
    html2pdf().set(opt).from(element).save().then(() => {
        element.classList.add('max-h-72', 'overflow-y-auto');
        hideExportLoader();
    }).catch(() => {
        element.classList.add('max-h-72', 'overflow-y-auto');
        hideExportLoader();
        alert("Failed to generate Chat Logs PDF.");
    });
}

async function loadChatLogs() {
    const res = await fetch('/api/admin/data', { headers: {'Authorization': 'Bearer ' + adminToken} });
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById('admin-chatlogs-tbody');
    tbody.innerHTML = '';
    const logs = data.chat_logs || [];
    
    logs.slice().reverse().forEach(log => {
        tbody.innerHTML += `
            <tr class="border-b hover:bg-slate-50">
                <td class="p-3 font-medium text-slate-500 whitespace-nowrap">${log.timestamp}</td>
                <td class="p-3 font-bold text-indigo-600">${log.student_id}</td>
                <td class="p-3 text-slate-700">${log.message}</td>
                <td class="p-3 text-slate-600 text-xs font-semibold">${log.sentiment || 'N/A'}</td>
                <td class="p-3 text-slate-600">${log.reply}</td>
            </tr>
        `;
    });
}

async function loadAdminTable() {
    const res = await fetch('/api/admin/data', { headers: {'Authorization': 'Bearer ' + adminToken} });
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById('admin-students-tbody');
    tbody.innerHTML = '';
    const students = data.students || {};
    for (const [sid, s] of Object.entries(students)) {
        tbody.innerHTML += `
            <tr class="border-b hover:bg-slate-50">
                <td class="p-3 font-bold text-indigo-600">${sid}</td>
                <td class="p-3">${s.name}</td>
                <td class="p-3">${s.email}</td>
                <td class="p-3">${s.phone || 'N/A'}</td>
                <td class="p-3">${s.field || 'N/A'}</td>
                <td class="p-3 text-center">
                    <button onclick="deleteStudent('${sid}')" class="bg-red-50 text-red-600 hover:bg-red-100 px-2 py-1 rounded font-medium transition">Delete</button>
                </td>
            </tr>
        `;
    }
}

function formatScheduleStr(days, start, end) {
    let t = "";
    if (start && end) t = `${start} to ${end}`;
    else if (start) t = `${start} onwards`;
    else t = "TBA";
    return days ? `${days} | ${t}` : t;
}

function validateCourseData(code, title, dept, credits, seats, days, start, end) {
    if (code !== null && !/^[A-Za-z]{2,4}\\d{2,4}$/.test(code)) {
        alert("Invalid Course Code."); return false;
    }
    if (!/^[0-9\\s\\-\\&,]*[a-zA-Z][a-zA-Z0-9\\s\\-\\&,]*$/.test(title)) {
        alert("Invalid Title."); return false;
    }
    if (!/^[A-Za-z]+$/.test(dept)) {
        alert("Invalid Department."); return false;
    }
    if (isNaN(credits) || credits < 1 || credits > 10) {
        alert("Credits must be a number between 1 and 10."); return false;
    }
    if (isNaN(seats) || seats < 0) {
        alert("Seats must be a positive number."); return false;
    }
    
    if (!days || !start) {
        alert("You must provide at least Days and a Start Time."); return false;
    }

    const daysRegex = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)(\\/(Mon|Tue|Wed|Thu|Fri|Sat|Sun))*$/;
    if (!daysRegex.test(days)) {
        alert("Invalid Days format. Use 3-letter abbreviations separated by a slash (e.g., Mon/Wed, Tue/Thu/Fri).");
        return false;
    }

    const timeRegex = /^(1[0-2]|0?[1-9]):[0-5][0-9] (AM|PM)$/;
    
    if (!timeRegex.test(start)) {
        alert("Start time must be in strict format: HH:MM AM/PM (e.g., 10:00 AM or 02:30 PM)");
        return false;
    }
    
    if (end) {
        if (!timeRegex.test(end)) {
            alert("End time must be in strict format: HH:MM AM/PM (e.g., 11:30 AM)");
            return false;
        }

        const parseTime = (timeStr) => {
            const [time, modifier] = timeStr.split(' ');
            let [hours, minutes] = time.split(':');
            if (hours === '12') hours = '00';
            if (modifier === 'PM') hours = parseInt(hours, 10) + 12;
            return (parseInt(hours, 10) * 60) + parseInt(minutes, 10);
        };
        
        if (parseTime(start) >= parseTime(end)) {
            alert("Strict Time Bound Error: End time must be strictly after the start time.");
            return false;
        }
    }
    return true;
}

async function loadAdminCourses() {
    const res = await fetch('/api/admin/data', { headers: {'Authorization': 'Bearer ' + adminToken} });
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById('admin-courses-tbody');
    tbody.innerHTML = '';
    const courses = data.courses || {};
    for (const [code, c] of Object.entries(courses)) {
        const safeTitle = c.title.replace(/'/g, "\\'");
        const safeDept = c.dept.replace(/'/g, "\\'");
        
        const safeDays = (c.days || "").replace(/'/g, "\\'");
        const safeStart = (c.start_time || "").replace(/'/g, "\\'");
        const safeEnd = (c.end_time || "").replace(/'/g, "\\'");
        
        const displaySchedule = formatScheduleStr(c.days, c.start_time, c.end_time);
        
        tbody.innerHTML += `
            <tr class="border-b hover:bg-slate-50">
                <td class="p-3 font-bold text-indigo-600">${code}</td>
                <td class="p-3">${c.title}</td>
                <td class="p-3 font-medium text-slate-500">${c.dept}</td>
                <td class="p-3 text-slate-500 font-medium">${displaySchedule}</td>
                <td class="p-3">${c.credits}</td>
                <td class="p-3">
                    <span class="px-2 py-1 rounded-full text-[10px] font-bold ${c.seats > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
                        ${c.seats > 0 ? c.seats + ' SEATS' : 'FULL'}
                    </span>
                </td>
                <td class="p-3 text-center flex justify-center gap-2">
                    <button onclick="openEditModal('${code}', '${safeTitle}', '${safeDept}', ${c.credits}, ${c.seats}, '${safeDays}', '${safeStart}', '${safeEnd}')" class="bg-indigo-50 text-indigo-600 hover:bg-indigo-100 px-2 py-1 rounded font-medium transition">Edit</button>
                    <button onclick="deleteCourse('${code}')" class="bg-red-50 text-red-600 hover:bg-red-100 px-2 py-1 rounded font-medium transition">Delete</button>
                </td>
            </tr>
        `;
    }
}

async function addCourse() {
    const payload = {
        code: document.getElementById('new-course-code').value.toUpperCase(),
        title: document.getElementById('new-course-title').value,
        dept: document.getElementById('new-course-dept').value.toUpperCase(),
        credits: parseInt(document.getElementById('new-course-credits').value),
        seats: parseInt(document.getElementById('new-course-seats').value),
        days: document.getElementById('new-course-days').value,
        start_time: document.getElementById('new-course-start').value,
        end_time: document.getElementById('new-course-end').value || ""
    };
    
    if (!validateCourseData(payload.code, payload.title, payload.dept, payload.credits, payload.seats, payload.days, payload.start_time, payload.end_time)) return;

    const res = await fetch('/api/admin/add-course', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + adminToken},
        body: JSON.stringify(payload)
    });
    const d = await res.json();

    if (res.ok) {
        const fields = [
            'new-course-code',
            'new-course-title',
            'new-course-dept',
            'new-course-days',
            'new-course-start',
            'new-course-end'
        ];

        fields.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                input.value = '';
                input.classList.remove('border-red-500', 'bg-red-50');
                input.classList.add('border-slate-300');
            }
            const err = document.getElementById('err-' + id);
            if (err) err.classList.add('hidden');
        });

        document.getElementById('new-course-credits').value = '3';
        document.getElementById('new-course-seats').value = '30';

        loadAdminCourses();
    } else {
        alert(d.detail || "Failed to add course.");
    }
}

async function deleteCourse(code) {
    if (!confirm(`Permanently delete ${code}? This will also remove it from any enrolled students' schedules.`)) return;
    const res = await fetch('/api/admin/delete-course/' + code, {
        method: 'DELETE',
        headers: {'Authorization': 'Bearer ' + adminToken}
    });
    if (res.ok) loadAdminCourses();
    else alert("Failed to delete course.");
}

function openEditModal(code, title, dept, credits, seats, days, start, end) {
    document.getElementById('edit-course-code').value = code;
    document.getElementById('edit-course-header').innerText = `Editing ${code}`;
    document.getElementById('edit-course-title').value = title;
    document.getElementById('edit-course-dept').value = dept;
    document.getElementById('edit-course-credits').value = credits;
    document.getElementById('edit-course-seats').value = seats;
    document.getElementById('edit-course-days').value = days;
    document.getElementById('edit-course-start').value = start;
    document.getElementById('edit-course-end').value = end;
    document.getElementById('modal-edit-course').classList.remove('hidden');
}

function closeEditModal() {
    document.getElementById('modal-edit-course').classList.add('hidden');
}

async function saveCourseEdit() {
    const code = document.getElementById('edit-course-code').value;
    const payload = {
        title: document.getElementById('edit-course-title').value,
        dept: document.getElementById('edit-course-dept').value.toUpperCase(),
        credits: parseInt(document.getElementById('edit-course-credits').value),
        seats: parseInt(document.getElementById('edit-course-seats').value),
        days: document.getElementById('edit-course-days').value,
        start_time: document.getElementById('edit-course-start').value,
        end_time: document.getElementById('edit-course-end').value || ""
    };
    
    if (!validateCourseData(null, payload.title, payload.dept, payload.credits, payload.seats, payload.days, payload.start_time, payload.end_time)) return;

    const res = await fetch('/api/admin/update-course/' + code, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + adminToken},
        body: JSON.stringify(payload)
    });
    
    if (res.ok) {
        closeEditModal();
        loadAdminCourses();
    } else {
        alert("Failed to update course.");
    }
}

async function resetCatalog() {
    if (!confirm('Restore default catalog? This will overwrite manual additions but keeps students.')) return;
    const res = await fetch('/api/admin/reset-catalog', {
        method: 'POST',
        headers: {'Authorization': 'Bearer ' + adminToken}
    });
    if (res.ok) loadAdminCourses();
}

async function loadAnalytics() {
    const res = await fetch('/api/admin/analytics', { headers: {'Authorization': 'Bearer ' + adminToken} });
    if (!res.ok) return;
    const data = await res.json();
    
    document.getElementById('stat-students').innerText = data.total_students;
    document.getElementById('stat-regs').innerText = data.total_registrations;
    document.getElementById('stat-logins').innerText = data.total_logins;

    const ctx = document.getElementById('analyticsChart').getContext('2d');
    if (chartInstance) chartInstance.destroy();
    
    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(data.field_distribution),
            datasets: [{
                label: 'Enrolled Students by Major',
                data: Object.values(data.field_distribution),
                backgroundColor: '#4f46e5',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });
}

async function deleteStudent(studentId) {
    if (!confirm('Permanently delete student record ' + studentId + '?')) return;
    await fetch('/api/admin/delete-student/' + studentId, {
        method: 'DELETE',
        headers: {'Authorization': 'Bearer ' + adminToken}
    });
    loadAdminTable();
}

async function clearAllStudents() {
    if (!confirm('Erase all student records from database?')) return;
    await fetch('/api/admin/clear-all-students', {
        method: 'POST',
        headers: {'Authorization': 'Bearer ' + adminToken}
    });
    loadAdminTable();
}

// -------------------------------------------------------------
// PHONE VERIFICATION ANIMATION
// -------------------------------------------------------------
async function verifyPhoneAnimation() {
    const phoneInput = document.getElementById('reg-phone').value.trim();
    const localNum = phoneInput.substring(3);
    
    const isDummy = /^(\\d)\1{9}$/.test(localNum) || localNum === "9876543210" || localNum === "6789012345";

    if (!phoneInput || !/^\\+91[6-9]\\d{9}$/.test(phoneInput) || isDummy) {
        return alert("Please enter a valid 12-digit Indian phone number starting with +91 (Dummy numbers are rejected).");
    }
    
    const btn = document.getElementById('btn-verify-phone');
    btn.disabled = true;
    btn.innerText = "Verifying...";
    
    const container = document.getElementById('phone-verify-container');
    container.classList.remove('hidden');
    
    for(let i=1; i<=3; i++) {
        document.getElementById(`pv-spin-${i}`).classList.remove('hidden');
        document.getElementById(`pv-icon-${i}`).classList.add('hidden');
        document.getElementById(`pv-val-${i}`).innerText = "Pending...";
    }
    
    await new Promise(r => setTimeout(r, 900));
    document.getElementById('pv-spin-1').classList.add('hidden');
    document.getElementById('pv-icon-1').classList.remove('hidden');
    document.getElementById('pv-val-1').innerText = "Verified (GlobalTel)";
    
    document.getElementById('pv-spin-2').classList.remove('hidden');
    await new Promise(r => setTimeout(r, 1200));
    document.getElementById('pv-spin-2').classList.add('hidden');
    document.getElementById('pv-icon-2').classList.remove('hidden');
    document.getElementById('pv-val-2').innerText = "Active Line";
    
    document.getElementById('pv-spin-3').classList.remove('hidden');
    await new Promise(r => setTimeout(r, 1100));
    document.getElementById('pv-spin-3').classList.add('hidden');
    document.getElementById('pv-icon-3').classList.remove('hidden');
    document.getElementById('pv-val-3').innerText = "Secure ✅";
    
    btn.innerText = "Verified";
    btn.classList.add('bg-green-600', 'hover:bg-green-700');
    btn.classList.remove('bg-slate-800');
    lastVerifiedPhone = phoneInput;
}

async function sendOtp() {
    const target = document.getElementById('reg-email').value;
    if (!target) return alert('Enter a valid email address.');

    const btn = document.getElementById('btn-send');
    btn.innerText = 'Sending...';
    btn.disabled = true;

    try {
        const res = await fetch('/api/auth/send-otp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target})
        });
        const d = await res.json();
        if (!res.ok) {
            alert(d.detail || 'Dispatch failed.');
        } else {
            alert(d.message);
            if (emailPoller) clearInterval(emailPoller);
            emailPoller = setInterval(async () => {
                const chk = await fetch('/api/auth/check-status?target=' + encodeURIComponent(target));
                const stat = await chk.json();
                if (stat.verified) {
                    document.getElementById('email-status').innerText = 'Status: Verified via Link ✅';
                    document.getElementById('email-status').className = 'text-xs text-green-600 font-semibold';
                    clearInterval(emailPoller);
                }
            }, 3000);
        }
    } finally {
        btn.innerText = 'Send Code';
        btn.disabled = false;
    }
}

async function verifyOtp() {
    const target = document.getElementById('reg-email').value.trim();
    const otp = document.getElementById('otp-email-val').value.trim();

    if (!target) {
        return alert("Please enter your email address first.");
    }
    if (!otp || otp.length !== 6) {
        return alert("Please enter the full 6-digit code sent to your inbox.");
    }

    try {
        const res = await fetch('/api/auth/verify-otp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target, otp})
        });
        
        const d = await res.json();
        
        if (res.ok) {
            document.getElementById('email-status').innerText = 'Status: Verified ✅';
            document.getElementById('email-status').className = 'text-xs text-green-600 font-semibold';
            if (emailPoller) clearInterval(emailPoller);
            alert(d.message || "Email successfully verified.");
        } else {
            let errorMessage = "Verification failed.";
            if (d.detail) {
                errorMessage = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
            }
            alert(errorMessage);
        }
    } catch (err) {
        alert("Network or server error during verification.");
    }
}

function validateRegistrationForm(name, phone) {
    const nameRegex = /^[A-Za-z\\s]+$/;
    
    if (!nameRegex.test(name)) {
        alert("Invalid Input: Name must only contain letters and spaces. Numbers and special characters are not allowed.");
        document.getElementById('reg-name').focus();
        return false;
    }
    
    const localNum = phone.substring(3);
    const isDummy = /^(\\d)\\1{9}$/.test(localNum) || localNum === "9876543210" || localNum === "6789012345";

    if (!/^\\+91[6-9]\\d{9}$/.test(phone) || isDummy) {
        alert("Please enter a valid 12-digit Indian phone number starting with +91 (Dummy numbers are rejected).");
        document.getElementById('reg-phone').focus();
        return false;
    }
    return true;
}

async function handleStudentRegister() {
    const name = document.getElementById('reg-name').value;
    const phone = document.getElementById('reg-phone').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-pass').value;
    const course = document.getElementById('reg-course').value;

    if(!validateRegistrationForm(name, phone)) return;

    const res = await fetch('/api/auth/register-student', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, phone, email, password, course})
    });
    const data = await res.json();
    
    if (!res.ok) {
        let msg = data.detail;
        if (Array.isArray(msg)) msg = msg.map(err => err.msg).join(', ');
        return alert(msg);
    }

    currentStudentId = data.student_id;
    startChat(data.name, data.student_id);
}

async function handleStudentLogin() {
    const email = document.getElementById('student-login-email').value;
    const password = document.getElementById('student-login-pass').value;

    const res = await fetch('/api/auth/student-login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password})
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || 'Invalid credentials');

    currentStudentId = data.student_id;
    startChat(data.student.name, data.student_id);
}

async function handleForgotPasswordSend() {
    const email = document.getElementById('forgot-email').value.trim();
    if (!email) return alert('Please enter your registered email address.');
    
    const btn = document.getElementById('btn-send-pass');
    btn.innerText = 'Sending...';
    btn.disabled = true;

    try {
        const res = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email})
        });
        const data = await res.json();
        
        if (res.ok) {
            alert('A temporary password has been sent to your email inbox.');
        } else {
            alert(data.detail || 'Failed to send password reset request.');
        }
    } finally {
        btn.innerText = 'Get Password';
        btn.disabled = false;
    }
}

async function handleForgotPasswordLogin() {
    const email = document.getElementById('forgot-email').value.trim();
    const password = document.getElementById('forgot-temp-pass').value.trim();
    
    if (!email || !password) return alert('Please enter both your email and the temporary password.');

    const res = await fetch('/api/auth/student-login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password})
    });
    
    const data = await res.json();
    if (!res.ok) return alert('Invalid temporary password or email. Please check your inbox.');

    currentStudentId = data.student_id;
    startChat(data.student.name, data.student_id);
}

const QUICK_FAQS = [
    "What courses are available in the catalog?",
    "Show my current class schedule.",
    "Are there any open seats in CS101?",
    "Register me for MATH101.",
    "Unregister me from MATH101."
];

function sendSuggestedMessage(msg) {
    document.getElementById('chat-input').value = msg;
    document.getElementById('chat-form').dispatchEvent(new Event('submit'));
}

function startChat(name, id) {
    hideAllViews();
    document.getElementById('view-chat').classList.remove('hidden');
    document.getElementById('chat-user-banner').innerText = `Session: ${name} (ID: ${id})`;
    
    let suggestionHTML = '<div class="flex flex-wrap gap-2 mt-4">';
    QUICK_FAQS.forEach(s => {
        const safeMsg = s.replace(/'/g, "\\'");
        suggestionHTML += `<button type="button" onclick="sendSuggestedMessage('${safeMsg}')" class="bg-indigo-100 text-indigo-800 border border-indigo-200 hover:bg-indigo-200 hover:border-indigo-300 px-3.5 py-1.5 rounded-full text-xs font-medium transition text-left">${s}</button>`;
    });
    suggestionHTML += '</div>';

    document.getElementById('chat-box').innerHTML = `
        <div class="bg-white p-5 rounded-2xl text-slate-800 border border-slate-200 shadow-sm mb-4">
            <h3 class="text-lg font-bold text-indigo-600 mb-1">👋 Welcome, ${name}!</h3>
            <p class="text-sm text-slate-600">I am your AI Registration Assistant. I can check course availability, manage your schedule, and register you for classes.</p>
            <p class="text-xs font-semibold text-slate-500 mt-4 mb-2 uppercase tracking-wide">Frequently Asked Questions</p>
            ${suggestionHTML}
        </div>
    `;
}

document.getElementById('chat-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const msg = input.value.trim();
    if (!msg) return;

    input.disabled = true;
    submitBtn.disabled = true;
    submitBtn.innerText = '...';

    const userTime = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    const box = document.getElementById('chat-box');
    
    box.innerHTML += `
        <div class="text-right mb-4">
            <span class="bg-indigo-600 text-white px-4 py-2.5 rounded-2xl rounded-tr-sm inline-block shadow-sm">
                ${msg}
                <div class="text-[9px] text-indigo-200 text-right mt-1">${userTime}</div>
            </span>
        </div>`;
    input.value = '';
    box.scrollTop = box.scrollHeight;

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({student_id: currentStudentId, message: msg})
        });
        
        const d = await res.json();
        if (!res.ok) throw new Error(d.detail || "Server connectivity error.");
        
        const aiTime = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        box.innerHTML += `
            <div class="text-left mb-4">
                <span class="bg-white text-slate-800 border border-slate-200 px-4 py-2.5 rounded-2xl rounded-tl-sm inline-block whitespace-pre-line shadow-sm leading-relaxed">
                    ${marked.parse(d.reply)}
                    <div class="text-[9px] text-slate-400 mt-1">${aiTime}</div>
                </span>
            </div>`;
            
        if (window.MathJax) {
            MathJax.typesetPromise([box]).catch((err) => console.log('MathJax error:', err.message));
        }
    } catch (err) {
        box.innerHTML += `
            <div class="text-left mb-4">
                <span class="bg-red-50 text-red-600 border border-red-200 px-4 py-2.5 rounded-2xl rounded-tl-sm inline-block shadow-sm text-sm">
                    ⚠️ **Error:** ${err.message}
                </span>
            </div>`;
    } finally {
        input.disabled = false;
        submitBtn.disabled = false;
        submitBtn.innerText = 'Send';
        input.focus();
        box.scrollTop = box.scrollHeight;
    }
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    # To run locally with this file: python main.py
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)

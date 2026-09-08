import os
import re
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    ToolMessage,
)

# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

load_dotenv()

api_key = "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"

if not api_key:
    raise RuntimeError(
        "Groq API key not found. "
        "Create a .env file and set GROQ_API_KEY=gsk_..."
    )

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="University AI Assistant & Complete Management Engine",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# GROQ / LANGCHAIN MODEL
# ============================================================

try:
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        groq_api_key=api_key,
        temperature=0,
        max_tokens=800,
    )
except Exception as e:
    raise RuntimeError(f"Failed to initialize Groq model: {e}")

# ============================================================
# VALIDATION & SENTIMENT HELPERS
# ============================================================

def validate_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))

def validate_name(name: str) -> bool:
    pattern = r"^[A-Za-z\s\-]+$"
    return bool(re.match(pattern, name)) and len(name.strip()) >= 2

def analyze_sentiment(text: str) -> str:
    """Lightweight sentiment analysis based on keywords."""
    text_lower = text.lower()
    frustrated_words = ["angry", "bad", "useless", "fail", "error", "stuck", "horrible", "stupid"]
    happy_words = ["thanks", "thank", "great", "awesome", "helpful", "perfect", "good", "love"]
    
    if any(word in text_lower for word in frustrated_words):
        return "Frustrated 🔴"
    elif any(word in text_lower for word in happy_words):
        return "Positive 🟢"
    return "Neutral 🟡"


# ============================================================
# JSON FILE PERSISTENCE & ANALYTICS LAYER
# ============================================================

DATA_FILE = "university_data.json"
ANALYTICS_FILE = "analytics_log.json"

DEFAULT_DATA = {
    "courses": {
        "CS101": {
            "title": "Intro to Computer Science",
            "dept": "CS",
            "credits": 3,
            "prereqs": [],
            "seats": 5,
            "schedule": "MWF 09:00-10:00 AM",
        },
        "CS301": {
            "title": "Data Structures & Algorithms",
            "dept": "CS",
            "credits": 4,
            "prereqs": ["CS101"],
            "seats": 0,
            "schedule": "TTh 11:00-12:30 PM",
        },
        "MATH101": {
            "title": "Calculus I",
            "dept": "MATH",
            "credits": 4,
            "prereqs": [],
            "seats": 8,
            "schedule": "MWF 10:00-11:00 AM",
        },
        "MATH202": {
            "title": "Linear Algebra",
            "dept": "MATH",
            "credits": 3,
            "prereqs": ["MATH101"],
            "seats": 12,
            "schedule": "TTh 02:00-03:30 PM",
        },
        "BIO101": {
            "title": "General Biology",
            "dept": "BIO",
            "credits": 4,
            "prereqs": [],
            "seats": 3,
            "schedule": "MWF 09:00-10:00 AM",
        },
    },
    "students": {}
}

def load_database() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        save_database(DEFAULT_DATA)
        return DEFAULT_DATA
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        save_database(DEFAULT_DATA)
        return DEFAULT_DATA

def save_database(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def log_interaction(student_id: str, message: str, intent: str, sentiment: str) -> None:
    """Log interaction details and detected sentiment for analytics."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "student_id": student_id,
        "message": message,
        "intent": intent,
        "sentiment": sentiment
    }
    logs = []
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    logs.append(log_entry)
    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)


# In-memory session tracking
CHAT_HISTORY: Dict[str, List[Any]] = {}
ACTIVE_STUDENT_SESSION: Dict[str, str] = {}


# ============================================================
# TOOLS (STUDENT OPERATIONS, COURSES, & FAQS)
# ============================================================

@tool
def register_new_student(name: str, email: str, field: str) -> str:
    """Register a new student by collecting name, email, and field of study and saving to JSON file."""
    clean_name = name.strip()
    clean_email = email.strip().lower()
    clean_field = field.strip()

    if not validate_name(clean_name):
        return f"❌ Registration Error: '{name}' is invalid. Names must contain only alphabetic characters and spaces."
    
    if not validate_email(clean_email):
        return f"❌ Registration Error: '{email}' is not a valid email address format (e.g., user@domain.com)."

    db = load_database()

    for sid, sdata in db["students"].items():
        if sdata.get("email") == clean_email:
            return f"ℹ️ Notice: An account with email {clean_email} already exists (Student ID: {sid}). You are logged in!"

    new_id = str(int(max(db["students"].keys(), key=lambda x: int(x) if x.isdigit() else 10000)) + 1) if db["students"] else "10001"

    db["students"][new_id] = {
        "name": clean_name,
        "email": clean_email,
        "field": clean_field,
        "completed_courses": [],
        "enrolled_courses": [],
        "max_credits": 18,
    }

    save_database(db)

    return (
        f"✅ Success! Your student account has been created and saved.\n"
        f"• Assigned Student ID: {new_id}\n"
        f"• Name: {clean_name}\n"
        f"• Email: {clean_email}\n"
        f"• Field of Study: {clean_field}\n\n"
        f"You are now fully registered and logged in!"
    )


@tool
def login_student(email: str) -> str:
    """Log in an existing student using their registered email address from JSON storage."""
    clean_email = email.strip().lower()

    if not validate_email(clean_email):
        return f"❌ Login Error: '{email}' is not a valid email format."

    db = load_database()

    for sid, sdata in db["students"].items():
        if sdata.get("email") == clean_email:
            return (
                f"✅ Login Successful! Welcome back, {sdata['name']}.\n"
                f"• Student ID: {sid}\n"
                f"• Field: {sdata.get('field', 'General')}\n"
                f"• Enrolled Courses: {', '.join(sdata['enrolled_courses']) if sdata['enrolled_courses'] else 'None'}"
            )

    return f"❌ Login Error: No account found with email {clean_email}. Please provide your details to register first."


@tool
def get_course_catalog(department: Optional[str] = None) -> str:
    """Retrieve available courses from the JSON catalog, optionally filtered by department."""
    if department and department.strip().lower() in ["none", "null"]:
        department = None

    db = load_database()
    results: List[str] = []

    for code, info in db["courses"].items():
        if department:
            if info["dept"].upper() != department.upper().strip():
                continue

        status = "OPEN" if info["seats"] > 0 else "FULL"
        prerequisites = ", ".join(info["prereqs"]) if info["prereqs"] else "None"

        results.append(
            f"• {code}: {info['title']} "
            f"({info['credits']} Credits) | "
            f"Schedule: {info['schedule']} | "
            f"Status: {status} "
            f"({info['seats']} seats left) | "
            f"Prereqs: {prerequisites}"
        )

    if not results:
        if department:
            return f"ℹ️ No courses found for department '{department}'."
        return "ℹ️ No courses are currently available."

    return "📚 Course Catalog:\n" + "\n".join(results)


@tool
def view_student_schedule(student_id: str) -> str:
    """View the student's current schedule, credit hours, and enrolled courses from storage."""
    db = load_database()
    student = db["students"].get(student_id)
    if not student:
        return f"❌ Error: No profile found for Student ID {student_id}. Please register or log in first."

    enrolled = student["enrolled_courses"]
    if not enrolled:
        return f"ℹ️ Student {student['name']} (ID: {student_id}) is not currently enrolled in any courses."

    schedule_lines: List[str] = []
    total_credits = 0

    for code in enrolled:
        course = db["courses"].get(code)
        if course:
            schedule_lines.append(
                f"• {code}: {course['title']} | "
                f"{course['schedule']} "
                f"({course['credits']} Cr)"
            )
            total_credits += course["credits"]

    completed = ", ".join(student["completed_courses"]) if student["completed_courses"] else "None"

    return (
        f"📅 Student Schedule ({student['name']} - ID: {student_id}):\n"
        + "\n".join(schedule_lines)
        + "\n"
        f"• Total Registered Credits: {total_credits}/{student['max_credits']} Credits.\n"
        f"• Completed Courses: {completed}"
    )


@tool
def check_prerequisites(student_id: str, course_code: str) -> str:
    """Check whether a student satisfies prerequisites for a specific course."""
    clean_code = course_code.upper().strip()
    db = load_database()
    student = db["students"].get(student_id)

    if not student:
        return f"❌ Error: Please register or log in before checking prerequisites."

    course = db["courses"].get(clean_code)
    if not course:
        return f"❌ Error: Course {clean_code} was not found in the catalog."

    missing = [
        prerequisite
        for prerequisite in course["prereqs"]
        if prerequisite not in student["completed_courses"]
    ]

    if missing:
        return f"⚠️ Ineligible for {clean_code}. Missing prerequisite(s): {', '.join(missing)}."

    return f"✅ Eligible! You satisfy all prerequisites for {clean_code}."


@tool
def check_seat_availability(course_code: str) -> str:
    """Check remaining seats for a specific course."""
    clean_code = course_code.upper().strip()
    db = load_database()
    course = db["courses"].get(clean_code)

    if not course:
        return f"❌ Error: Course {clean_code} was not found in the catalog."

    seats = course["seats"]
    if seats > 0:
        return f"✅ Course {clean_code} ({course['title']}) is OPEN with {seats} seats remaining."

    return f"⚠️ Course {clean_code} ({course['title']}) is FULL (0 seats remaining)."


@tool
def register_for_course(student_id: str, course_code: str) -> str:
    """Register a student for a course, update seat counts, and persist changes to JSON."""
    clean_code = course_code.upper().strip()
    db = load_database()
    student = db["students"].get(student_id)

    if not student:
        return f"❌ Error: You must register or log in before enrolling in courses."

    course = db["courses"].get(clean_code)
    if not course:
        return f"❌ Error: Course {clean_code} does not exist."

    if clean_code in student["enrolled_courses"]:
        return f"ℹ️ Notice: You are already enrolled in {clean_code}."

    missing = [
        prerequisite
        for prerequisite in course["prereqs"]
        if prerequisite not in student["completed_courses"]
    ]
    if missing:
        return f"❌ Registration Failed: Missing prerequisite(s) {', '.join(missing)} for {clean_code}."

    if course["seats"] <= 0:
        return f"❌ Registration Failed: {clean_code} is full (0 seats remaining)."

    current_credits = sum(
        db["courses"][code]["credits"]
        for code in student["enrolled_courses"]
        if code in db["courses"]
    )
    new_total = current_credits + course["credits"]

    if new_total > student["max_credits"]:
        return f"❌ Registration Failed: Exceeds maximum term credit limit of {student['max_credits']}."

    new_schedule = course["schedule"]
    for enrolled_code in student["enrolled_courses"]:
        enrolled_course = db["courses"].get(enrolled_code)
        if enrolled_course and enrolled_course["schedule"] == new_schedule:
            return f"❌ Registration Failed: Schedule conflict with {enrolled_code} ({new_schedule})."

    course["seats"] -= 1
    student["enrolled_courses"].append(clean_code)
    save_database(db)

    return f"✅ Success! Enrolled in {clean_code} ({course['title']}). Remaining seats: {course['seats']}."


@tool
def drop_course(student_id: str, course_code: str) -> str:
    """Drop a course from the student's enrollment and update JSON storage."""
    clean_code = course_code.upper().strip()
    db = load_database()
    student = db["students"].get(student_id)

    if not student:
        return f"❌ Error: Profile not found. Please log in first."

    if clean_code not in student["enrolled_courses"]:
        return f"❌ Drop Failed: You are not currently registered for {clean_code}."

    student["enrolled_courses"].remove(clean_code)

    if clean_code in db["courses"]:
        db["courses"][clean_code]["seats"] += 1
        save_database(db)
        return f"✅ Success! Dropped {clean_code}. Updated seat count: {db['courses'][clean_code]['seats']}."

    save_database(db)
    return f"✅ Success! Dropped {clean_code}."


@tool
def handle_university_faq(query_topic: str) -> str:
    """Provide answers to university frequently asked questions (tuition, housing, library, parking)."""
    faqs = {
        "tuition": "Tuition payment for the current term is due by the 1st of next month.",
        "housing": "On-campus housing applications open every March for the upcoming academic year.",
        "library": "The campus library is open Monday to Saturday from 8:00 AM to 10:00 PM.",
        "parking": "Student parking permits can be picked up at the administrative office with your Student ID."
    }
    key = query_topic.lower().strip()
    for topic, answer in faqs.items():
        if topic in key:
            return f"📌 FAQ Answer ({topic.capitalize()}): {answer}"
    return "ℹ️ For specific FAQs, please ask about: tuition, housing, library, or parking."


tools = [
    register_new_student,
    login_student,
    get_course_catalog,
    view_student_schedule,
    check_prerequisites,
    check_seat_availability,
    register_for_course,
    drop_course,
    handle_university_faq,
]

tools_by_name = {current_tool.name: current_tool for current_tool in tools}
llm_with_tools = llm.bind_tools(tools)


class ChatRequest(BaseModel):
    student_id: Optional[str] = "GUEST"
    message: str


# ============================================================
# CONVERSATION ENGINE (WITH STRICT AUTH & MULTI-LANGUAGE)
# ============================================================

async def process_ai_request(client_session_id: str, user_message: str):
    db = load_database()
    
    # Strict Session Check: Default to GUEST unless explicitly logged in
    current_student_id = ACTIVE_STUDENT_SESSION.get(client_session_id, "GUEST")
    if current_student_id != "GUEST" and current_student_id not in db["students"]:
        current_student_id = "GUEST"
        ACTIVE_STUDENT_SESSION[client_session_id] = "GUEST"

    is_authenticated = current_student_id in db["students"]

    system_prompt = f"""
ROLE: CampusBot, University AI Assistant & JSON Storage Engine.
SESSION ID: {client_session_id}
CURRENT AUTHENTICATED STUDENT ID: {current_student_id}
IS AUTHENTICATED: {str(is_authenticated).upper()}

INSTRUCTIONS:
1. MANDATORY ONBOARDING & LOGIN: If IS AUTHENTICATED is FALSE, you do not know the user. Do NOT assume they are logged in. If they provide their name, email, and field, call `register_new_student`. If they want to log in, ask for their email and call `login_student`.
2. RESTRICTED ACCESS: If IS AUTHENTICATED is FALSE, block them from viewing schedules or registering for classes until they log in or register.
3. AUTHENTICATED ACTIONS: Use their bound Student ID ({current_student_id}) to execute course queries automatically.
4. MULTI-LANGUAGE SUPPORT: Detect the user's language and respond fluently in that exact same language, translating tool outputs if necessary.
5. CONCISENESS: Keep responses short (1-2 sentences).
""".strip()

    if client_session_id not in CHAT_HISTORY:
        CHAT_HISTORY[client_session_id] = [SystemMessage(content=system_prompt)]
    else:
        CHAT_HISTORY[client_session_id][0] = SystemMessage(content=system_prompt)

    CHAT_HISTORY[client_session_id].append(HumanMessage(content=user_message))
    messages = CHAT_HISTORY[client_session_id]

    detected_intent = "general_inquiry"
    detected_course = None
    tool_results: List[str] = []

    max_rounds = 5

    try:
        for _ in range(max_rounds):
            ai_message = await llm_with_tools.ainvoke(messages)
            messages.append(ai_message)

            if not getattr(ai_message, 'tool_calls', None):
                final_content = ai_message.content
                if isinstance(final_content, list):
                    parts = []
                    for item in final_content:
                        if isinstance(item, dict):
                            text = item.get("text")
                            if text:
                                parts.append(str(text))
                        else:
                            parts.append(str(item))
                    final_content = "\n".join(parts)
                
                if tool_results:
                    combined_tools = "\n\n".join(tool_results)
                    final_str = str(final_content).strip()
                    if combined_tools not in final_str:
                        final_content = f"{final_str}\n\n{combined_tools}" if final_str else combined_tools

                if not final_content or len(str(final_content).strip()) < 2:
                    final_content = "Please provide your registered email address to log in or your details to register."

                # Analyze sentiment and log the interaction
                sentiment = analyze_sentiment(user_message)
                log_interaction(current_student_id, user_message, detected_intent, sentiment)

                return str(final_content).strip(), detected_intent, detected_course

            for tool_call in ai_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = dict(tool_call.get("args") or {})

                detected_intent = tool_name
                if "course_code" in tool_args:
                    detected_course = tool_args["course_code"]

                selected_tool = tools_by_name.get(tool_name)

                if selected_tool is None:
                    tool_output = f"⚠️ Unknown tool requested: {tool_name}"
                else:
                    if "student_id" in selected_tool.args:
                        if is_authenticated:
                            tool_args["student_id"] = current_student_id
                        elif tool_name not in ["register_new_student", "login_student"]:
                            tool_output = "⚠️ Action denied: You must register or log in first."
                            tool_results.append(tool_output)
                            messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))
                            continue

                    try:
                        tool_output = selected_tool.invoke(tool_args)
                        
                        if tool_name in ["register_new_student", "login_student"] and "Success" in tool_output:
                            fresh_db = load_database()
                            for sid, sdata in fresh_db["students"].items():
                                if tool_args.get("email", "").lower().strip() == sdata.get("email"):
                                    ACTIVE_STUDENT_SESSION[client_session_id] = sid
                                    break

                    except Exception as tool_error:
                        tool_output = f"⚠️ Tool execution error: {type(tool_error).__name__}."

                tool_results.append(str(tool_output))
                messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))

        if tool_results:
            sentiment = analyze_sentiment(user_message)
            log_interaction(current_student_id, user_message, detected_intent, sentiment)
            return "\n\n".join(tool_results), detected_intent, detected_course

    except Exception as engine_error:
        print(f"Engine Error: {type(engine_error).__name__}: {engine_error}")
        return "⚠️ An unexpected error occurred. Please provide your email to log in.", "fallback_error", None

    return "Please provide your email to log in.", "fallback_onboarding", None


# ============================================================
# ADMIN ANALYTICS ENDPOINT
# ============================================================

@app.get("/api/admin/analytics")
async def get_admin_analytics():
    """Admin dashboard endpoint to check students, courses, and chat analytics logs."""
    db = load_database()
    total_students = len(db["students"])
    total_courses = len(db["courses"])
    
    interaction_logs = []
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                interaction_logs = json.load(f)
        except Exception:
            interaction_logs = []
            
    return {
        "status": "success",
        "metrics": {
            "total_registered_students": total_students,
            "total_catalog_courses": total_courses,
            "total_chat_interactions": len(interaction_logs)
        },
        "recent_logs": interaction_logs[-10:]
    }


# ============================================================
# FRONTEND UI WITH ADMIN DASHBOARD TOGGLE
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>University AI Assistant & Admin Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 min-h-screen flex flex-col">

<header class="bg-indigo-600 text-white shadow-md p-4">
    <div class="max-w-3xl mx-auto flex items-center justify-between">
        <div class="flex items-center space-x-3">
            <span class="text-2xl">🎓</span>
            <div>
                <h1 class="text-lg font-semibold">CampusBot</h1>
                <p class="text-xs text-indigo-100">Multi-Language & Persistent Portal</p>
            </div>
        </div>
        <div class="flex items-center space-x-2">
            <button onclick="toggleAdminDashboard()" class="text-xs bg-indigo-700 hover:bg-indigo-800 text-white px-3 py-1.5 rounded-lg font-medium transition">Admin Dashboard</button>
            <span class="text-xs bg-indigo-500 px-3 py-1 rounded-full font-medium">Online</span>
        </div>
    </div>
</header>

<!-- Admin Modal -->
<div id="admin-modal" class="hidden fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
    <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
        <div class="flex justify-between items-center border-b pb-3">
            <h2 class="text-lg font-semibold text-slate-800">📊 Admin Analytics Dashboard</h2>
            <button onclick="toggleAdminDashboard()" class="text-slate-400 hover:text-slate-600 font-bold">✕</button>
        </div>
        <div id="admin-content" class="space-y-3 text-sm text-slate-600">
            <p class="animate-pulse">Loading analytics data...</p>
        </div>
        <div class="text-right pt-2">
            <button onclick="toggleAdminDashboard()" class="bg-indigo-600 text-white text-xs px-4 py-2 rounded-xl">Close</button>
        </div>
    </div>
</div>

<main id="chat-container" class="flex-1 overflow-y-auto p-4 space-y-4 max-w-3xl w-full mx-auto">
    <div class="flex items-start space-x-3">
        <div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0">🤖</div>
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-200 max-w-[85%] text-slate-800 text-sm leading-relaxed">
            <p>Hello! Welcome to University Course Registration.</p>
            <p class="mt-2">To get started, please log in or register:</p>
            <ul class="list-disc ml-5 mt-2 text-xs text-slate-600 space-y-1">
                <li><b>Register</b>: "My name is Riya, email is riya@uni.edu, and my field is Physics"</li>
                <li><b>Login</b>: "Log me in with email myemail@uni.edu"</li>
                <li><b>FAQs</b>: Ask questions about tuition, housing, or library hours!</li>
            </ul>
        </div>
    </div>
</main>

<footer class="bg-white border-t border-slate-200 p-4 shadow-lg">
    <form id="chat-form" class="max-w-3xl mx-auto flex gap-2">
        <input type="text" id="user-input" placeholder="Type your message here..." autocomplete="off" class="flex-1 border border-slate-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm" required>
        <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-medium text-sm">Send</button>
    </form>
</footer>

<script>
let clientSessionId = localStorage.getItem("campus_session");
if (!clientSessionId) {
    clientSessionId = 'session-' + Math.random().toString(36).substring(2);
    localStorage.setItem("campus_session", clientSessionId);
}

const chatContainer = document.getElementById("chat-container");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");

async function toggleAdminDashboard() {
    const modal = document.getElementById("admin-modal");
    modal.classList.toggle("hidden");
    
    if (!modal.classList.contains("hidden")) {
        const contentDiv = document.getElementById("admin-content");
        contentDiv.innerHTML = "<p class='animate-pulse'>Loading analytics data...</p>";
        try {
            const res = await fetch('/api/admin/analytics');
            const data = await res.json();
            const metrics = data.metrics;
            
            let logsHtml = data.recent_logs.map(l => `<div class='text-xs border-b pb-1'><b>[${l.sentiment}]</b> ID: ${l.student_id} | Intent: ${l.intent} <br><span class='text-slate-400'>\"${l.message}\"</span></div>`).join("");
            
            contentDiv.innerHTML = `
                <div class="grid grid-cols-3 gap-2 text-center">
                    <div class="bg-indigo-50 p-3 rounded-xl"><p class="text-xs text-slate-500">Students</p><p class="text-lg font-bold text-indigo-600">${metrics.total_registered_students}</p></div>
                    <div class="bg-indigo-50 p-3 rounded-xl"><p class="text-xs text-slate-500">Courses</p><p class="text-lg font-bold text-indigo-600">${metrics.total_catalog_courses}</p></div>
                    <div class="bg-indigo-50 p-3 rounded-xl"><p class="text-xs text-slate-500">Interactions</p><p class="text-lg font-bold text-indigo-600">${metrics.total_chat_interactions}</p></div>
                </div>
                <h3 class="font-semibold text-slate-700 pt-2">Recent Interactions & Sentiment:</h3>
                <div class="max-h-48 overflow-y-auto space-y-2 pr-1">${logsHtml || "<p>No interactions logged yet.</p>"}</div>
            `;
        } catch (err) {
            contentDiv.innerHTML = "<p class='text-red-500'>Failed to load admin analytics.</p>";
        }
    }
}

function escapeHTML(str) {
    return String(str).replace(/[&<>'"]/g, tag => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[tag] || tag));
}

function appendMessage(sender, text, metadata = null) {
    const isUser = sender === "user";
    const messageDiv = document.createElement("div");
    messageDiv.className = `flex items-start space-x-3 ${isUser ? "justify-end" : ""}`;

    let metaHtml = "";
    if (metadata && !isUser && metadata.intent && metadata.intent !== "general_inquiry") {
        metaHtml = `
            <div class="mt-2 text-xs text-indigo-600 bg-indigo-50 p-2 rounded border border-indigo-100">
                ⚡ Tool Action: <strong>${escapeHTML(metadata.intent)}</strong>
            </div>
        `;
    }

    if (isUser) {
        messageDiv.innerHTML = `
            <div class="bg-indigo-600 text-white p-3.5 rounded-2xl shadow-sm max-w-[85%] text-sm">${escapeHTML(text)}</div>
            <div class="bg-slate-300 text-slate-700 rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm">👤</div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm">🤖</div>
            <div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 max-w-[85%] text-sm whitespace-pre-line">
                ${escapeHTML(text)}${metaHtml}
            </div>
        `;
    }

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showLoadingIndicator() {
    const id = "loading-" + Date.now();
    const loadingDiv = document.createElement("div");
    loadingDiv.id = id;
    loadingDiv.className = "flex items-start space-x-3";
    loadingDiv.innerHTML = `
        <div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm">🤖</div>
        <div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 text-slate-400 text-sm animate-pulse">Processing request...</div>
    `;
    chatContainer.appendChild(loadingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return id;
}

function removeLoadingIndicator(id) {
    const element = document.getElementById(id);
    if (element) element.remove();
}

chatForm.addEventListener("submit", async function(event) {
    event.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage("user", text);
    userInput.value = "";
    const loadingId = showLoadingIndicator();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ student_id: clientSessionId, message: text })
        });
        const data = await response.json();
        removeLoadingIndicator(loadingId);

        if (!response.ok) {
            const errorMessage = data.detail || "The server returned an error.";
            appendMessage("bot", errorMessage);
            return;
        }

        appendMessage("bot", data.reply || "No response was generated.", {
            intent: data.intent,
            entities: data.entities
        });
    } catch (error) {
        removeLoadingIndicator(loadingId);
        appendMessage("bot", "Sorry, I could not connect to the university server.");
    }
});
</script>
</body>
</html>
"""


# ============================================================
# API ENDPOINT
# ============================================================

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        client_session_id = request.student_id or "GUEST"

        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        reply_text, detected_intent, detected_course = await process_ai_request(
            client_session_id=client_session_id,
            user_message=request.message.strip(),
        )

        return {
            "status": "success",
            "intent": detected_intent,
            "entities": {
                "course_code": detected_course,
                "semester_name": "Current Term",
            },
            "reply": reply_text,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Chat endpoint error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail="The AI service could not process your request.",
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False,
    )

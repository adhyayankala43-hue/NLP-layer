import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# LangChain & Google GenAI imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

load_dotenv()

app = FastAPI(title="University AI Assistant & NLP Orchestrator - AI-SS-001")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    google_api_key=api_key
)

# ==========================================
# 1. EXPANDED MOCK DATABASE LAYER
# ==========================================
MOCK_COURSES = {
    "CS101": {
        "title": "Intro to Computer Science", 
        "dept": "CS", 
        "credits": 3, 
        "prereqs": [], 
        "seats": 5, 
        "schedule": "MWF 09:00-10:00 AM"
    },
    "CS301": {
        "title": "Data Structures & Algorithms", 
        "dept": "CS", 
        "credits": 4, 
        "prereqs": ["CS101"], 
        "seats": 0, 
        "schedule": "TTh 11:00-12:30 PM"
    },
    "MATH101": {
        "title": "Calculus I", 
        "dept": "MATH", 
        "credits": 4, 
        "prereqs": [], 
        "seats": 8, 
        "schedule": "MWF 10:00-11:00 AM"
    },
    "MATH202": {
        "title": "Linear Algebra", 
        "dept": "MATH", 
        "credits": 3, 
        "prereqs": ["MATH101"], 
        "seats": 12, 
        "schedule": "TTh 02:00-03:30 PM"
    },
    "BIO101": {
        "title": "General Biology", 
        "dept": "BIO", 
        "credits": 4, 
        "prereqs": [], 
        "seats": 3, 
        "schedule": "MWF 09:00-10:00 AM"
    }
}

MOCK_STUDENTS = {
    "12345": {
        "name": "Alex Student",
        "completed_courses": ["CS101"],
        "enrolled_courses": ["CS101"],
        "max_credits": 18
    }
}

# ==========================================
# 2. ENHANCED DATABASE TOOLS
# ==========================================
@tool
def get_course_catalog(department: Optional[str] = None) -> str:
    """Retrieves available courses from the university catalog, optionally filtered by department (e.g. 'CS', 'MATH', 'BIO')."""
    results = []
    for code, info in MOCK_COURSES.items():
        if department and info["dept"].upper() != department.upper().strip():
            continue
        status = "OPEN" if info["seats"] > 0 else "FULL"
        results.append(
            f"• {code}: {info['title']} ({info['credits']} Credits) | "
            f"Schedule: {info['schedule']} | Status: {status} ({info['seats']} seats left) | "
            f"Prereqs: {', '.join(info['prereqs']) if info['prereqs'] else 'None'}"
        )
    if not results:
        return f"No courses found for department '{department}'."
    return "Course Catalog:\n" + "\n".join(results)

@tool
def view_student_schedule(student_id: str = "12345") -> str:
    """Views the student's current schedule, enrolled courses, total registered credit hours, and completed courses."""
    student = MOCK_STUDENTS.get(student_id, MOCK_STUDENTS["12345"])
    enrolled = student["enrolled_courses"]
    
    if not enrolled:
        return f"Student {student_id} is not currently enrolled in any courses."
        
    schedule_lines = []
    total_credits = 0
    for code in enrolled:
        course = MOCK_COURSES.get(code)
        if course:
            schedule_lines.append(f"• {code}: {course['title']} | {course['schedule']} ({course['credits']} Cr)")
            total_credits += course['credits']
            
    return (
        f"Student Schedule ({student['name']} - ID: {student_id}):\n"
        + "\n".join(schedule_lines) + "\n"
        f"Total Registered Credits: {total_credits}/{student['max_credits']} Credits.\n"
        f"Completed Prerequisites: {', '.join(student['completed_courses'])}"
    )

@tool
def check_prerequisites(student_id: str, course_code: str) -> str:
    """Checks if a student meets the prerequisite requirements for a given course code."""
    clean_code = course_code.upper().strip()
    student = MOCK_STUDENTS.get(student_id, MOCK_STUDENTS["12345"])
    course = MOCK_COURSES.get(clean_code)
    
    if not course:
        return f"Course {clean_code} not found in catalog."
        
    missing = [p for p in course["prereqs"] if p not in student["completed_courses"]]
    if missing:
        return f"Ineligible for {clean_code}. Missing required prerequisite(s): {', '.join(missing)}."
    return f"Eligible! Student satisfied all prerequisites for {clean_code}."

@tool
def check_seat_availability(course_code: str) -> str:
    """Checks remaining seat counts and waitlist availability for a specific course code."""
    clean_code = course_code.upper().strip()
    course = MOCK_COURSES.get(clean_code)
    
    if not course:
        return f"Course {clean_code} not found in catalog."
    
    seats = course["seats"]
    if seats > 0:
        return f"Course {clean_code} ({course['title']}) is OPEN with {seats} seats remaining."
    return f"Course {clean_code} ({course['title']}) is FULL (0 seats). You may request waitlisting."

@tool
def register_for_course(student_id: str, course_code: str) -> str:
    """Enrolls student after validating prerequisites, seat availability, time conflicts, and max credit limits."""
    clean_code = course_code.upper().strip()
    student = MOCK_STUDENTS.get(student_id, MOCK_STUDENTS["12345"])
    course = MOCK_COURSES.get(clean_code)
    
    if not course:
        return f"Registration error: Course {clean_code} does not exist."
    
    if clean_code in student["enrolled_courses"]:
        return f"Registration notice: You are already enrolled in {clean_code}."

    # 1. Prerequisite Validation
    missing = [p for p in course["prereqs"] if p not in student["completed_courses"]]
    if missing:
        return f"Registration failed: Missing prerequisite(s) {', '.join(missing)} for {clean_code}."
        
    # 2. Seat Availability Validation
    if course["seats"] <= 0:
        return f"Registration failed: {clean_code} is full (0 seats remaining)."

    # 3. Credit Hour Limit Check
    current_credits = sum(MOCK_COURSES[c]["credits"] for c in student["enrolled_courses"] if c in MOCK_COURSES)
    if current_credits + course["credits"] > student["max_credits"]:
        return f"Registration failed: Enrolling in {clean_code} ({course['credits']} Cr) exceeds maximum term credit limit ({student['max_credits']} Cr)."

    # 4. Schedule Time Conflict Check
    new_sched = course["schedule"]
    for enrolled_code in student["enrolled_courses"]:
        enrolled_course = MOCK_COURSES.get(enrolled_code)
        if enrolled_course and enrolled_course["schedule"] == new_sched:
            return f"Registration failed: Schedule conflict! {clean_code} ({new_sched}) overlaps with your enrolled course {enrolled_code} ({enrolled_course['schedule']})."

    # Execute Database Mutation
    course["seats"] -= 1
    student["enrolled_courses"].append(clean_code)
    return f"Success! Enrolled in {clean_code} ({course['title']}). Schedule: {course['schedule']}. Remaining seats: {course['seats']}."

@tool
def drop_course(student_id: str, course_code: str) -> str:
    """Drops/unenrolls a student from a currently registered course."""
    clean_code = course_code.upper().strip()
    student = MOCK_STUDENTS.get(student_id, MOCK_STUDENTS["12345"])
    
    if clean_code not in student["enrolled_courses"]:
        return f"Drop failed: You are not currently registered for {clean_code}."
        
    student["enrolled_courses"].remove(clean_code)
    if clean_code in MOCK_COURSES:
        MOCK_COURSES[clean_code]["seats"] += 1
        
    return f"Success! Dropped {clean_code}. Updated seat count for {clean_code}: {MOCK_COURSES[clean_code]['seats']}."

tools = [
    get_course_catalog,
    view_student_schedule,
    check_prerequisites, 
    check_seat_availability, 
    register_for_course, 
    drop_course
]

# Standard Tool Binding
tools_by_name = {t.name: t for t in tools}
llm_with_tools = llm.bind_tools(tools)

class ChatRequest(BaseModel):
    student_id: Optional[str] = "12345"
    message: str

# ==========================================
# 3. FRONTEND UI ROUTE
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>University AI Assistant - AI-SS-001</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 h-screen flex flex-col justify-between">
    <header class="bg-indigo-600 text-white shadow-md p-4 flex items-center justify-between">
        <div class="flex items-center space-x-3">
            <span class="text-2xl">🎓</span>
            <h1 class="text-lg font-semibold">CampusBot - AI Registration Assistant</h1>
        </div>
        <span class="text-xs bg-indigo-500 px-2.5 py-1 rounded-full font-medium">Online (AI-SS-001)</span>
    </header>

    <main id="chat-container" class="flex-1 overflow-y-auto p-4 space-y-4 max-w-2xl w-full mx-auto">
        <div class="flex items-start space-x-3">
            <div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">🤖</div>
            <div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 max-w-[80%] text-slate-800 text-sm leading-relaxed">
                Hello! I'm your University Assistant. You can ask me to:
                <ul class="list-disc ml-4 mt-1 text-xs text-slate-600 space-y-1">
                    <li>Show available courses (<em>"Show computer science electives"</em>)</li>
                    <li>Check my schedule (<em>"What is my current schedule?"</em>)</li>
                    <li>Verify eligibility or seats (<em>"Can I take MATH202?"</em>)</li>
                    <li>Enroll or drop classes (<em>"Enroll me in BIO101"</em>)</li>
                </ul>
            </div>
        </div>
    </main>

    <footer class="bg-white border-t border-slate-200 p-4 shadow-lg">
        <form id="chat-form" class="max-w-2xl mx-auto flex gap-2">
            <input type="text" id="user-input" placeholder="Type your query here..." autocomplete="off"
                class="flex-1 border border-slate-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm" required>
            <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-medium text-sm">Send</button>
        </form>
    </footer>

    <script>
        const chatContainer = document.getElementById('chat-container');
        const chatForm = document.getElementById('chat-form');
        const userInput = document.getElementById('user-input');

        function appendMessage(sender, text, metadata = null) {
            const isUser = sender === 'user';
            const messageDiv = document.createElement('div');
            messageDiv.className = `flex items-start space-x-3 ${isUser ? 'justify-end' : ''}`;
            
            let metaHtml = '';
            if (metadata && !isUser && metadata.intent !== 'general_inquiry') {
                metaHtml = `<div class="mt-2 text-xs text-indigo-600 bg-indigo-50 p-1.5 rounded border border-indigo-100 flex gap-2">
                    <span>⚡ Tool Action: <strong>${metadata.intent}</strong></span>
                    ${metadata.entities.course_code ? `<span>| 📚 Course: <strong>${metadata.entities.course_code}</strong></span>` : ''}
                </div>`;
            }

            if (isUser) {
                messageDiv.innerHTML = `<div class="bg-indigo-600 text-white p-3.5 rounded-2xl shadow-sm max-w-[80%] text-sm">${escapeHTML(text)}</div><div class="bg-slate-300 text-slate-700 rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">👤</div>`;
            } else {
                messageDiv.innerHTML = `<div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">🤖</div><div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 max-w-[80%] text-sm whitespace-pre-line">${escapeHTML(text)}${metaHtml}</div>`;
            }
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        function escapeHTML(str) {
            return str.replace(/[&<>'"]/g, tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag));
        }

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = userInput.value.trim();
            if (!text) return;
            appendMessage('user', text);
            userInput.value = '';
            const loadingId = showLoadingIndicator();
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ student_id: "12345", message: text })
                });
                const data = await response.json();
                removeLoadingIndicator(loadingId);
                
                appendMessage('bot', data.reply, { intent: data.intent, entities: data.entities });
            } catch (error) {
                removeLoadingIndicator(loadingId);
                appendMessage('bot', 'Sorry, I am having trouble connecting to the university server right now.');
            }
        });

        function showLoadingIndicator() {
            const id = 'loading-' + Date.now();
            const loadingDiv = document.createElement('div');
            loadingDiv.id = id;
            loadingDiv.className = 'flex items-start space-x-3';
            loadingDiv.innerHTML = `<div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">🤖</div><div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 text-slate-400 text-sm animate-pulse">Processing request against database...</div>`;
            chatContainer.appendChild(loadingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return id;
        }

        function removeLoadingIndicator(id) {
            const el = document.getElementById(id);
            if (el) el.remove();
        }
    </script>
</body>
</html>
    """

# ==========================================
# 4. API ENDPOINT
# ==========================================
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        student_id = request.student_id or "12345"
        prompt = (
            f"You are CampusBot, an official AI Course Registration Assistant. "
            f"Student ID: {student_id}. Answer the user query using tools if necessary.\n"
            f"User Query: {request.message}"
        )
        
        ai_message = await llm_with_tools.ainvoke(prompt)
        
        detected_intent = "general_inquiry"
        detected_course = None
        reply_text = ai_message.content or ""

        if hasattr(ai_message, "tool_calls") and ai_message.tool_calls:
            tool_call = ai_message.tool_calls[0]
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            detected_intent = tool_name
            detected_course = tool_args.get("course_code")
            
            if tool_name in tools_by_name:
                selected_tool = tools_by_name[tool_name]
                if "student_id" in selected_tool.args and "student_id" not in tool_args:
                    tool_args["student_id"] = student_id
                
                tool_output = selected_tool.invoke(tool_args)
                reply_text = str(tool_output)

        return {
            "status": "success",
            "intent": detected_intent,
            "entities": {
                "course_code": detected_course,
                "semester_name": "Current Term"
            },
            "reply": reply_text
        }
    except Exception as e:
        print(f"Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

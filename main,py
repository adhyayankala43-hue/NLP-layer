import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# LangChain & Google GenAI imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

app = FastAPI(title="University AI Assistant & NLP Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini LLM (using the latest flash model)
llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash", 
    temperature=0,
    google_api_key="AQ.Ab8RN6JwgaDGRZ9Wdb6LqRYk7pryC4m7e7eeONH8v4qnNVE-LQ")

# --- Define Data Models for NLP Extraction ---
class StudentQueryAnalysis(BaseModel):
    intent: str = Field(description="The core intent of the user. Options: check_prerequisites, check_seats, check_schedule, general_inquiry")
    course_code: Optional[str] = Field(default=None, description="The extracted course code if present, e.g., 'CS101', 'MATH202'")
    semester_name: Optional[str] = Field(default=None, description="The semester name if present, e.g., 'Fall 2026', 'Spring 2027'")
    response_draft: str = Field(description="A natural, helpful response addressing the student's question based on the analysis.")

orchestrator_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You are an intelligent university assistant orchestrator. "
     "Analyze the student's query, extract relevant academic entities (course codes, semesters), "
     "determine their intent, and draft a natural response."),
    ("user", "{user_message}")
])

# Structured output chain binding Pydantic schema via native json_schema
structured_llm = llm.with_structured_output(StudentQueryAnalysis, method="json_schema")
orchestrator_chain = orchestrator_prompt | structured_llm

class ChatRequest(BaseModel):
    student_id: Optional[str] = "12345"
    message: str

# --- HTML / Tailwind UI Route ---
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>University AI Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 h-screen flex flex-col justify-between">
    <header class="bg-indigo-600 text-white shadow-md p-4 flex items-center justify-between">
        <div class="flex items-center space-x-3">
            <span class="text-2xl">🎓</span>
            <h1 class="text-lg font-semibold">CampusBot - University Assistant</h1>
        </div>
        <span class="text-xs bg-indigo-500 px-2.5 py-1 rounded-full font-medium">Online</span>
    </header>

    <main id="chat-container" class="flex-1 overflow-y-auto p-4 space-y-4 max-w-2xl w-full mx-auto">
        <div class="flex items-start space-x-3">
            <div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">🤖</div>
            <div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 max-w-[80%] text-slate-800 text-sm leading-relaxed">
                Hello! I'm your University Assistant. Ask me about course prerequisites, seat availability, or your schedule! *(e.g., "Can I take CS101 this semester?")*
            </div>
        </div>
    </main>

    <footer class="bg-white border-t border-slate-200 p-4 shadow-lg">
        <form id="chat-form" class="max-w-2xl mx-auto flex gap-2">
            <input type="text" id="user-input" placeholder="Type your question here..." autocomplete="off"
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
            if (metadata && !isUser) {
                metaHtml = `<div class="mt-2 text-xs text-indigo-500 bg-indigo-50 p-1.5 rounded border border-indigo-100 flex gap-2">
                    <span>⚡ Intent: <strong>${metadata.intent}</strong></span>
                    ${metadata.entities.course_code ? `<span>| 📚 Course: <strong>${metadata.entities.course_code}</strong></span>` : ''}
                </div>`;
            }

            if (isUser) {
                messageDiv.innerHTML = `<div class="bg-indigo-600 text-white p-3.5 rounded-2xl shadow-sm max-w-[80%] text-sm">${escapeHTML(text)}</div><div class="bg-slate-300 text-slate-700 rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">👤</div>`;
            } else {
                messageDiv.innerHTML = `<div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">🤖</div><div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 max-w-[80%] text-sm">${escapeHTML(text)}${metaHtml}</div>`;
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
                
                // Pass backend NLP metadata (intent & entities) to the UI bubble
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
            loadingDiv.innerHTML = `<div class="bg-indigo-600 text-white rounded-full h-8 w-8 flex items-center justify-center flex-shrink-0 text-sm font-bold">🤖</div><div class="bg-white p-3.5 rounded-2xl shadow-sm border border-slate-200 text-slate-400 text-sm animate-pulse">Thinking...</div>`;
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

# --- API Backend Endpoint for NLP Parsing ---
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Run the NLP command chain
        analysis: StudentQueryAnalysis = orchestrator_chain.invoke({"user_message": request.message})
        
        return {
            "status": "success",
            "intent": analysis.intent,
            "entities": {
                "course_code": analysis.course_code,
                "semester_name": analysis.semester_name
            },
            "reply": analysis.response_draft
        }
    except Exception as e:
        print(f"Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

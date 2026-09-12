# 🎓 Secure AI Registration Portal

A full-stack, secure university administration and student portal built with **FastAPI**. It features an integrated LangChain-powered AI assistant capable of autonomous course registration, rigorous input validation, and real email OTP verification.

## ✨ Core Features



##### 🛡️ Security \& Authentication

* **Real Email Verification:** Integrates the Brevo API to dispatch physical 6-digit OTP codes and one-tap verification links to user inboxes.
* **Strict Input Validation:** Utilizes Pydantic v2 (Rust-based engine) to enforce rigorous Regex constraints on names, phone numbers, and course codes.
* **Session Protection:** Features a browser-native "Session Reloaded" detection overlay and secure password hashing.



##### 🎒 Student Experience

* **Autonomous AI Agent:** Integrated LangChain + Groq chat interface with tool-calling capabilities. The AI can dynamically fetch catalogs, check schedules, and execute course registrations.
* **Anti-Hallucination Guardrails:** Strict system prompts prevent the AI from inventing fake academic advisors or campus data.
* **Suggestive Chat Chips:** Quick-reply interactive UI elements to guide students on how to interact with the bot.



##### ⚙️ Admin Master Control

* **Course CRUD Operations:** Full administrative control to Add, Edit, and Delete courses.
* **Dynamic Scheduling:** Supports complex time configurations (e.g., "Mon/Wed | 10:00 AM to 11:30 AM" or "Fri | 10:00 AM onwards").
* **Visual Analytics:** Real-time Chart.js integration tracking student registrations, total logins, and major distributions.
* **Data Safety:** Thread-safe JSON file locking with cascade-delete logic (deleting a course automatically unenrolls students).



##### 🛠️ Tech Stack

* **Backend:** Python 3, FastAPI, Pydantic v2
* **AI/LLM:** LangChain, Groq API (GPT-OSS-120B / Llama)
* **Email Service:** Brevo REST API
* **Frontend:** Vanilla HTML/JS, Tailwind CSS (via CDN), Chart.js
* **Database:** Local JSON (`university\\\\\\\_data.json`)



##### 🚀 Installation \& Setup

**1. Clone the repository and navigate to the project directory.**

**2. Install dependencies:**
Ensure you have Python 3 installed, then run:
`pip install fastapi uvicorn pydantic langchain langchain-groq langchain-core`

**3. Configure API Keys:**
The application uses a Fallback Pattern for API keys. For local testing, you can place your keys directly in the `HARDCODED\\\\\\\_` variables at the top of `main.py`. For secure production environments, set the following environment variables:

* `GROQ\\\\\\\_API\\\\\\\_KEY`: Your Groq LLM API key.
* `EMAIL\\\\\\\_API\\\\\\\_KEY`: Your Brevo API key.
* `SENDER\\\\\\\_EMAIL`: The verified email address linked to your Brevo account.

**4. Run the Server:**
`python main.py`
*The application will be accessible at `http://localhost:8000`.*



###### 📖 Usage

* **Admin Access:** Use username `admin` and the password defined in `ADMIN\\\\\\\_STATIC\\\\\\\_PASSWORD` (default: `1!`) to access the Master Control dashboard.
* **Student Access:** New users must provide a valid email address and verify the OTP sent to their inbox before completing the registration form.


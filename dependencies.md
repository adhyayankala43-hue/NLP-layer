### Setup Requirements Breakdown

| Library / Module | Installation Required? | Key Functions & Classes Used |
| :--- | :--- | :--- |
| **FastAPI** (`fastapi`) | Yes (`pip install fastapi`) | `FastAPI`, `HTTPException`, `Depends`, `HTMLResponse`, `CORSMiddleware` |
| **Uvicorn** (`uvicorn`) | Yes (`pip install uvicorn`) | `uvicorn.run()` |
| **Pydantic** (`pydantic`) | Yes (`pip install pydantic`) | `BaseModel`, `Field` |
| **LangChain Core** (`langchain-core`) | Yes (`pip install langchain-core`) | `@tool`, `SystemMessage`, `HumanMessage`, `ToolMessage` |
| **LangChain Groq** (`langchain-groq`) | Yes (`pip install langchain-groq`) | `ChatGroq` |
| **OS & Typing** (`os`, `typing`) | No (Python Built-in) | `os.getenv`, `os.path.exists`, `Dict`, `List`, `Optional`, `Any` |
| **JSON** (`json`) | No (Python Built-in) | `json.load`, `json.dump`, `json.loads`, `json.dumps` |
| **Security** (`secrets`, `hashlib`) | No (Python Built-in) | `secrets.token_hex`, `secrets.compare_digest`, `hashlib.pbkdf2_hmac` |
| **Threading** (`threading`) | No (Python Built-in) | `threading.Lock()` |
| **Network** (`urllib.request`) | No (Python Built-in) | `Request()`, `urlopen()`, `HTTPError` |
| **Time Management** (`datetime`) | No (Python Built-in) | `datetime`, `timezone`, `timedelta` |
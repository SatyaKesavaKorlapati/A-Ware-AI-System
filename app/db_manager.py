import os
import json
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, Any

DB_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "database"
SESSIONS_FILE = DB_DIR / "sessions.json"

def init_db():
    if not DB_DIR.exists():
        DB_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSIONS_FILE.exists():
        with open(SESSIONS_FILE, "w") as f:
            json.dump([], f)

def get_all_sessions() -> List[dict]:
    init_db()
    with open(SESSIONS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_session(session: dict):
    init_db()
    sessions = get_all_sessions()
    
    # Check if session exists
    for i, s in enumerate(sessions):
        if s.get("id") == session.get("id"):
            sessions[i] = session
            with open(SESSIONS_FILE, "w") as f:
                json.dump(sessions, f, indent=2)
            return
            
    # New session
    sessions.append(session)
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2)

def update_session_title(session_id: str, title: str):
    init_db()
    sessions = get_all_sessions()
    for i, s in enumerate(sessions):
        if s.get("id") == session_id:
            sessions[i]["title"] = title
            with open(SESSIONS_FILE, "w") as f:
                json.dump(sessions, f, indent=2)
            return True
    return False

def delete_session(session_id: str):
    init_db()
    sessions = get_all_sessions()
    sessions = [s for s in sessions if s.get("id") != session_id]
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2)

import os
import io
import json
import base64
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We need to add the parent directory to sys.path if not running from root
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.engine import AWareEngine
from app.engine import AWareEngine
# Initialize Engine
engine = AWareEngine()

app = FastAPI(title="A-Ware API", description="Backend for the A-Ware Multimodal Logistics Assistant")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatHistoryMessage(BaseModel):
    role: str
    content: str

@app.post("/api/chat")
async def chat_endpoint(
    query: str = Form(...),
    use_yolo_only: bool = Form(False),
    allow_changes: bool = Form(False),
    history_file: Optional[UploadFile] = File(None),
    context_images_file: Optional[UploadFile] = File(None),
    files: List[UploadFile] = File(default=[])
):
    try:
        if history_file:
            content = await history_file.read()
            parsed_history = json.loads(content.decode("utf-8"))
        else:
            parsed_history = []
    except Exception as e:
        print("Failed to parse history_file", e)
        parsed_history = []

    images_to_process = []
    try:
        if context_images_file:
            content = await context_images_file.read()
            active_images_b64 = json.loads(content.decode("utf-8"))
            for b64_str in active_images_b64:
                if "," in b64_str:
                    _, data = b64_str.split(",", 1)
                else:
                    data = b64_str
                img_data = base64.b64decode(data)
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                images_to_process.append(img)
    except Exception as e:
        print(f"Failed to parse context_images_file: {e}")

    def event_stream():
        ans = ""
        meta = []
        ann = []
        
        status_map = {
            "contextualize": "Understanding chat context...",
            "supervisor": "Supervisor routing query...",
            "sql_agent": "SQL Agent querying inventory database...",
            "rag_manual_agent": "RAG Agent retrieving system manuals...",
            "rag_specs_agent": "RAG Agent retrieving system specs & research...",
            "vision_agent": "Vision Agent analyzing images with YOLO...",
            "final_synthesis": "Synthesizing final response..."
        }
        
        for node_name, state_update in engine.process_query(query, images_to_process, parsed_history, use_yolo_only, allow_changes):
            if node_name in status_map:
                yield f"data: {json.dumps({'status': status_map[node_name]})}\n\n"
                
            if node_name == "final_synthesis":
                ans = state_update.get("final_response", "")
            if "metadata" in state_update:
                meta = state_update["metadata"]
            if "annotated_images" in state_update:
                ann = state_update["annotated_images"]
                
        encoded_annotations = []
        for img_bytes in ann:
            encoded_str = base64.b64encode(img_bytes).decode("utf-8")
            encoded_annotations.append(f"data:image/jpeg;base64,{encoded_str}")
            
        yield f"data: {json.dumps({'response': ans, 'metadata': meta, 'annotated_images': encoded_annotations})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

from fastapi import Request
import app.db_manager as db

@app.get("/api/sessions")
def get_sessions():
    return db.get_all_sessions()

@app.post("/api/sessions")
async def save_session(req: Request):
    session = await req.json()
    db.save_session(session)
    return {"status": "ok"}

@app.put("/api/sessions/{session_id}/title")
async def update_title(session_id: str, req: Request):
    payload = await req.json()
    success = db.update_session_title(session_id, payload.get("title", "New Session"))
    return {"success": success}

class PinRequest(BaseModel):
    is_pinned: bool

@app.put("/api/sessions/{session_id}/pin")
def update_pin(session_id: str, req: PinRequest):
    success = db.update_session_pin(session_id, req.is_pinned)
    return {"success": success}

@app.delete("/api/sessions/{session_id}")
async def delete_session_ep(session_id: str):
    db.delete_session(session_id)
    return {"status": "ok"}

class TitleRequest(BaseModel):
    query: str

@app.post("/api/generate-title")
def generate_title(req: TitleRequest):
    try:
        from langchain_core.messages import HumanMessage
        prompt = f"Summarize this query into a concise 2-4 word Title for a chat session, and prepend a single relevant emoji. Do not use quotes or punctuation. Return ONLY the emoji and title. Query: '{req.query}'"
        msg = engine.llm.invoke([HumanMessage(content=prompt)])
        content = msg.content
        if isinstance(content, list):
            content = content[0].get("text", "New Session")
        return {"title": content.strip().replace('\"', '')}
    except Exception as e:
        print(f"Generate title error: {e}")
        return {"title": "New Session"}

from app.sql_manager import query_db, execute_db

@app.get("/api/map/layout")
def get_map_layout():
    items = query_db("SELECT * FROM inventory")
    return {"status": "success", "items": items}

class AdjustRequest(BaseModel):
    item_id: int
    action: str

@app.post("/api/map/adjust")
def adjust_map_item(req: AdjustRequest):
    if req.action == "decrement":
        execute_db("DELETE FROM inventory WHERE id = ?", (req.item_id,))
    elif req.action == "increment":
        execute_db("INSERT INTO inventory (name, category, x, y, z, rack_id, physical_aisle, shelf_level) SELECT name, category, x, y, z, rack_id, physical_aisle, shelf_level FROM inventory WHERE id = ?", (req.item_id,))
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
import os

def rewrite_engine():
    code = """from __future__ import annotations
import os
import re
import json
import base64
from io import BytesIO
from typing import Any, TypedDict, Annotated
import operator

from PIL import Image, ImageDraw
import torch
from ultralytics import YOLO

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from data.data_ingestion import ensure_database
from utils.project_paths import MODELS_DIR, ensure_local_model_dirs
from app.sql_manager import query_db, execute_db

# --- 1. GLOBAL MAPPINGS ---
CATEGORY_ALIASES = {
    "box": "box", "boxes": "box", "carton": "box", "cartons": "box",
    "crate": "crate", "crates": "crate", "rack": "rack", "racks": "rack",
    "shelf": "rack", "shelves": "rack", "bottle": "bottle", "bottles": "bottle",
    "sign": "sign", "signs": "sign", "fire extinguisher": "extinguisher",
    "extinguisher": "extinguisher", "extinguishers": "extinguisher",
    "forklift": "forklift", "forklifts": "forklift", "barrel": "barrel",
    "barel": "barrel", "barrels": "barrel", "cone": "cone", "cones": "cone",
    "pallet": "pallet", "pallets": "pallet", "fuse box": "fuse_box",
    "fuse_box": "fuse_box", "emergency board": "emergency_board",
    "paper note": "paper_note", "floor decal": "floor_decal",
    "pillar": "pillar", "pillars": "pillar", "bracket": "bracket",
    "brackets": "bracket", "lamp": "lamp", "lamps": "lamp",
    "wire": "wire", "wires": "wire", "cart": "cart", "carts": "cart",
    "bucket": "bucket", "buckets": "bucket", "barcode": "barcode",
    "barcodes": "barcode", "floor": "floor",
}

YOLO_TO_METADATA_CATEGORY = {
    "pillar": "pillar", "bracket": "bracket", "lamp": "lamp",
    "paper_shortcut": "paper_shortcut", "sign": "sign", "wire": "wire",
    "box": "box", "floor_decal": "floor", "paper_note": "paper_shortcut",
    "pallet": "pallet", "crate": "crate", "barel": "barrel", "barrel": "barrel", 
    "fuse_box": "fuse_box", "fire_extinguisher": "extinguisher", "forklift": "forklift",
    "bucket": "bucket", "barcode": "barcode", "bottle": "bottle",
    "cart": "cart", "cone": "cone", "emergency_board": "emergency_board",
}

def reducer_list(a: list, b: list) -> list:
    return a + b if b else a

def reducer_string(a: str, b: str) -> str:
    return b if b else a

class AgentState(TypedDict):
    current_query: str
    images: list[Any]
    history: list[dict]
    target_categories: list[str]
    vision_info: Annotated[str, reducer_string]
    sql_info: Annotated[str, reducer_string]
    rag_info: Annotated[str, reducer_string]
    annotated_images: Annotated[list[bytes], reducer_list]
    metadata: Annotated[list[dict], reducer_list]
    final_response: Annotated[str, reducer_string]
    use_yolo_only: bool
    allow_changes: bool
    next_nodes: list[str]

def _image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

class AWereEngine:
    def __init__(self):
        print("🧠 Initializing A-Ware Cognitive Engine (Multi-Agent Architecture)...")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
        
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
        
        print("📁 Loading RAG Collection...")
        self.collection = ensure_database(populate_if_missing=True)
        
        self._load_yolo()
        self.graph = self._build_graph()
        print("✅ Engine Ready.")

    def _load_yolo(self):
        model_paths = ensure_local_model_dirs()
        weights_path = model_paths["yolo"]
        
        if not weights_path:
            raise FileNotFoundError(f"YOLO weights not found in {MODELS_DIR}")

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.yolo = YOLO(str(weights_path)).to(device)

    def _draw_boxes(self, image: Image.Image, detections: list[dict]) -> Image.Image:
        canvas = image.copy()
        draw = ImageDraw.Draw(canvas)
        for det in detections:
            x1, y1, x2, y2 = det["box"]
            cls_name = det["class_name"]
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1, y1), cls_name, fill="red")
        return canvas

    def _extract_categories(self, query: str) -> list[str]:
        words = re.findall(r'\w+', query.lower())
        found = set()
        for w in words:
            if w in CATEGORY_ALIASES:
                found.add(CATEGORY_ALIASES[w])
        return list(found)

    def node_supervisor(self, state: AgentState) -> dict:
        query = state["current_query"]
        
        sys_prompt = '''You are the Router. Decide which agents should process this query.
        Available Agents:
        - vision_agent: Route here if the user uploaded images and asks about what is in the images.
        - sql_agent: Route here if the user asks about warehouse inventory, counting items, finding items (like 'where are the boxes?', 'how many pallets?'), or moving/updating items.
        - rag_agent: Route here if the user asks about the warehouse system manuals, who owns it, what tech it uses, location, or general system questions.

        If a query requires multiple agents (e.g. "who owns the warehouse and how many boxes are there?"), route to BOTH 'sql_agent' and 'rag_agent'.
        Always route to 'vision_agent' if the user uploaded images.
        Respond ONLY with a JSON list of strings, like ["sql_agent", "rag_agent"]. Do NOT output markdown formatting like ```json.
        '''
        
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"Query: {query}\\nImages uploaded: {bool(state['images'])}")
        ]
        
        response = self.llm.invoke(messages).content.strip()
        # Clean markdown if present
        if response.startswith("```"):
            response = response.split("\\n", 1)[1]
            response = response.rsplit("\\n", 1)[0]
        
        try:
            next_nodes = json.loads(response)
        except:
            next_nodes = ["sql_agent"] # fallback
            
        if not isinstance(next_nodes, list) or len(next_nodes) == 0:
            next_nodes = ["sql_agent"]
            
        return {"next_nodes": next_nodes}

    def node_vision_agent(self, state: AgentState) -> dict:
        query = state["current_query"]
        images = state["images"]
        target_cats = self._extract_categories(query)
        
        vision_infos = []
        annotated_images = []
        metadata = []
        
        if images:
            for idx, img in enumerate(images):
                pil_image = img.convert("RGB")
                results = self.yolo(pil_image, verbose=False)[0]
                
                hl_det = []
                counts = Counter()
                for box in results.boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = results.names[cls_id]
                    mapped_cat = YOLO_TO_METADATA_CATEGORY.get(cls_name, cls_name)
                    
                    if not target_cats or mapped_cat in target_cats:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        hl_det.append({
                            "class_name": mapped_cat,
                            "box": [x1, y1, x2, y2]
                        })
                        counts[mapped_cat] += 1
                        
                info = ", ".join([f"{count} {cat}" for cat, count in counts.items()])
                if not info: info = "No objects detected."
                vision_infos.append(f"[Image {idx + 1}]: {info}")
                
                canvas = self._draw_boxes(pil_image, hl_det)
                annotated_images.append(_image_to_png_bytes(canvas))
                metadata.append({"vision_highlighted": list(counts.keys())})
        
        v_info = "\\n".join(vision_infos) if vision_infos else "No images provided."
        return {"vision_info": v_info, "annotated_images": annotated_images, "metadata": metadata, "target_categories": target_cats}

    def node_sql_agent(self, state: AgentState) -> dict:
        query = state["current_query"]
        allow_changes = state["allow_changes"]
        
        sys_prompt = f'''You are the SQL Inventory Agent. You have access to a SQLite database 'inventory'.
        Schema: inventory(id, prim_path, name, category, x, y, z, rack_id, physical_aisle, shelf_level, last_updated)
        
        Safety rule: allow_changes={allow_changes}.
        If False, you MUST ONLY generate SELECT queries. If the user asks to modify/delete/insert, you must refuse and say "Modification denied: safety toggle is OFF."
        If True, you may generate INSERT/UPDATE/DELETE queries.
        
        You MUST output your response in the following strict JSON format:
        {{
            "sql_query": "SELECT count(*) FROM inventory WHERE category = 'box';"
        }}
        Do NOT wrap it in markdown. Do NOT explain. If you refuse, output:
        {{ "sql_query": "REFUSE: Safety toggle is OFF." }}
        '''
        
        response = self.llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=query)]).content.strip()
        if response.startswith("```"):
            response = response.split("\\n", 1)[1]
            response = response.rsplit("\\n", 1)[0]
            
        sql_info = ""
        try:
            data = json.loads(response)
            sql_query = data.get("sql_query", "")
            
            if sql_query.startswith("REFUSE"):
                sql_info = sql_query
            elif sql_query.strip().upper().startswith("SELECT"):
                res = query_db(sql_query)
                sql_info = f"Query: {sql_query}\\nResult: {res}"
            else:
                if not allow_changes:
                    sql_info = "Modification denied: safety toggle is OFF."
                else:
                    res = execute_db(sql_query)
                    sql_info = f"Query: {sql_query}\\nResult: {res}"
        except Exception as e:
            sql_info = f"Error interpreting SQL agent JSON: {e} - Raw: {response}"
            
        return {"sql_info": sql_info}

    def node_rag_agent(self, state: AgentState) -> dict:
        q = state["current_query"]
        res = self.collection.query(query_texts=[q], n_results=3)
        rag_docs = "\\n".join(res.get("documents", [[]])[0])
        return {"rag_info": rag_docs}

    def node_final_synthesis(self, state: AgentState) -> dict:
        sys_inst = (
            "You are A-Ware, a helpful Warehouse Logistics AI.\\n"
            "You MUST think step-by-step and wrap your internal reasoning inside <thinking>...</thinking> tags at the very beginning of your response.\\n"
            "Write a natural, conversational response.\\n"
            "You will be given raw output from various sub-agents (Vision, SQL, RAG). Synthesize them into a clear answer."
        )

        prompt_text = (
            f"User Query: {state['current_query']}\\n\\n"
            f"--- Agent Data ---\\n"
            f"SQL Inventory Agent:\\n{state.get('sql_info', 'Not called')}\\n\\n"
            f"RAG Knowledge Agent:\\n{state.get('rag_info', 'Not called')}\\n\\n"
            f"Vision Agent:\\n{state.get('vision_info', 'Not called')}\\n\\n"
            "Synthesize this information into a response. If the SQL agent refused to modify, politely inform the user to turn on the 'Allow Changes' toggle."
        )
        
        messages = [SystemMessage(content=sys_inst)]
        
        # History
        if state["history"]:
            for msg in state["history"][-4:]:
                messages.append(AIMessage(content=msg["content"]) if msg["role"] == "assistant" else HumanMessage(content=msg["content"]))
                
        messages.append(HumanMessage(content=prompt_text))

        response = self.llm.invoke(messages).content
        return {"final_response": response}

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)
        
        builder.add_node("supervisor", self.node_supervisor)
        builder.add_node("sql_agent", self.node_sql_agent)
        builder.add_node("rag_agent", self.node_rag_agent)
        builder.add_node("vision_agent", self.node_vision_agent)
        builder.add_node("final_synthesis", self.node_final_synthesis)
        
        builder.add_edge(START, "supervisor")
        
        def route(state: AgentState):
            # next_nodes contains the list of parallel nodes
            nodes = state["next_nodes"]
            # To ensure final_synthesis runs after, we just return the parallel nodes.
            # LangGraph handles fan-out.
            return nodes
            
        builder.add_conditional_edges("supervisor", route, ["sql_agent", "rag_agent", "vision_agent"])
        
        # Fan-in
        builder.add_edge("sql_agent", "final_synthesis")
        builder.add_edge("rag_agent", "final_synthesis")
        builder.add_edge("vision_agent", "final_synthesis")
        builder.add_edge("final_synthesis", END)
        
        return builder.compile()

    def process_query(self, query: str, images: list[Image.Image], history: list[dict], use_yolo_only: bool = False, allow_changes: bool = False):
        initial_state = {
            "current_query": query,
            "images": images,
            "history": history,
            "target_categories": [],
            "vision_info": "",
            "sql_info": "",
            "rag_info": "",
            "annotated_images": [],
            "metadata": [],
            "final_response": "",
            "use_yolo_only": use_yolo_only,
            "allow_changes": allow_changes,
            "next_nodes": []
        }
        
        for event in self.graph.stream(initial_state):
            for key, value in event.items():
                yield key, value
"""
    with open("app/engine.py", "w", encoding="utf-8") as f:
        f.write(code)

if __name__ == "__main__":
    rewrite_engine()
    print("app/engine.py rewritten successfully.")

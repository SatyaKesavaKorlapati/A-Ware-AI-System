from __future__ import annotations
import os
import re
import json
import base64
from io import BytesIO
from typing import Any, TypedDict, Annotated
import operator
from collections import Counter

from PIL import Image, ImageDraw
import torch
from ultralytics import YOLO

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from data.data_ingestion import ensure_databases
from utils.project_paths import MODELS_DIR, ensure_local_model_dirs
from app.sql_manager import query_db, execute_db

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


from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

@tool
def calculate(expression: str) -> str:
    """Evaluates a mathematical expression (e.g., '10 + 5 * 2'). Do not use this for SQL database operations."""
    try:
        return str(eval(expression, {"__builtins__": None}, {}))
    except Exception as e:
        return f"Error evaluating math: {e}"

@tool
def get_current_time() -> str:
    """Returns the current local date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def search_wikipedia(query: str) -> str:
    """Searches Wikipedia for general knowledge information."""
    import wikipediaapi
    try:
        wiki = wikipediaapi.Wikipedia('A-Ware Assistant (support@example.com)', 'en')
        page = wiki.page(query)
        if not page.exists():
            return "No information found on Wikipedia."
        return page.summary[0:1500]
    except Exception as e:
        return f"Could not find information on Wikipedia: {e}"

@tool
def web_search(query: str) -> str:
    """Searches the web for current events, news, or facts."""
    from googlesearch import search
    try:
        results = search(query, num_results=3, advanced=True)
        out = []
        for r in results:
            out.append(f"{r.title}: {r.description}")
        if not out:
            return "No results found on the web."
        return "\n".join(out)
    except Exception as e:
        return f"Web search failed: {e}"

TOOLS = [calculate, get_current_time, search_wikipedia, web_search]

def reducer_list(a: list, b: list) -> list:
    return a + b if b else a

def reducer_string(a: str, b: str) -> str:
    return b if b else a

class AgentState(TypedDict):
    current_query: str
    standalone_query: str
    images: list[Any]
    history: list[dict]
    target_categories: list[str]
    vision_info: Annotated[str, reducer_string]
    sql_info: Annotated[str, reducer_string]
    rag_manual_info: Annotated[str, reducer_string]
    rag_specs_info: Annotated[str, reducer_string]
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

class AWareEngine:
    def __init__(self):
        print("🧠 Initializing A-Ware Cognitive Engine (Agentic RAG)...")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
        
        self.llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)
        
        print("📁 Loading RAG Collections...")
        dbs = ensure_databases(populate_if_missing=True)
        self.collection_manuals = dbs["manuals"]
        self.collection_specs = dbs["specs"]
        
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

    def _extract_text(self, content) -> str:
        if isinstance(content, list):
            return content[0].get("text", "")
        return str(content)

    def _extract_categories(self, query: str) -> list[str]:
        words = re.findall(r'\w+', query.lower())
        found = set()
        for w in words:
            if w in CATEGORY_ALIASES:
                found.add(CATEGORY_ALIASES[w])
        return list(found)

    def node_contextualize(self, state: AgentState) -> dict:
        query = state["current_query"]
        history = state["history"]
        if not history:
            return {"standalone_query": query}
            
        sys_prompt = "You are an AI tasked with contextualizing a follow-up query. Given the chat history and the latest user query, rewrite the user query so it is a standalone, self-contained question that includes all necessary context (e.g. subjects, items). Do NOT answer the query, just return the standalone query."
        
        msgs = [SystemMessage(content=sys_prompt)]
        for msg in history[-4:]:
            msgs.append(AIMessage(content=msg["content"]) if msg["role"] == "assistant" else HumanMessage(content=msg["content"]))
        msgs.append(HumanMessage(content=query))
        
        res = self._extract_text(self.llm.invoke(msgs).content).strip()
        return {"standalone_query": res}

    def node_supervisor(self, state: AgentState) -> dict:
        query = state["standalone_query"]
        
        sys_prompt = '''You are the Agentic RAG Supervisor. Route the query to the correct specialized agents.
        Available Agents:
        - vision_agent: Route here if the user uploaded images and asks about what is in the images.
        - sql_agent: Route here if the user asks about warehouse inventory, counting items, finding items, breakdowns, physical locations, or moving items.
        - rag_manual_agent: Route here if the user asks about operational system manuals, location, owner, or capabilities.
        - rag_specs_agent: Route here if the user asks about YOLO training metrics, precision, recall, synthetic dataset generation, VLM architecture, system specs, authors, README, or research reports.

        If a query requires multiple agents, route to ALL of them.
        Always route to 'vision_agent' if the user uploaded images.
        Respond ONLY with a JSON list of strings, like ["sql_agent", "rag_specs_agent"]. Do NOT output markdown formatting like ```json.
        '''
        
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"Query: {query}\nImages uploaded: {bool(state['images'])}")
        ]
        
        response = self._extract_text(self.llm.invoke(messages).content).strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            response = response.rsplit("\n", 1)[0]
        
        try:
            next_nodes = json.loads(response)
        except:
            next_nodes = ["sql_agent"]
            
        if not isinstance(next_nodes, list) or len(next_nodes) == 0:
            next_nodes = ["sql_agent"]
            
        return {"next_nodes": next_nodes}

    def node_vision_agent(self, state: AgentState) -> dict:
        query = state["standalone_query"]
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
        
        v_info = "\n".join(vision_infos) if vision_infos else "No images provided."
        return {"vision_info": v_info, "annotated_images": annotated_images, "metadata": metadata, "target_categories": target_cats}

    def node_sql_agent(self, state: AgentState) -> dict:
        query = state["standalone_query"]
        allow_changes = state["allow_changes"]
        
        from app.sql_skills import create_sql_tools
        sql_tools = create_sql_tools(allow_changes)
        
        sys_prompt = '''You are the SQL Inventory Agent. You have access to explicit warehouse skills.
        DO NOT generate raw SQL. Use your explicit tools (`get_inventory`, `add_inventory`, `remove_inventory`, `move_inventory`) to interact with the database safely.
        Answer the user's query exactly. If you need to make modifications and the tools return REFUSED because safety toggle is OFF, explicitly inform the user they must enable the 'Database Modifying Mode'.
        Always query for inventory before taking actions if you are unsure of the current state.
        '''
        
        try:
            agent = create_react_agent(self.llm, sql_tools)
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=query)
            ]
            result = agent.invoke({"messages": messages})
            sql_info = self._extract_text(result["messages"][-1].content)
        except Exception as e:
            sql_info = f"Error interpreting SQL agent: {e}"
            
        return {"sql_info": sql_info}

    def node_rag_manual_agent(self, state: AgentState) -> dict:
        q = state["standalone_query"]
        res = self.collection_manuals.query(query_texts=[q], n_results=3)
        rag_docs = "\n".join(res.get("documents", [[]])[0])
        return {"rag_manual_info": rag_docs}

    def node_rag_specs_agent(self, state: AgentState) -> dict:
        q = state["standalone_query"]
        res = self.collection_specs.query(query_texts=[q], n_results=3)
        rag_docs = "\n".join(res.get("documents", [[]])[0])
        return {"rag_specs_info": rag_docs}

    def node_final_synthesis(self, state: AgentState) -> dict:
        sys_inst = (
            "You are A-Ware, a helpful Warehouse Logistics AI.\n"
            "You MUST think step-by-step and wrap your internal reasoning inside <thinking>...</thinking> tags at the very beginning of your final response. THIS IS MANDATORY for every single response.\n"
            "Write a natural, conversational response.\n"
            "You will be given raw output from various specialized sub-agents. Synthesize them into a clear answer.\n"
            "CRITICAL: If the SQL Inventory Agent states that modifications are denied because the safety toggle is OFF, you MUST explicitly tell the user that they need to enable the 'Database Modifying Mode' toggle in the UI. DO NOT pretend that the items were added or deleted.\n"
            "CRITICAL: If the provided Agent Data does not contain the answer (e.g., for general knowledge, current events, or real-world facts), you MUST use your web_search or search_wikipedia tools to find the answer before responding!"
        )

        prompt_text = (
            f"User Original Query: {state['current_query']}\n"
            f"Contextualized Query: {state['standalone_query']}\n\n"
            f"--- Agent Data ---\n"
            f"SQL Inventory Agent:\n{state.get('sql_info', 'Not called')}\n\n"
            f"RAG Manual Agent:\n{state.get('rag_manual_info', 'Not called')}\n\n"
            f"RAG Specs & Research Agent:\n{state.get('rag_specs_info', 'Not called')}\n\n"
            f"Vision Agent:\n{state.get('vision_info', 'Not called')}\n\n"
            "Synthesize this information into a response."
        )
        
        messages = [SystemMessage(content=sys_inst)]
        
        if state["history"]:
            for msg in state["history"][-4:]:
                messages.append(AIMessage(content=msg["content"]) if msg["role"] == "assistant" else HumanMessage(content=msg["content"]))
                
        messages.append(HumanMessage(content=prompt_text))

        try:
            agent = create_react_agent(self.llm, TOOLS)
            result = agent.invoke({"messages": messages})
            response = self._extract_text(result["messages"][-1].content)
        except Exception as e:
            response = f"I encountered an error trying to process the final response: {str(e)}"
        return {"final_response": response}

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)
        
        builder.add_node("contextualize", self.node_contextualize)
        builder.add_node("supervisor", self.node_supervisor)
        builder.add_node("sql_agent", self.node_sql_agent)
        builder.add_node("rag_manual_agent", self.node_rag_manual_agent)
        builder.add_node("rag_specs_agent", self.node_rag_specs_agent)
        builder.add_node("vision_agent", self.node_vision_agent)
        builder.add_node("final_synthesis", self.node_final_synthesis)
        
        builder.add_edge(START, "contextualize")
        builder.add_edge("contextualize", "supervisor")
        
        def route(state: AgentState):
            return state["next_nodes"]
            
        builder.add_conditional_edges("supervisor", route, ["sql_agent", "rag_manual_agent", "rag_specs_agent", "vision_agent"])
        
        builder.add_edge("sql_agent", "final_synthesis")
        builder.add_edge("rag_manual_agent", "final_synthesis")
        builder.add_edge("rag_specs_agent", "final_synthesis")
        builder.add_edge("vision_agent", "final_synthesis")
        builder.add_edge("final_synthesis", END)
        
        return builder.compile()

    def process_query(self, query: str, images: list[Image.Image], history: list[dict], use_yolo_only: bool = False, allow_changes: bool = False):
        initial_state = {
            "current_query": query,
            "standalone_query": "",
            "images": images,
            "history": history,
            "target_categories": [],
            "vision_info": "",
            "sql_info": "",
            "rag_manual_info": "",
            "rag_specs_info": "",
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

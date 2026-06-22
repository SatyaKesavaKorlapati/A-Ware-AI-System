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

from app.general_skills import GENERAL_TOOLS
TOOLS = GENERAL_TOOLS

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
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        sys_prompt = f"You are an AI tasked with contextualizing a follow-up query. The current date is {current_date}. Given the chat history and the latest user query, rewrite the user query so it is a standalone, self-contained question that includes all necessary context (e.g. subjects, items). Do NOT answer the query, just return the standalone query."
        
        msgs = [SystemMessage(content=sys_prompt)]
        for msg in history[-4:]:
            msgs.append(AIMessage(content=msg["content"]) if msg["role"] == "assistant" else HumanMessage(content=msg["content"]))
        msgs.append(HumanMessage(content=query))
        
        res = self._extract_text(self.llm.invoke(msgs).content).strip()
        return {"standalone_query": res}

    def node_supervisor(self, state: AgentState) -> dict:
        query = state["standalone_query"]
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        sys_prompt = f'''You are the Agentic RAG Supervisor. The current date is {current_date}. Route the query to the correct specialized agents.
        Available Agents:
        - vision_agent: Route here if the user uploaded images and asks about what is in the images.
        - sql_agent: Route here if the user asks about warehouse inventory, counting items, finding items, breakdowns, physical locations, or moving items. CRITICAL: Any query asking "how many", "count", "do we have", or mentioning warehouse items (like forklifts, helmets), OR using action verbs like "add", "remove", "move", "rename", OR mentioning a "Rack" MUST route here.
        - rag_manual_agent: Route here if the user asks about operational system manuals, location, owner, or capabilities.
        - rag_specs_agent: Route here if the user asks about YOLO training metrics, precision, recall, synthetic dataset generation, VLM architecture, system specs, authors, README, or research reports.

        If a query requires multiple agents, route to ALL of them.
        Always route to 'vision_agent' if the user uploaded images.
        If the query is a purely general knowledge question (e.g. "who is the president", "how are you", "what is the capital of") and does NOT relate to the warehouse, inventory, or items, return an EMPTY list: []. Do NOT return [] if the user is asking about our inventory or equipment.
        Respond ONLY with a JSON list of strings, like ["sql_agent", "rag_specs_agent"] or []. Do NOT output markdown formatting like ```json.
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
            if not isinstance(next_nodes, list):
                next_nodes = []
        except:
            next_nodes = []
            
        # Ensure final_synthesis is always called
        if len(next_nodes) == 0:
            next_nodes = ["final_synthesis"]
            
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
                try:
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
                except Exception as e:
                    vision_infos.append(f"[Image {idx + 1}]: Error processing image: {str(e)}")
                    print(f"YOLO vision processing error: {e}")
        
        v_info = "\n".join(vision_infos) if vision_infos else "No images provided."
        return {"vision_info": v_info, "annotated_images": annotated_images, "metadata": metadata, "target_categories": target_cats}

    def node_sql_agent(self, state: AgentState) -> dict:
        query = state["standalone_query"]
        allow_changes = state["allow_changes"]
        
        from app.sql_skills import create_sql_tools
        sql_tools = create_sql_tools(allow_changes) + TOOLS
        
        sys_prompt = '''You are the SQL Inventory Agent. You have access to explicit warehouse skills and general tools like web search.
        DO NOT generate raw SQL. Use your explicit tools (`get_inventory`, `add_inventory`, `remove_inventory`, `move_inventory`, `rename_inventory`) to interact with the database safely.
        If you need to search the web to find constraints (e.g. brand names, versions), use the web_search tool FIRST, and THEN use the inventory tools.
        Answer the user's query exactly. If you need to make modifications and the tools return an error or item not found, explain the exact error.
        If a tool returns an error starting with "REFUSED:", quote the exact error message to the user. Do NOT mention "Database Modifying Mode" unless it is literally in the tool's error message.
        Always query for inventory before taking actions if you are unsure of the current state.
        If the user's query is NOT related to warehouse inventory, items, or SQL, simply reply "IDK" so you do not hallucinate unrelated facts.
        '''
        
        try:
            agent = create_react_agent(self.llm, sql_tools)
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=query)
            ]
            result = agent.invoke({"messages": messages})
            
            output_msgs = result["messages"][len(messages):]
            thinking_steps = []
            final_text = ""
            for msg in output_msgs:
                if msg.__class__.__name__ == "AIMessage":
                    content_str = self._extract_text(msg.content) if msg.content else ""
                    if content_str and getattr(msg, 'tool_calls', None):
                        thinking_steps.append(content_str)
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            args_str = str(tc.get('args', {}))
                            thinking_steps.append(f"Using tool **{tc['name']}** with args: `{args_str}`")
                    if not getattr(msg, 'tool_calls', None) and content_str:
                        final_text = content_str
                elif msg.__class__.__name__ == "ToolMessage":
                    content_str = str(msg.content)[:500]
                    thinking_steps.append(f"Tool Result ({msg.name}):\n```\n{content_str}\n```")

            sql_info = ""
            if thinking_steps:
                sql_info += "SQL AGENT THINKING:\n" + "\n".join(thinking_steps) + "\n\n"
            sql_info += final_text or self._extract_text(result["messages"][-1].content)
            
        except Exception as e:
            sql_info = f"Error interpreting SQL agent: {e}"
            
        return {"sql_info": sql_info}

    def node_rag_manual_agent(self, state: AgentState) -> dict:
        q = state["standalone_query"]
        try:
            res = self.collection_manuals.query(query_texts=[q], n_results=3)
            rag_docs = "\n".join(res.get("documents", [[]])[0])
        except Exception as e:
            print(f"RAG manual query error: {e}")
            rag_docs = "Error retrieving manual documents."
        return {"rag_manual_info": rag_docs}

    def node_rag_specs_agent(self, state: AgentState) -> dict:
        q = state["standalone_query"]
        try:
            res = self.collection_specs.query(query_texts=[q], n_results=3)
            rag_docs = "\n".join(res.get("documents", [[]])[0])
        except Exception as e:
            print(f"RAG specs query error: {e}")
            rag_docs = "Error retrieving specs documents."
        return {"rag_specs_info": rag_docs}

    def node_final_synthesis(self, state: AgentState) -> dict:
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        sys_inst = (
            f"You are A-Ware, a helpful Warehouse Logistics AI. The current date is {current_date}.\n"
            "Write a natural, conversational response.\n"
            "You will be given raw output from various specialized sub-agents. Synthesize them into a clear answer.\n"
            "CRITICAL: Explain exactly what failed if an agent reports a failure (e.g. 'Item not found'). If a tool or agent returns an error starting with 'REFUSED:', quote the exact error message to the user. Do NOT hallucinate the phrase 'Database Modifying Mode' as an excuse for general errors or unavailable items.\n"
            "CRITICAL: If the provided Agent Data does not contain the complete answer, or an agent failed because it lacked context (e.g., SQL agent needed Vision data to run an update), you MUST use your tools to finish the task (e.g. using sql tools to make database changes based on vision_info)!\n"
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
            "Synthesize this information into a response. If the SQL Inventory Agent failed to make an inventory update due to missing information (e.g., missing count from Vision Agent), you must use your SQL tools to complete the inventory update now."
        )
        
        messages = [SystemMessage(content=sys_inst)]
        
        if state["history"]:
            for msg in state["history"][-4:]:
                messages.append(AIMessage(content=msg["content"]) if msg["role"] == "assistant" else HumanMessage(content=msg["content"]))
                
        messages.append(HumanMessage(content=prompt_text))

        try:
            from app.sql_skills import create_sql_tools
            final_tools = create_sql_tools(state["allow_changes"]) + TOOLS
            agent = create_react_agent(self.llm, final_tools)
            result = agent.invoke({"messages": messages})
            
            output_msgs = result["messages"][len(messages):]
            thinking_steps = []
            final_text = ""
            
            for msg in output_msgs:
                if msg.__class__.__name__ == "AIMessage":
                    content_str = self._extract_text(msg.content) if msg.content else ""
                    if content_str and getattr(msg, 'tool_calls', None):
                        thinking_steps.append(content_str)
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            args_str = str(tc.get('args', {}))
                            thinking_steps.append(f"Using tool **{tc['name']}** with args: `{args_str}`")
                    if not getattr(msg, 'tool_calls', None) and content_str:
                        final_text = content_str
                elif msg.__class__.__name__ == "ToolMessage":
                    content_str = str(msg.content)[:500] + ("..." if len(str(msg.content)) > 500 else "")
                    thinking_steps.append(f"Tool Result ({msg.name}):\n```\n{content_str}\n```")

            if thinking_steps:
                thinking_block = "<thinking>\n" + "\n\n".join(thinking_steps) + "\n</thinking>\n\n"
            else:
                thinking_block = ""
                
            if thinking_block and "<thinking>" not in final_text:
                response = thinking_block + final_text
            else:
                response = final_text or self._extract_text(result["messages"][-1].content)
                
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
            
        builder.add_conditional_edges("supervisor", route, ["sql_agent", "rag_manual_agent", "rag_specs_agent", "vision_agent", "final_synthesis"])
        
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

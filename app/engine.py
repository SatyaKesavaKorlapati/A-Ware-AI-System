from __future__ import annotations
import os
import re
import hashlib
import json
import base64
from collections import Counter
from io import BytesIO
from typing import Any, TypedDict

from PIL import Image, ImageDraw
import torch
from ultralytics import YOLO

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from data.data_ingestion import ensure_database, load_metadata
from utils.project_paths import MODELS_DIR, ensure_local_model_dirs

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

DISPLAY_LABELS = {
    "barel": "barrel", "fire_extinguisher": "fire extinguisher",
    "floor_decal": "floor decal", "paper_note": "paper note",
    "paper_shortcut": "paper shortcut", "fuse_box": "fuse box",
    "emergency_board": "emergency board",
}

CLASS_COLORS = {
    "pillar": "#d64550", "bracket": "#ef7d57", "lamp": "#f4a259",
    "paper_shortcut": "#ffd166", "sign": "#06d6a0", "wire": "#2ec4b6",
    "box": "#118ab2", "floor_decal": "#83c5be", "paper_note": "#ffca3a",
    "pallet": "#8d99ae", "crate": "#3a86ff", "barel": "#e63946",
    "fuse_box": "#9b5de5", "fire_extinguisher": "#f94144",
    "forklift": "#ff6b6b", "bucket": "#43aa8b", "barcode": "#577590",
    "bottle": "#4cc9f0", "cart": "#4361ee", "cone": "#f8961e",
    "emergency_board": "#f72585",
}

FALLBACK_COLORS = ["#ff595e", "#ff924c", "#ffca3a", "#8ac926", "#52b788", "#1982c4", "#4267ac", "#6a4c93", "#f15bb5", "#00bbf9"]

# --- 2. UTILITY FUNCTIONS ---
def _display_name(label: str) -> str:
    return DISPLAY_LABELS.get(label, label).replace("_", " ")

def _color_for_label(label: str) -> str:
    if label in CLASS_COLORS: return CLASS_COLORS[label]
    digest = hashlib.md5(label.encode("utf-8")).hexdigest()
    return FALLBACK_COLORS[int(digest, 16) % len(FALLBACK_COLORS)]

def _image_to_png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. LANGGRAPH STATE DEFINITION ---
class AgentState(TypedDict):
    history: list[dict]
    current_query: str
    images: list[Image.Image]
    target_categories: list[str]
    vision_info: str
    spatial_context: str
    rag_docs: str
    annotated_images: list[bytes]
    metadata: list[dict]
    final_response: str
    use_yolo_only: bool

# --- 4. WAREHOUSE AI ENGINE (LangChain / LangGraph) ---
class WarehouseAI:
    def __init__(self):
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        
        print("🧠 Initializing A-Ware Cognitive Engine (LangGraph Architecture)...")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing.")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite",
            temperature=0.1,
            api_key=api_key
        )

        print("📁 Loading Hierarchical Facts...")
        self.collection = ensure_database(populate_if_missing=True)
        self.facts = self._load_verified_summaries()
        
        self.yolo_model_path = str(MODELS_DIR / "lar1r.pt")
        self.detector = None
        
        self.graph = self._build_graph()
        print("✅ Backend Ready.")

    def _load_verified_summaries(self) -> dict[str, Any]:
        meta = self.collection.metadata
        return {
            "global": json.loads(meta.get("global_summary", "{}")),
            "aisle": json.loads(meta.get("aisle_summary", "{}")),
            "rack": json.loads(meta.get("rack_summary", "{}")),
            "shelf": json.loads(meta.get("shelf_summary", "{}")),
            "total": meta.get("total_items", 0)
        }

    def _get_detector(self):
        if self.detector is None:
            self.detector = YOLO(self.yolo_model_path)
        return self.detector

    def _get_target_categories(self, current_query: str, history: list[dict]) -> list[str]:
        query_lower = current_query.lower()
        
        current_targets = set()
        for alias, canonical in CATEGORY_ALIASES.items():
            if re.search(rf"\b{alias}\b", query_lower):
                current_targets.add(canonical)

        accumulative_keywords = [r"along with", r"\bprev", r"\bprevious", r"\bkeep", r"\badd\b", r"\balso\b"]
        is_accumulative = any(re.search(kw, query_lower) for kw in accumulative_keywords)

        if is_accumulative and history:
            for msg in reversed(history):
                if msg["role"] == "user":
                    last_query_lower = msg["content"].lower()
                    for alias, canonical in CATEGORY_ALIASES.items():
                        if re.search(rf"\b{alias}\b", last_query_lower):
                            current_targets.add(canonical)
                    break 

        if not current_targets:
            if re.search(r"\b(all|every|everything|what|describe|summary|overall|any)\b", query_lower):
                return ["__ALL__"]
            return []

        return list(current_targets)

    def _get_spatial_context(self, query: str, cats: list[str]) -> str:
        q = query.lower()
        aisle = re.search(r"\baisle\s*(\d+)\b", q)
        rack = re.search(r"\brack\s*(\d+)\b", q)
        shelf = re.search(r"\b(?:shelf|level|layer)\s*(\d+)\b", q)

        ctx = [f"GLOBAL SNAPSHOT: {self.facts['total']} total objects indexed."]
        
        if cats:
            for cat in cats:
                count = self.facts['global'].get(cat, 0)
                ctx.append(f"Fact: {count} {cat}(s) in the warehouse.")
                breakdown = {f"Rack {r}": self.facts['rack'].get(str(r), {}).get(cat, 0) for r in range(1, 13)}
                ctx.append(f"Rack Distribution for '{cat}': {breakdown}")

        elif "racks" in q or "every rack" in q or "all racks" in q or "distribution" in q:
            ctx.append(f"VERIFIED FULL RACK INVENTORY: {self.facts['rack']}")

        if aisle:
            aid = str(aisle.group(1))
            data = self.facts['aisle'].get(aid, {})
            ctx.append(f"AISLE {aid} GROUND TRUTH: Contains {sum(data.values())} total items. Breakdown: {dict(data)}")

        if rack:
            rid = str(rack.group(1))
            data = self.facts['rack'].get(rid, {})
            ctx.append(f"RACK {rid} GROUND TRUTH: Contains {sum(data.values())} total items. Breakdown: {dict(data)}")

        if rack and shelf:
            key = f"rack_{rack.group(1)}_shelf_{shelf.group(1)}"
            data = self.facts['shelf'].get(key, {})
            ctx.append(f"SHELF {shelf.group(1)} of RACK {rack.group(1)} GROUND TRUTH: Contains {dict(data)}")

        return "\n".join(ctx)

    def _draw_boxes(self, img, detections):
        canvas = img.copy()
        draw = ImageDraw.Draw(canvas)
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            color = _color_for_label(d["label"])
            label = f"{_display_name(d['label'])} {d['confidence']:.2f}"
            draw.rounded_rectangle((x1, y1, x2, y2), outline=color, width=4, radius=10)
            draw.text((x1+5, y1-20), label, fill=color)
        return canvas

    # --- LANGGRAPH NODE FUNCTIONS ---
    
    def node_analyze_vision(self, state: AgentState) -> dict:
        target_cats = self._get_target_categories(state["current_query"], state["history"])
        
        all_metadata = []
        annotated_images = []
        vision_infos = []

        if state["images"]:
            for idx, img in enumerate(state["images"]):
                # Ensure PIL Image
                pil_image = img.convert("RGB")
                
                # Run YOLO
                result = self._get_detector().predict(source=pil_image, conf=0.25, verbose=False)[0]
                detections = []
                if result.boxes is not None:
                    for box in result.boxes:
                        label = str(result.names[int(box.cls[0].item())])
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        mapped_cat = YOLO_TO_METADATA_CATEGORY.get(label, label)
                        detections.append({
                            "label": label,
                            "metadata_category": mapped_cat,
                            "confidence": float(box.conf[0].item()),
                            "bbox": [x1, y1, x2, y2]
                        })
                
                if target_cats == ["__ALL__"]:
                    hl_det = detections
                elif target_cats == []:
                    hl_det = []
                else:
                    hl_det = [d for d in detections if d["metadata_category"] in target_cats]
                
                info = ", ".join([f"{_display_name(k)} (x{v})" for k, v in Counter(d["label"] for d in detections).items()])
                if not info: info = "No objects detected."
                vision_infos.append(f"[Image {idx + 1}]: {info}")
                
                canvas = self._draw_boxes(pil_image, hl_det)
                annotated_images.append(_image_to_png_bytes(canvas))
                all_metadata.append({"highlighted_cats": target_cats})
        else:
            all_metadata = [{"used_fact_layer": True}]

        if vision_infos:
            return {"vision_info": "\n".join(vision_infos), "annotated_images": annotated_images, "metadata": all_metadata, "target_categories": target_cats}
        else:
            return {"vision_info": "No detections found across provided images.", "annotated_images": [], "metadata": all_metadata, "target_categories": target_cats}

    def node_retrieve_context(self, state: AgentState) -> dict:
        q = state["current_query"]
        spatial_ctx = self._get_spatial_context(q, state["target_categories"])
        
        n_res = 5 if state["images"] else 15
        res = self.collection.query(query_texts=[q], n_results=n_res)
        rag_docs = "\n".join(res.get("documents", [[]])[0])
        
        return {
            "spatial_context": spatial_ctx,
            "rag_docs": rag_docs
        }

    def node_generate_response(self, state: AgentState) -> dict:
        sys_inst = (
            "You are A-Ware, a helpful Warehouse Logistics AI.\n"
            "You MUST think step-by-step and wrap your internal reasoning inside <thinking>...</thinking> tags at the very beginning of your response. In these tags, explain your logic for answering the query. Do NOT leave the thinking block empty!\n"
            "Write a natural, conversational response. Speak like a warehouse assistant.\n"
            "Do NOT say 'According to VERIFIED DATA'. State the numbers clearly but casually.\n"
            "Use the exact counts provided in the context.\n"
            "Layout: 6 Aisles, 12 Racks. Aisle N = Racks 2N-1 and 2N."
        )

        messages = [SystemMessage(content=sys_inst)]

        # 1. Native Chat History (with Images)
        if state["history"]:
            for msg in state["history"][-4:]:
                text_content = msg.get("content", "")
                
                if msg["role"] == "user":
                    content_parts = [{"type": "text", "text": text_content}]
                    if "images" in msg and msg["images"]:
                        for img_str in msg["images"]:
                            # The frontend already passes "data:image/..." format
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {"url": img_str}
                            })
                    messages.append(HumanMessage(content=content_parts))
                else:
                    messages.append(AIMessage(content=text_content))

        # 2. Current Query Context
        prompt_text = (
            f"Relevant Context Data:\n{state['spatial_context']}\n\n"
            f"Current Vision Detection:\n{state['vision_info']}\n\n"
            f"Specific Database Records:\n{state['rag_docs']}\n\n"
            f"User Query: {state['current_query']}\n\n"
            "INSTRUCTIONS: You are provided with up to 5 images (labeled Image 1, Image 2, etc. in the Vision Detection). "
            "The user's query may refer to specific images (e.g., 'both', 'the last one', 'the first one', 'all of them'). "
            "Determine which image(s) the user is asking about and answer based ONLY on the relevant detections and your visual analysis of those specific images. "
            "If the database differs from the visual detection of the requested image(s), explicitly mention the discrepancy."
        )
        
        current_content_parts = [{"type": "text", "text": prompt_text}]
        
        if state["images"] and not state["use_yolo_only"]:
            for img in state["images"]:
                buffered = BytesIO()
                img.convert("RGB").save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                current_content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}
                })
                
        messages.append(HumanMessage(content=current_content_parts))

        response = self.llm.invoke(messages)
        
        # Handle cases where response.content is a list of blocks
        content = response.content
        if isinstance(content, list):
            # Extract text from the list of dicts
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and "text" in part]
            final_text = "".join(text_parts)
        else:
            # It's already a string
            final_text = str(content)
            
        return {"final_response": final_text}

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)
        
        builder.add_node("analyze_vision", self.node_analyze_vision)
        builder.add_node("retrieve_context", self.node_retrieve_context)
        builder.add_node("generate_response", self.node_generate_response)
        
        builder.add_edge(START, "analyze_vision")
        builder.add_edge("analyze_vision", "retrieve_context")
        builder.add_edge("retrieve_context", "generate_response")
        builder.add_edge("generate_response", END)
        
        return builder.compile()

    def process_query(self, query: str, images: list[Image.Image], history: list[dict], use_yolo_only: bool = False):
        initial_state = {
            "current_query": query,
            "images": images,
            "history": history,
            "target_categories": [],
            "vision_info": "",
            "spatial_context": "",
            "rag_docs": "",
            "annotated_images": [],
            "metadata": [],
            "final_response": "",
            "use_yolo_only": use_yolo_only
        }
        
        for event in self.graph.stream(initial_state):
            for key, value in event.items():
                yield key, value
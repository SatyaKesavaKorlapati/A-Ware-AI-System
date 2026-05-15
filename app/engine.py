from __future__ import annotations

import os
import re
import hashlib
import json
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
import torch
from ultralytics import YOLO
from google import genai

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

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    color = hex_color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))

def _text_color_for_background(hex_color: str) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#04121b" if luminance > 0.65 else "#ecf6ff"

def _color_for_label(label: str) -> str:
    if label in CLASS_COLORS: return CLASS_COLORS[label]
    digest = hashlib.md5(label.encode("utf-8")).hexdigest()
    return FALLBACK_COLORS[int(digest, 16) % len(FALLBACK_COLORS)]

# --- 3. WAREHOUSE AI ENGINE ---

class WarehouseAI:
    def __init__(self):
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        
        print("🧠 Initializing A-Ware Cognitive Engine...")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing.")
        
        self.gemini_client = genai.Client(api_key=api_key)
        self.model_name = "gemini-3.1-pro-preview"

        print("📁 Loading Hierarchical Facts...")
        self.collection = ensure_database(populate_if_missing=True)
        self.facts = self._load_verified_summaries()
        
        self.yolo_model_path = str(MODELS_DIR / "lar1r.pt")
        self.detector = None
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

    def _get_target_categories(self, current_query: str, history: list[dict[str, str]] | None) -> list[str]:
        """Intelligent spotting logic: Independent by default, cumulative if requested."""
        query_lower = current_query.lower()
        
        # 1. Trigger 'everything' mode
        if re.search(r"\b(all|every|everything)\b", query_lower):
            return []
            
        # 2. Extract targets from current query
        current_targets = set()
        for alias, canonical in CATEGORY_ALIASES.items():
            if re.search(rf"\b{alias}\b", query_lower):
                current_targets.add(canonical)

        # 3. Intent Detection: Check for accumulative keywords ("prev", "previous", "along with")
        accumulative_keywords = [r"along with", r"\bprev", r"\bprevious", r"\bkeep", r"\badd\b", r"\balso\b"]
        is_accumulative = any(re.search(kw, query_lower) for kw in accumulative_keywords)

        if is_accumulative and history:
            # Fetch targets from the LAST user message and add them to current targets
            for msg in reversed(history):
                if msg["role"] == "user":
                    last_query_lower = msg["content"].lower()
                    for alias, canonical in CATEGORY_ALIASES.items():
                        if re.search(rf"\b{alias}\b", last_query_lower):
                            current_targets.add(canonical)
                    break # Only fetch from the immediate previous message

        return list(current_targets)

    def _format_history(self, history: list[dict[str, str]] | None) -> str:
        if not history:
            return "No previous conversation context."
        
        formatted = []
        for msg in history[-4:]:
            role = "User" if msg["role"] == "user" else "A-Ware"
            text = msg.get("content", "")
            formatted.append(f"{role}: {text}")
            
        return "\n".join(formatted)

    def _get_spatial_context(self, query: str, history: list[dict[str, str]] | None) -> str:
        q = query.lower()
        aisle = re.search(r"\baisle\s*(\d+)\b", q)
        rack = re.search(r"\brack\s*(\d+)\b", q)
        shelf = re.search(r"\b(?:shelf|level|layer)\s*(\d+)\b", q)
        cats = self._get_target_categories(query, history)

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

    def detect_objects(self, image, conf: float = 0.25):
        pil_image = image.convert("RGB") if isinstance(image, Image.Image) else Image.open(image).convert("RGB")
        result = self._get_detector().predict(source=pil_image, conf=conf, verbose=False)[0]
        
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
        return detections

    def process_image_query(self, image, user_query: str, history=None):
        pil_image = image.convert("RGB") if isinstance(image, Image.Image) else Image.open(image).convert("RGB")
        all_detections = self.detect_objects(pil_image)
        
        target_cats = self._get_target_categories(user_query, history)
        if target_cats:
            highlighted_detections = [d for d in all_detections if d["metadata_category"] in target_cats]
        else:
            highlighted_detections = all_detections

        vision_info = ", ".join([f"{_display_name(k)} (x{v})" for k, v in Counter(d["label"] for d in all_detections).items()])
        fact_context = self._get_spatial_context(user_query, history)
        chat_history = self._format_history(history)
        
        res = self.collection.query(query_texts=[user_query], n_results=5)
        rag_docs = "\n".join(res.get("documents", [[]])[0])

        prompt = (
            f"You MUST wrap your internal reasoning inside <thinking>...</thinking> tags at the very beginning of your response.\n"
            f"Write a natural, conversational response. Speak like a warehouse assistant. "
            f"Do NOT say 'According to VERIFIED DATA'. State the numbers clearly but casually.\n\n"
            f"CONVERSATION HISTORY:\n{chat_history}\n\n"
            f"Relevant Context Data:\n{fact_context}\n\n"
            f"Current Vision Detection: {vision_info}\n\n"
            f"Specific Database Records:\n{rag_docs}\n\n"
            f"User Query: {user_query}"
        )

        answer = self._call_gemini(prompt, pil_image)
        canvas = self._draw_boxes(pil_image, highlighted_detections)
        return answer, {"highlighted_cats": target_cats}, self._image_to_png_bytes(canvas)

    def process_text_query(self, user_query: str, history=None):
        fact_context = self._get_spatial_context(user_query, history)
        chat_history = self._format_history(history)
        
        res = self.collection.query(query_texts=[user_query], n_results=15)
        rag_docs = "\n".join(res.get("documents", [[]])[0])

        prompt = (
            f"You MUST wrap your internal reasoning inside <thinking>...</thinking> tags at the very beginning of your response.\n"
            f"Write a natural, conversational response. Do NOT use the phrase 'VERIFIED DATA'.\n\n"
            f"CONVERSATION HISTORY:\n{chat_history}\n\n"
            f"Fact Context:\n{fact_context}\n\n"
            f"Detailed Records:\n{rag_docs}\n\n"
            f"User Query: {user_query}"
        )
        return self._call_gemini(prompt), {"used_fact_layer": True}

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

    def _image_to_png_bytes(self, image):
        buf = BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    def _call_gemini(self, prompt, image=None):
        contents = [image, prompt] if image else [prompt]
        sys_inst = (
            "You are A-Ware, a helpful Warehouse Logistics AI. "
            "Use the exact counts provided in the context. "
            "Layout: 6 Aisles, 12 Racks. Aisle N = Racks 2N-1 and 2N."
        )
        res = self.gemini_client.models.generate_content(
            model=self.model_name, contents=contents,
            config={"temperature": 0.1, "system_instruction": sys_inst}
        )
        return res.text

    def process_scene(self, image, user_query: str, history=None):
        return self.process_image_query(image, user_query, history)
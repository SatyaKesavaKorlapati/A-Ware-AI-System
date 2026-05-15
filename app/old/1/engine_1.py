from __future__ import annotations

import os
import re
import hashlib
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageDraw
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2VLForConditionalGeneration
from transformers.utils import logging as hf_logging

from data.data_ingestion import ensure_database, load_metadata
from utils.project_paths import MODELS_DIR, ensure_local_model_dirs

try:
    from qwen_vl_utils import process_vision_info
except ImportError:
    process_vision_info = None

try:
    import bitsandbytes  # noqa: F401

    BNB_AVAILABLE = True
except ImportError:
    BNB_AVAILABLE = False

try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

hf_logging.set_verbosity_error()


CATEGORY_ALIASES = {
    "box": "box",
    "boxes": "box",
    "carton": "box",
    "cartons": "box",
    "crate": "crate",
    "crates": "crate",
    "rack": "rack",
    "racks": "rack",
    "shelf": "rack",
    "shelves": "rack",
    "bottle": "bottle",
    "bottles": "bottle",
    "sign": "sign",
    "signs": "sign",
    "fire extinguisher": "extinguisher",
    "extinguisher": "extinguisher",
    "extinguishers": "extinguisher",
    "forklift": "forklift",
    "forklifts": "forklift",
    "barrel": "barrel",
    "barel": "barrel",
    "barrels": "barrel",
    "cone": "cone",
    "cones": "cone",
    "pallet": "pallet",
    "pallets": "pallet",
    "fuse box": "fuse_box",
    "fuse_box": "fuse_box",
    "emergency board": "emergency_board",
    "paper note": "paper_note",
    "floor decal": "floor_decal",
    "pillar": "pillar",
    "pillars": "pillar",
    "bracket": "bracket",
    "brackets": "bracket",
    "lamp": "lamp",
    "lamps": "lamp",
    "wire": "wire",
    "wires": "wire",
    "cart": "cart",
    "carts": "cart",
    "bucket": "bucket",
    "buckets": "bucket",
    "barcode": "barcode",
    "barcodes": "barcode",
    "floor": "floor",
}


YOLO_TO_METADATA_CATEGORY = {
    "pillar": "pillar",
    "bracket": "bracket",
    "lamp": "lamp",
    "paper_shortcut": "paper_shortcut",
    "sign": "sign",
    "wire": "wire",
    "box": "box",
    "floor_decal": "floor",
    "paper_note": "paper_shortcut",
    "pallet": None,
    "crate": "crate",
    "barel": "barrel",
    "fuse_box": None,
    "fire_extinguisher": "extinguisher",
    "forklift": "forklift",
    "bucket": "bucket",
    "barcode": "barcode",
    "bottle": "bottle",
    "cart": "cart",
    "cone": "cone",
    "emergency_board": None,
}

DISPLAY_LABELS = {
    "barel": "barrel",
    "fire_extinguisher": "fire extinguisher",
    "floor_decal": "floor decal",
    "paper_note": "paper note",
    "paper_shortcut": "paper shortcut",
    "fuse_box": "fuse box",
    "emergency_board": "emergency board",
}

CLASS_COLORS = {
    "pillar": "#d64550",
    "bracket": "#ef7d57",
    "lamp": "#f4a259",
    "paper_shortcut": "#ffd166",
    "sign": "#06d6a0",
    "wire": "#2ec4b6",
    "box": "#118ab2",
    "floor_decal": "#83c5be",
    "paper_note": "#ffca3a",
    "pallet": "#8d99ae",
    "crate": "#3a86ff",
    "barel": "#e63946",
    "fuse_box": "#9b5de5",
    "fire_extinguisher": "#f94144",
    "forklift": "#ff6b6b",
    "bucket": "#43aa8b",
    "barcode": "#577590",
    "bottle": "#4cc9f0",
    "cart": "#4361ee",
    "cone": "#f8961e",
    "emergency_board": "#f72585",
}

FALLBACK_COLORS = [
    "#ff595e",
    "#ff924c",
    "#ffca3a",
    "#8ac926",
    "#52b788",
    "#1982c4",
    "#4267ac",
    "#6a4c93",
    "#f15bb5",
    "#00bbf9",
]


def _pluralize(noun: str, count: int) -> str:
    if count == 1:
        return noun
    if noun == "box":
        return "boxes"
    if noun.endswith("y"):
        return noun[:-1] + "ies"
    return noun + "s"


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
    if label in CLASS_COLORS:
        return CLASS_COLORS[label]
    digest = hashlib.md5(label.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(FALLBACK_COLORS)
    return FALLBACK_COLORS[index]


def _clean_refined_query(text: str) -> str:
    cleaned = text.strip().strip('"').strip("'")
    cleaned = re.sub(r"^refined query:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    unique_values = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _normalize_messages(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    return history or []


def _extract_aisle_number(query: str) -> int | None:
    match = re.search(r"\b(?:aisle|asile)\s*(\d+)\b", query.lower())
    if match:
        return int(match.group(1))
    return None


def _extract_multiple_aisle_numbers(query: str) -> list[int]:
    return [int(value) for value in re.findall(r"\b(?:aisle|asile)?\s*(\d+)\b", query.lower())]


def _looks_like_layout_summary_query(query: str) -> bool:
    query_lower = query.lower()
    return any(term in query_lower for term in ["summarize the warehouse layout", "warehouse layout", "layout summary"])


def _is_follow_up_reference(query: str) -> bool:
    return re.search(r"\b(it|them|that|those|one|ones|same)\b", query.lower()) is not None


def _is_object_listing_query(query: str) -> bool:
    query_lower = query.lower()
    return (
        re.search(r"\bwhat(?:\s+\w+){0,3}\s+objects?\b", query_lower) is not None
        or "which objects" in query_lower
        or "list objects" in query_lower
        or "what is in this image" in query_lower
        or "what's in this image" in query_lower
    )


def build_inventory_snapshot() -> dict[str, Any]:
    records = load_metadata()
    category_counts = Counter(record.get("category", "unknown") for record in records)

    aisle_x_positions = sorted(
        {
            round(record["world_position"]["x"], 2)
            for record in records
            if "aislesign" in record.get("name", "").lower()
        }
    )
    aisle_centers = {idx + 1: x_pos for idx, x_pos in enumerate(aisle_x_positions)}

    boxes_per_aisle: dict[int, int] = {aisle: 0 for aisle in aisle_centers}
    for record in records:
        world_position = record.get("world_position", {})
        x_pos = world_position.get("x")
        if x_pos is None or not aisle_centers:
            continue
        nearest_aisle = min(aisle_centers, key=lambda aisle: abs(aisle_centers[aisle] - x_pos))
        if record.get("category") == "box":
            boxes_per_aisle[nearest_aisle] += 1

    return {
        "total_items": len(records),
        "category_counts": dict(category_counts),
        "inferred_aisle_count": len(aisle_centers),
        "boxes_per_aisle": boxes_per_aisle,
    }


class WarehouseAI:
    def __init__(self):
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        model_paths = ensure_local_model_dirs()
        self.model_path = str(model_paths["qwen"] or "Qwen/Qwen2-VL-7B-Instruct")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"🧠 Loading Qwen2-VL from {self.model_path}...")
        model_kwargs: dict[str, Any] = {
            "local_files_only": True,
            "attn_implementation": "sdpa",
        }
        if torch.cuda.is_available():
            if BNB_AVAILABLE:
                print("⚙️ Using 4-bit quantized loading to reduce VRAM usage.")
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
            else:
                model_kwargs["torch_dtype"] = torch.bfloat16
            model_kwargs["device_map"] = "auto"
        else:
            model_kwargs["torch_dtype"] = torch.float32

        self.model = Qwen2VLForConditionalGeneration.from_pretrained(self.model_path, **model_kwargs)
        self.processor = AutoProcessor.from_pretrained(
            self.model_path,
            local_files_only=True,
            use_fast=False,
        )
        for attr in ("temperature", "top_p", "top_k"):
            if hasattr(self.model.generation_config, attr):
                setattr(self.model.generation_config, attr, None)

        print("📁 Verifying Spatial RAG database...")
        self.collection = ensure_database(populate_if_missing=True)
        self.records = load_metadata()
        self.category_counts = Counter(record.get("category", "unknown") for record in self.records)
        self.aisle_centers = self._infer_aisles()
        self.records_with_aisles = self._attach_aisles(self.records)
        self.category_counts_by_aisle = self._build_category_counts_by_aisle()
        self.global_summary = self._build_global_summary()
        self.yolo_model_path = str(MODELS_DIR / "lar1r.pt")
        self.detector = None

    def should_use_image_context(self, user_query: str, history: list[dict[str, str]] | None = None) -> bool:
        query_lower = user_query.lower()
        image_terms = [
            "image",
            "picture",
            "photo",
            "scene",
            "see",
            "visible",
            "spot",
            "show",
            "locate",
            "where is",
            "where are",
            "highlight",
            "mark",
            "detect",
            "in this",
        ]
        if any(term in query_lower for term in image_terms):
            return True
        return self._category_from_query(user_query, history) is not None

    def _infer_aisles(self) -> dict[int, float]:
        aisle_x_positions = sorted(
            {
                round(record["world_position"]["x"], 2)
                for record in self.records
                if "aislesign" in record.get("name", "").lower()
            }
        )
        return {idx + 1: x_pos for idx, x_pos in enumerate(aisle_x_positions)}

    def _attach_aisles(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.aisle_centers:
            return records

        enriched_records = []
        for record in records:
            world_position = record.get("world_position", {})
            x_pos = world_position.get("x")
            aisle = None
            if x_pos is not None:
                aisle = min(self.aisle_centers, key=lambda aisle_id: abs(self.aisle_centers[aisle_id] - x_pos))

            enriched_record = dict(record)
            enriched_record["inferred_aisle"] = aisle
            enriched_records.append(enriched_record)
        return enriched_records

    def _build_global_summary(self) -> str:
        top_categories = ", ".join(
            f"{category}: {count}" for category, count in self.category_counts.most_common(6)
        )
        aisle_summary = ", ".join(
            f"Aisle {aisle}: x={x_pos:.2f}" for aisle, x_pos in list(self.aisle_centers.items())[:8]
        )
        return (
            f"Total indexed items: {len(self.records)}.\n"
            f"Top categories: {top_categories}.\n"
            f"Inferred aisle columns: {len(self.aisle_centers)}.\n"
            f"Sample aisle centers: {aisle_summary}.\n"
            "Aisles are inferred from aisle-sign x positions because the metadata does not expose a clean aisle field."
        )

    def _build_category_counts_by_aisle(self) -> dict[int, Counter]:
        counts_by_aisle: dict[int, Counter] = {aisle: Counter() for aisle in self.aisle_centers}
        for record in self.records_with_aisles:
            aisle = record.get("inferred_aisle")
            category = record.get("category", "unknown")
            if aisle in counts_by_aisle:
                counts_by_aisle[aisle][category] += 1
        return counts_by_aisle

    def _counts_for_category_by_aisle(self, category: str) -> dict[int, int]:
        return {
            aisle: aisle_counter.get(category, 0)
            for aisle, aisle_counter in sorted(self.category_counts_by_aisle.items())
        }

    def _format_per_aisle_counts(self, category: str) -> str:
        counts = self._counts_for_category_by_aisle(category)
        lines = [f"- Aisle {aisle}: {count} {_pluralize(category, count)}" for aisle, count in counts.items()]
        return "\n".join(lines)

    def _category_from_query(self, query: str, history: list[dict[str, str]] | None = None) -> str | None:
        query_lower = query.lower()
        for alias, canonical in sorted(CATEGORY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if alias in query_lower:
                return canonical

        for message in reversed(_normalize_messages(history)):
            content = str(message.get("content", "")).lower()
            for alias, canonical in sorted(CATEGORY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
                if alias in content:
                    return canonical
        return None

    def _categories_from_query(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        include_history: bool = False,
    ) -> list[str]:
        discovered: list[str] = []
        query_lower = query.lower()
        alias_pairs = sorted(CATEGORY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)

        for alias, canonical in alias_pairs:
            if alias in query_lower:
                discovered.append(canonical)

        if include_history:
            # Use only the latest user turn with explicit categories to avoid assistant-response leakage.
            for message in reversed(_normalize_messages(history)):
                if message.get("role") != "user":
                    continue

                content = str(message.get("content", "")).lower()
                latest_user_categories = []
                for alias, canonical in alias_pairs:
                    if alias in content:
                        latest_user_categories.append(canonical)

                if latest_user_categories:
                    discovered.extend(latest_user_categories)
                    break

        return _ordered_unique(discovered)

    def _retrieve_context(self, query: str, limit: int = 8):
        results = self.collection.query(query_texts=[query], n_results=limit)
        documents = results.get("documents", [[]])[0]
        metadata = results.get("metadatas", [[]])[0]
        context_text = "\n".join(documents) if documents else "No indexed warehouse context was found."
        return context_text, metadata

    def _get_detector(self):
        if not YOLO_AVAILABLE:
            raise RuntimeError("Ultralytics is not installed in this environment.")
        if self.detector is None:
            self.detector = YOLO(self.yolo_model_path)
        return self.detector

    def _metadata_positions_for_category(self, category: str | None, limit: int = 4):
        if not category:
            return {"metadata_category": None, "count": 0, "positions": []}

        matching = [record for record in self.records_with_aisles if record.get("category") == category]
        positions = [
            {
                "name": record.get("name"),
                "x": record.get("world_position", {}).get("x"),
                "y": record.get("world_position", {}).get("y"),
                "z": record.get("world_position", {}).get("z"),
                "aisle": record.get("inferred_aisle"),
            }
            for record in matching[:limit]
        ]
        return {"metadata_category": category, "count": len(matching), "positions": positions}

    def detect_objects(self, image, conf: float = 0.25):
        pil_image = image.convert("RGB") if isinstance(image, Image.Image) else Image.open(image).convert("RGB")
        detector = self._get_detector()
        results = detector.predict(source=pil_image, conf=conf, verbose=False)
        result = results[0]

        detections = []
        if result.boxes is None:
            return detections

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            label = str(result.names[class_id])
            metadata_category = YOLO_TO_METADATA_CATEGORY.get(label)
            x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
            detections.append(
                {
                    "label": label,
                    "metadata_category": metadata_category,
                    "confidence": float(box.conf[0].item()),
                    "bbox": [x1, y1, x2, y2],
                }
            )
        return detections

    def _draw_bounding_boxes(
        self,
        image: Image.Image,
        detections: list[dict],
        target_labels: set[str] | None = None,
        target_categories: set[str] | None = None,
    ):
        canvas = image.convert("RGB").copy()
        draw = ImageDraw.Draw(canvas)

        filtered = detections
        if target_labels or target_categories:
            filtered = [
                detection
                for detection in detections
                if (target_labels and detection["label"] in target_labels)
                or (target_categories and detection["metadata_category"] in target_categories)
            ]
        for detection in filtered:
            x1, y1, x2, y2 = detection["bbox"]
            color = _color_for_label(detection["label"])
            text_color = _text_color_for_background(color)
            label = f"{detection['label']} {detection['confidence']:.2f}"
            draw.rounded_rectangle((x1, y1, x2, y2), outline=color, width=4, radius=10)
            draw.rounded_rectangle((x1, max(0, y1 - 28), x1 + max(120, len(label) * 7), y1), fill=color, radius=8)
            draw.text((x1 + 8, max(2, y1 - 22)), label, fill=text_color)
        return canvas, filtered

    def _image_to_png_bytes(self, image: Image.Image) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _crop_detection_region(self, image: Image.Image, detection: dict[str, Any]) -> Image.Image:
        width, height = image.size
        x1, y1, x2, y2 = detection["bbox"]
        box_width = x2 - x1
        box_height = y2 - y1
        pad_x = int(box_width * 0.9)
        pad_y_top = int(box_height * 0.5)
        pad_y_bottom = int(box_height * 0.25)
        crop = (
            max(0, x1 - pad_x),
            max(0, y1 - pad_y_top),
            min(width, x2 + pad_x),
            min(height, y2 + pad_y_bottom),
        )
        return image.crop(crop)

    def _extract_visible_aisle_number(self, image: Image.Image, detection: dict[str, Any]) -> int | None:
        crop_image = self._crop_detection_region(image, detection)
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are reading warehouse aisle signs from an image crop near a detected object. "
                            "Return only the visible aisle number nearest the object, or unknown if no number is readable."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": crop_image},
                    {
                        "type": "text",
                        "text": (
                            f"The detected object is a {detection['label']}. "
                            "Read the nearest visible aisle sign number in this crop. "
                            "Return only the number or unknown."
                        ),
                    },
                ],
            },
        ]
        answer = self._generate_response(messages, max_new_tokens=12).strip()
        match = re.search(r"\b(\d{1,2})\b", answer)
        return int(match.group(1)) if match else None

    def _build_detection_context(self, detections: list[dict]):
        label_counts = Counter(detection["label"] for detection in detections)
        lines = []
        metadata_lookup = {}
        for label, count in label_counts.items():
            metadata_category = YOLO_TO_METADATA_CATEGORY.get(label)
            meta = self._metadata_positions_for_category(metadata_category)
            metadata_lookup[label] = meta
            position_lines = []
            for pos in meta["positions"]:
                position_lines.append(
                    f"({pos['x']}, {pos['y']}, {pos['z']}) aisle {pos['aisle']}"
                )
            sample_positions = ", ".join(position_lines) if position_lines else "No direct metadata positions available."
            lines.append(
                f"- {label}: detected {count} times; metadata category={metadata_category}; "
                f"indexed matches={meta['count']}; sample positions={sample_positions}"
            )
        return "\n".join(lines), metadata_lookup

    def _format_detection_list(self, detections: list[dict]) -> str:
        counts = Counter(detection["label"] for detection in detections)
        lines = [f"- {_display_name(label)}: {count}" for label, count in sorted(counts.items())]
        return "\n".join(lines)

    def process_image_query(self, image, user_query: str, history: list[dict[str, str]] | None = None):
        clean_query = user_query.strip() or "What objects are in this image?"
        refined_query = self._refine_user_query(clean_query, history)
        pil_image = image.convert("RGB") if isinstance(image, Image.Image) else Image.open(image).convert("RGB")
        detections = self.detect_objects(pil_image)

        if not detections:
            return (
                "I could not confidently detect any known YOLO objects in this image.",
                {
                    "original_query": clean_query,
                    "refined_query": refined_query,
                    "detections": [],
                },
                None,
            )

        detection_context, metadata_lookup = self._build_detection_context(detections)
        requested_categories = self._categories_from_query(refined_query)
        if not requested_categories and _is_follow_up_reference(refined_query):
            requested_categories = self._categories_from_query("", history, include_history=True)
        requested_category = requested_categories[0] if requested_categories else None
        query_lower = refined_query.lower()
        raw_query_lower = clean_query.lower()
        intent_text = f"{raw_query_lower} {query_lower}"
        target_yolo_labels: set[str] = set()
        if requested_categories:
            for requested in requested_categories:
                for label, mapped_category in YOLO_TO_METADATA_CATEGORY.items():
                    if mapped_category == requested or label == requested:
                        target_yolo_labels.add(label)

        wants_boxes = any(
            token in intent_text
            for token in [
                "where is",
                "where are",
                "bounding",
                "bounding box",
                "box it",
                "draw",
                "mark",
                "show",
                "locate",
                "highlight",
                "spot",
                "identify",
                "detect",
                "outline",
            ]
        )
        annotated_image = None
        highlighted = []
        if wants_boxes:
            annotated_image, highlighted = self._draw_bounding_boxes(
                pil_image,
                detections,
                target_labels=target_yolo_labels or None,
                target_categories=set(requested_categories) or None,
            )

        visible_aisle = None
        if highlighted:
            visible_aisle = self._extract_visible_aisle_number(pil_image, highlighted[0])
        elif target_yolo_labels:
            matching = [detection for detection in detections if detection["label"] in target_yolo_labels]
            if matching:
                visible_aisle = self._extract_visible_aisle_number(pil_image, matching[0])

        visible_aisle_line = (
            f"Nearest readable aisle sign in the image near the target object: aisle {visible_aisle}."
            if visible_aisle is not None
            else "No aisle number could be read confidently from the image near the target object."
        )

        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a warehouse vision copilot. "
                            "Use the YOLO detections as the primary image evidence and combine them with metadata lookups. "
                            "If exact world coordinates cannot be uniquely resolved from one image, say that clearly and provide the most likely indexed positions. "
                            "When the user asks what objects are visible, list the detected classes first. "
                            "When the user asks for locations, prefer any readable aisle sign from the image over inferred metadata aisles. "
                            "Only mention warehouse-wide counts when the user explicitly asks for totals."
                        ),
                    }
                ],
            },
            *self._history_as_messages(history),
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},
                    {
                        "type": "text",
                        "text": (
                            f"Original question: {clean_query}\n"
                            f"Refined query: {refined_query}\n\n"
                            f"YOLO detections:\n{detection_context}\n\n"
                            f"Image-local aisle evidence:\n{visible_aisle_line}\n\n"
                            "Answer the question using the detections and metadata. "
                            "List detected object names when asked what objects are in the image. "
                            "If bounding boxes were highlighted, mention that explicitly. "
                            "If the question is about one object in this image, answer specifically about that object instead of summarizing the whole warehouse. "
                            "Prefer compact, structured answers with short bullets when helpful."
                        ),
                    },
                ],
            },
        ]
        answer = self._generate_response(messages, max_new_tokens=260)
        result_metadata = {
            "original_query": clean_query,
            "refined_query": refined_query,
            "detections": detections,
            "metadata_candidates": metadata_lookup,
            "visible_aisle": visible_aisle,
        }
        if highlighted:
            result_metadata["highlighted_detections"] = highlighted
        annotated_bytes = self._image_to_png_bytes(annotated_image) if annotated_image is not None else None

        if requested_categories and wants_boxes:
            matched_by_category: dict[str, int] = {}
            for category in requested_categories:
                matched_count = sum(
                    1
                    for detection in detections
                    if detection["metadata_category"] == category or detection["label"] == category
                )
                matched_by_category[category] = matched_count

            total_matched = sum(matched_by_category.values())
            if total_matched == 0:
                target_names = ", ".join(_display_name(category) for category in requested_categories)
                answer = f"I could not detect any of the requested objects ({target_names}) in this image."
                return answer, result_metadata, annotated_bytes

            summary_lines = ["I highlighted the requested objects in the image:"]
            for category in requested_categories:
                count = matched_by_category.get(category, 0)
                label_name = _display_name(category)
                summary_lines.append(f"- {label_name}: {count}")

            if visible_aisle is not None:
                summary_lines.append(f"Nearest readable aisle sign near a highlighted object: aisle {visible_aisle}.")
            else:
                summary_lines.append("I could not read a reliable aisle number from the visible signs in this image.")

            if annotated_bytes is not None:
                summary_lines.append("I returned an annotated image with bounding boxes for these detections.")
            return "\n".join(summary_lines), result_metadata, annotated_bytes

        if _is_object_listing_query(intent_text) or any(term in intent_text for term in ["what can you see", "what do you see"]):
            answer = "Visible detected objects:\n" + self._format_detection_list(detections)
            return answer, result_metadata, annotated_bytes

        if requested_category and any(term in intent_text for term in ["where is", "where are", "locate", "spot", "identify", "detect"]):
            detected_count = sum(
                1
                for detection in detections
                if detection["label"] in target_yolo_labels or detection["metadata_category"] == requested_category
            )
            if detected_count:
                target_name = _display_name(requested_category)
                if visible_aisle is not None:
                    answer = f"The {target_name} appears near aisle {visible_aisle} in this image."
                else:
                    answer = f"I detected {detected_count} {target_name} object(s) in the image, but I could not read a reliable aisle number from the visible signs."
                if annotated_bytes is not None:
                    answer += " I also returned an annotated image with the highlighted detections."
                return answer, result_metadata, annotated_bytes

        return answer, result_metadata, annotated_bytes

    def _build_grounding_context(self, refined_query: str, history: list[dict[str, str]] | None = None):
        category = self._category_from_query(refined_query, history)
        aisles = [value for value in _extract_multiple_aisle_numbers(refined_query) if value in self.aisle_centers]
        if category is None and aisles and history:
            category = self._category_from_query("", history)

        documents, metadata = self._retrieve_context(refined_query, limit=5)
        facts = [
            f"Total indexed objects: {len(self.records)}",
            f"Inferred aisle count: {len(self.aisle_centers)}",
            f"Top categories: {', '.join(f'{name}={count}' for name, count in self.category_counts.most_common(6))}",
        ]

        if category is not None:
            facts.append(f"Total {_pluralize(category, 2)} in warehouse: {self.category_counts.get(category, 0)}")
            facts.append(f"{_pluralize(category, 2).capitalize()} by aisle:\n{self._format_per_aisle_counts(category)}")

        if aisles:
            box_counts = self._counts_for_category_by_aisle("box")
            requested = "\n".join(f"- Aisle {aisle}: {box_counts.get(aisle, 0)} boxes" for aisle in aisles)
            facts.append(f"Requested aisle box counts:\n{requested}")

        if _looks_like_layout_summary_query(refined_query):
            box_counts = self._counts_for_category_by_aisle("box")
            facts.append(
                "Box distribution by aisle:\n" + "\n".join(
                    f"- Aisle {aisle}: {count} boxes" for aisle, count in box_counts.items()
                )
            )

        return {
            "category": category,
            "aisles": aisles,
            "facts_text": "\n".join(f"- {fact}" if "\n" not in fact else fact for fact in facts),
            "retrieved_text": documents,
            "retrieved_metadata": metadata,
        }

    def _prepare_inputs(self, messages):
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        has_image = any(
            content_item.get("type") == "image"
            for message in messages
            for content_item in message.get("content", [])
        )

        if has_image:
            if process_vision_info is not None:
                image_inputs, video_inputs = process_vision_info(messages)
            else:
                image_inputs, video_inputs = [messages[-1]["content"][0]["image"]], None

            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
        else:
            inputs = self.processor(
                text=[text],
                padding=True,
                return_tensors="pt",
            )

        if torch.cuda.is_available():
            inputs = inputs.to("cuda")
        return inputs

    def _refine_user_query(self, user_query: str, history: list[dict[str, str]] | None = None) -> str:
        history_tail = self._history_as_messages(history)[-4:]
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a query normalizer for a warehouse RAG system. "
                            "Correct spelling mistakes, normalize wording, preserve the original meaning, "
                            "and keep aisle numbers exactly as intended. Return only the corrected query."
                        ),
                    }
                ],
            },
            *history_tail,
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Rewrite this warehouse query so it is clean and correctly spelled. "
                            "Do not answer it. Return only the rewritten query.\n\n"
                            f"Query: {user_query}"
                        ),
                    }
                ],
            },
        ]
        refined_query = _clean_refined_query(self._generate_response(messages, max_new_tokens=48))
        return refined_query or user_query

    def _generate_response(self, messages, max_new_tokens: int = 220) -> str:
        inputs = self._prepare_inputs(messages)

        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": False,
            "use_cache": True,
        }

        try:
            with torch.inference_mode():
                generated_ids = self.model.generate(**inputs, **generation_kwargs)
        except torch.OutOfMemoryError:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

            fallback_tokens = min(96, max_new_tokens)
            warning = (
                "GPU memory was tight, so I used a lower-memory generation fallback. "
                "If this keeps happening, close other GPU-heavy apps or reset the model cache."
            )
            with torch.inference_mode():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=fallback_tokens,
                    do_sample=False,
                    use_cache=False,
                )

        trimmed_ids = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(inputs.input_ids, generated_ids)
        ]
        answer = self.processor.batch_decode(
            trimmed_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        answer = answer or "The model did not return a response. Please try another prompt."
        if "warning" in locals():
            return f"{answer}\n\nNote: {warning}"
        return answer

    def _history_as_messages(self, history: list[dict[str, str]] | None):
        messages = []
        for item in _normalize_messages(history):
            role = item.get("role")
            content = str(item.get("content", ""))
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": [{"type": "text", "text": content}]})
        return messages[-8:]

    def process_text_query(self, user_query: str, history: list[dict[str, str]] | None = None):
        clean_query = user_query.strip()
        if not clean_query:
            return "Please enter a warehouse question.", {}

        refined_query = self._refine_user_query(clean_query, history)
        refined_lower = refined_query.lower()

        if re.search(r"\b(number|count|total|how many)\b", refined_lower) and re.search(
            r"\b(objects?|items?)\b", refined_lower
        ):
            result_metadata = {
                "original_query": clean_query,
                "refined_query": refined_query,
                "category": None,
                "aisles": [],
                "retrieved_matches": [],
            }
            return f"There are {len(self.records)} objects in the warehouse.", result_metadata

        if re.search(r"\b(classes?|categories|types?)\b", refined_lower) and re.search(
            r"\b(objects?|items?|warehouse|their|them|all)\b", refined_lower
        ):
            sorted_categories = sorted(self.category_counts.items(), key=lambda item: item[0])
            category_lines = [f"- {name}: {count}" for name, count in sorted_categories]
            result_metadata = {
                "original_query": clean_query,
                "refined_query": refined_query,
                "category": None,
                "aisles": [],
                "retrieved_matches": [],
            }
            return "Object classes in the warehouse:\n" + "\n".join(category_lines), result_metadata

        grounding = self._build_grounding_context(refined_query, history)
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a warehouse copilot. Reason carefully over the supplied warehouse facts and retrieved records. "
                            "Do not invent counts. Prefer the structured facts when answering counts or aisle questions. "
                            "If data is inferred, say that clearly, but still answer directly.\n\n"
                            f"Warehouse summary:\n{self.global_summary}\n\n"
                            "Aisles are inferred from aisle-sign columns."
                        ),
                    }
                ],
            },
            *self._history_as_messages(history),
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Structured warehouse facts:\n{grounding['facts_text']}\n\n"
                            f"Retrieved warehouse records:\n{grounding['retrieved_text']}\n\n"
                            f"Original question: {clean_query}\n"
                            f"Refined retrieval query: {refined_query}\n\n"
                            "Answer from scratch using the facts above. "
                            "For count questions, give the exact number if available. "
                            "Do not dump raw records unless the user explicitly asks for them. "
                            "Keep the answer concise and complete."
                        ),
                    }
                ],
            },
        ]
        result_metadata = {
            "original_query": clean_query,
            "refined_query": refined_query,
            "category": grounding["category"],
            "aisles": grounding["aisles"],
            "retrieved_matches": grounding["retrieved_metadata"],
        }
        return self._generate_response(messages, max_new_tokens=220), result_metadata

    def process_scene(self, image, user_query: str, history: list[dict[str, str]] | None = None):
        clean_query = user_query.strip()
        if not clean_query:
            return "Please enter a warehouse question.", []

        refined_query = self._refine_user_query(clean_query, history)
        context_text, metadata = self._retrieve_context(refined_query, limit=6)
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a warehouse operations assistant. "
                            "Use both the uploaded image and the retrieved warehouse context. "
                            "When counts are visible, estimate carefully and say whether the answer comes from image evidence, indexed context, or both."
                        ),
                    }
                ],
            },
            *self._history_as_messages(history),
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {
                        "type": "text",
                        "text": (
                            "Warehouse ground-truth context:\n"
                            f"{context_text}\n\n"
                            f"Original question: {clean_query}\n"
                            f"Refined retrieval query: {refined_query}\n\n"
                            "Answer clearly and mention the most relevant objects or areas."
                        ),
                    },
                ],
            },
        ]
        return self._generate_response(messages, max_new_tokens=160), {
            "original_query": clean_query,
            "refined_query": refined_query,
            "retrieved_matches": metadata,
        }

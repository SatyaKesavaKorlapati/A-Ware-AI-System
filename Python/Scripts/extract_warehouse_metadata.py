import os
import ctypes
import json
import time
from collections import Counter
from pathlib import Path

# 1. DLL Setup for PyTorch/Isaac Sim Stability
dll_path = r"D:\RAJU\rs\IssacSim\isaac_sim_g\Lib\site-packages\torch\lib"
if os.path.exists(dll_path):
    os.add_dll_directory(dll_path)
    try:
        ctypes.CDLL(os.path.join(dll_path, "c10.dll"))
    except Exception:
        pass

# Initialize Isaac Sim SimulationApp
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

import omni.usd
from pxr import Usd, UsdGeom

# --- CONFIGURATION ---
WAREHOUSE_USD_PATH = r"D:\RAJU\rs\IssacSim\Collected_Warehouse\Warehouse.usd"  
OUTPUT_JSON_PATH = "warehouse_rag_metadata_full.json"

# Full 22+ class list aligned with the vision model and A-Ware engine
TARGET_CATEGORIES = [
    "pillar", "bracket", "lamp", "paper_shortcut", "sign", "wire", 
    "box", "floor", "floor_decal", "paper_note", "pallet", "crate", 
    "barrel", "fuse_box", "fire_extinguisher", "extinguisher", "forklift", 
    "bucket", "barcode", "bottle", "cart", "cone", "emergency_board", 
    "rack"
]

print("\n" + "="*60)
print("🏗️  WAREHOUSE ANALYTICS: ROOT-LEVEL METADATA AGGREGATION 🏗️")
print("="*60)

# Open the USD Stage
print(f"Loading stage: {WAREHOUSE_USD_PATH}...")
omni.usd.get_context().open_stage(WAREHOUSE_USD_PATH)
stage = omni.usd.get_context().get_stage()
xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())

if not stage:
    print("❌ Failed to load the USD stage.")
    simulation_app.close()
    exit()

raw_metadata = []
seen_coordinates = {} # Key: (x, y, z, category) -> Value: prim_path

# --- 2. Robust Root-Level Extraction Logic ---
print("Scanning USD hierarchy for unique physical entities...")
for prim in stage.Traverse():
    if not prim.IsA(UsdGeom.Xformable):
        continue

    p_path = str(prim.GetPath())
    p_name = prim.GetName().lower()
    
    # Category Identification
    category = next((cat for cat in TARGET_CATEGORIES if cat in p_name), None)
    
    if category:
        # Compute Absolute World Position
        world_transform = xform_cache.GetLocalToWorldTransform(prim)
        translation = world_transform.ExtractTranslation()
        x, y, z = round(translation[0], 2), round(translation[1], 2), round(translation[2], 2)
        coord_key = (x, y, z, category)

        # SPATIAL DEDUPLICATION (Root-Level Count)
        # We only keep the primitive with the shortest path to ensure sub-components 
        # (like body parts of vehicles or machinery) do not inflate the object count.
        if coord_key in seen_coordinates:
            if len(p_path) < len(seen_coordinates[coord_key]):
                seen_coordinates[coord_key] = p_path
        else:
            seen_coordinates[coord_key] = p_path

        raw_metadata.append({
            "prim_path": p_path,
            "name": prim.GetName(),
            "category": category,
            "world_position": {"x": x, "y": y, "z": z}
        })

# --- 3. Analytics: Per-Rack and Per-Aisle Distribution ---
# Identify aisle centers based on "aislesign" metadata to orient the warehouse grid
aisle_centers_x = sorted({
    round(e["world_position"]["x"], 2) 
    for e in raw_metadata if "aislesign" in e["name"].lower()
})
rack_centers = {idx + 1: x_pos for idx, x_pos in enumerate(aisle_centers_x)}

final_metadata = []
global_counts = Counter()
rack_counts = {r: Counter() for r in rack_centers}
aisle_counts = {(r + 1) // 2: Counter() for r in rack_centers}

print("Computing rack-to-aisle distributions and spatial attributes...")
for entry in raw_metadata:
    # Process only the 'best' root path identified during traversal
    coord_tuple = (entry["world_position"]["x"], entry["world_position"]["y"], entry["world_position"]["z"], entry["category"])
    if seen_coordinates[coord_tuple] != entry["prim_path"]:
        continue

    x, y, z = entry["world_position"]["x"], entry["world_position"]["y"], entry["world_position"]["z"]
    cat = entry["category"]
    
    # Spatial Assignment (12 Rack IDs mapping to 6 Physical Aisles)
    # Physical Aisle = (Rack_ID + 1) // 2
    rid = min(rack_centers, key=lambda r: abs(rack_centers[r] - x)) if rack_centers else 0
    paid = (rid + 1) // 2 if rid else 0
    
    # Structural Attributes
    # Vertical Level Classification (based on shelf heights)
    shelf_level = 1 if z < 0.5 else (2 if z < 2.0 else (3 if z < 4.0 else 4))
    
    entry.update({
        "rack_id": rid,
        "physical_aisle": paid,
        "shelf_level": shelf_level,
        "text_context": f"Object {entry['name']} (Category: {cat}) is located at Rack {rid}, Aisle {paid} (Level {shelf_level}) at coordinates ({x}, {y}, {z})."
    })
    
    # Global and Local Aggregation
    global_counts[cat] += 1
    if rid: 
        rack_counts[rid][cat] += 1
        aisle_counts[paid][cat] += 1
    
    final_metadata.append(entry)

# --- 4. Report Generation & Output ---
print("\n" + "="*40)
print("WAREHOUSE INVENTORY REPORT")
print("="*40)
print(f"Total Unique Physical Objects: {len(final_metadata)}")
for cat, count in global_counts.most_common():
    print(f"- {cat.capitalize()}: {count}")

print("\n" + "="*40)
print("PER-AISLE LOGISTICS SUMMARY")
print("="*40)
for aisle, counts in sorted(aisle_counts.items()):
    total_items = sum(counts.values())
    print(f"Aisle {aisle}: {total_items} items total | Boxes: {counts.get('box', 0)}")

with open(OUTPUT_JSON_PATH, "w") as f:
    json.dump(final_metadata, f, indent=4)

print(f"\n✅ Cleaned metadata saved with Rack/Aisle counts to: {OUTPUT_JSON_PATH}")
simulation_app.close()
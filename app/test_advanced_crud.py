import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import AWereEngine
import sqlite3

def run_verify():
    engine = AWereEngine()
    conn = sqlite3.connect('database/warehouse_inventory.db')
    
    print("--- 1. Testing Mass Deletion ---")
    conn.execute("INSERT INTO inventory (category, rack_id, physical_aisle, shelf_level, x, y, z) VALUES ('lamp', 12, 6, 1, 0, 0, 0)")
    conn.execute("INSERT INTO inventory (category, rack_id, physical_aisle, shelf_level, x, y, z) VALUES ('lamp', 12, 6, 1, 1, 0, 0)")
    conn.commit()
    
    query1 = "Delete all lamps from Rack 12."
    events1 = list(engine.process_query(query1, [], [], allow_changes=True))
    ans1 = events1[-1][1].get("final_response", "")
    print(f"AI: {ans1[:100]}...")
    
    lamps_r12 = conn.execute("SELECT id FROM inventory WHERE category='lamp' AND rack_id=12").fetchall()
    if len(lamps_r12) == 0:
        print("✅ Correctly deleted all lamps from Rack 12.")
    else:
        print(f"❌ Failed to delete all lamps. Found: {len(lamps_r12)}")

    print("\\n--- 2. Testing Mass Shift ---")
    conn.execute("INSERT INTO inventory (category, rack_id, physical_aisle, shelf_level, x, y, z) VALUES ('box', 1, 1, 1, 0, 0, 0)")
    conn.execute("INSERT INTO inventory (category, rack_id, physical_aisle, shelf_level, x, y, z) VALUES ('box', 1, 1, 1, 1, 0, 0)")
    conn.commit()
    
    query2 = "Move all existing boxes from Rack 1 to Rack 3."
    events2 = list(engine.process_query(query2, [], [], allow_changes=True))
    ans2 = events2[-1][1].get("final_response", "")
    print(f"AI: {ans2[:100]}...")
    
    boxes_r1 = conn.execute("SELECT id FROM inventory WHERE category='box' AND rack_id=1").fetchall()
    boxes_r3 = conn.execute("SELECT rack_id, physical_aisle FROM inventory WHERE category='box' AND rack_id=3").fetchall()
    
    if len(boxes_r1) == 0 and len(boxes_r3) >= 2:
        aisles = set([b[1] for b in boxes_r3])
        if aisles == {2}:
            print("✅ Correctly shifted boxes and updated aisle mapping!")
        else:
            print(f"❌ Aisle mapping failed. Aisles: {aisles}")
    else:
        print("❌ Mass shift failed.")

    print("\\n--- 3. Testing Complex Multi-Spacing ---")
    query3 = "Add 3 new cones to Rack 1 and space them out exactly by 0.5 meters on the X-axis starting from x=0.0."
    events3 = list(engine.process_query(query3, [], [], allow_changes=True))
    ans3 = events3[-1][1].get("final_response", "")
    print(f"AI: {ans3[:100]}...")
    
    cones_r1 = conn.execute("SELECT x FROM inventory WHERE category='cone' AND rack_id=1 ORDER BY id DESC LIMIT 3").fetchall()
    x_coords = sorted([c[0] for c in cones_r1])
    print(f"Cone X coords: {x_coords}")
    
    if x_coords == [0.0, 0.5, 1.0]:
        print("✅ Correctly generated multiple precise spacing queries!")
    else:
        print(f"❌ Spacing failed. Coords: {x_coords}")

if __name__ == "__main__":
    run_verify()

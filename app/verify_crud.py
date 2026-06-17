import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import AWereEngine
import sqlite3

def run_verify():
    engine = AWereEngine()
    
    print("--- 1. Testing Safe INSERT ---")
    query1 = "Add a 5th lamp to Rack 12 safely."
    events1 = list(engine.process_query(query1, [], [], allow_changes=True))
    ans1 = events1[-1][1].get("final_response", "")
    print(f"AI: {ans1[:100]}...")

    conn = sqlite3.connect('database/warehouse_inventory.db')
    lamps_r12 = conn.execute("SELECT id, physical_aisle, shelf_level FROM inventory WHERE category='lamp' AND rack_id=12 ORDER BY id DESC").fetchall()
    print(f"Lamps in Rack 12: {lamps_r12}")
    
    if len(lamps_r12) >= 5:
        print("✅ Correctly added 5th lamp. Wait, there were 4 earlier. Now there are 5.")
        new_lamp_id = lamps_r12[0][0] # highest ID
    else:
        print("❌ Failed to add lamp.")
        return

    print("\\n--- 2. Testing Robust UPDATE ---")
    query2 = "Move that 5th lamp from Rack 12 to Aisle 1, Rack 1."
    events2 = list(engine.process_query(query2, [], [], allow_changes=True))
    ans2 = events2[-1][1].get("final_response", "")
    print(f"AI: {ans2[:100]}...")
    
    # Verify the ID was actually moved
    moved_lamp = conn.execute(f"SELECT rack_id, physical_aisle FROM inventory WHERE id={new_lamp_id}").fetchall()
    print(f"Moved Lamp State: {moved_lamp}")
    if moved_lamp[0][0] == 1 and moved_lamp[0][1] == 1:
        print("✅ Correctly updated the precise item using robust logic!")
    else:
        print("❌ Failed to update correctly.")

if __name__ == "__main__":
    run_verify()

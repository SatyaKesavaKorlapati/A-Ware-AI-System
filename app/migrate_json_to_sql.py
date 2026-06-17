import json
import os
import sys

# Add parent directory to path so we can import app.sql_manager
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.sql_manager import init_db, get_connection

def migrate():
    print("Initializing Database Schema...")
    init_db()
    
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MDta", "warehouse_rag_metadata_full.json")
    if not os.path.exists(json_path):
        print(f"Error: Could not find {json_path}")
        return
        
    print("Loading JSON data...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"Found {len(data)} records. Inserting into SQLite...")
    conn = get_connection()
    cursor = conn.cursor()
    
    count = 0
    for item in data:
        try:
            x = item.get("world_position", {}).get("x", 0.0)
            y = item.get("world_position", {}).get("y", 0.0)
            z = item.get("world_position", {}).get("z", 0.0)
            
            cursor.execute("""
                INSERT OR REPLACE INTO inventory 
                (prim_path, name, category, x, y, z, rack_id, physical_aisle, shelf_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get("prim_path"),
                item.get("name"),
                item.get("category"),
                x, y, z,
                item.get("rack_id"),
                item.get("physical_aisle"),
                item.get("shelf_level")
            ))
            count += 1
        except Exception as e:
            print(f"Failed to insert {item.get('prim_path')}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Successfully migrated {count} records to SQL.")

if __name__ == "__main__":
    migrate()

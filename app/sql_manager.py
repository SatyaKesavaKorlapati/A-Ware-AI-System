import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "warehouse_inventory.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prim_path TEXT UNIQUE,
            name TEXT,
            category TEXT,
            x REAL,
            y REAL,
            z REAL,
            rack_id INTEGER,
            physical_aisle INTEGER,
            shelf_level INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS racks (
            id INTEGER PRIMARY KEY,
            capacity INTEGER DEFAULT 600,
            physical_aisle INTEGER
        )
    """)
    
    # Check if racks exist, if not, seed default 12 racks
    cursor.execute("SELECT COUNT(*) as count FROM racks")
    row = cursor.fetchone()
    if row and dict(row).get('count', 0) == 0:
        import math
        for r in range(1, 13):
            aisle = math.ceil(r / 2.0)
            cursor.execute("INSERT INTO racks (id, capacity, physical_aisle) VALUES (?, ?, ?)", (r, 600, aisle))
            
    conn.commit()
    conn.close()

def query_db(query: str, params: tuple = ()) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        return results
    except Exception as e:
        return [{"error": str(e)}]
    finally:
        conn.close()

def execute_db(query: str, params: tuple = ()) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
        return {"status": "success", "rows_affected": cursor.rowcount}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

import math
from langchain_core.tools import tool
from typing import Optional, List
from app.sql_manager import query_db, execute_db

# Aisle mapping logic
def _get_physical_aisle(rack_id: int) -> int:
    return math.ceil(rack_id / 2.0)

def create_sql_tools(allow_changes: bool):
    
    @tool
    def get_inventory(category: str = None, rack_id: int = None) -> str:
        """Retrieves exact counts and locations of items in the warehouse. Provide category (singular) and/or rack_id to filter."""
        query = "SELECT category, rack_id, physical_aisle, COUNT(*) as total_count FROM inventory"
        conditions = []
        params = []
        
        if category:
            conditions.append("(category = ? OR name LIKE ?)")
            params.extend([category, f"%{category}%"])
        if rack_id:
            conditions.append("rack_id = ?")
            params.append(rack_id)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " GROUP BY category, rack_id, physical_aisle ORDER BY rack_id"
        
        res = query_db(query, tuple(params))
        if not res:
            return "No items found matching the criteria."
        if isinstance(res, list) and len(res) > 0 and "error" in res[0]:
            return f"Error querying database: {res[0]['error']}"
            
        summary = ["Inventory Found:"]
        for row in res:
            summary.append(f"- Category: {row['category']}, Rack: {row['rack_id']}, Aisle: {row['physical_aisle']}, Count: {row['total_count']}")
        return "\n".join(summary)

    @tool
    def add_inventory(category: str, count: int, rack_id: int = None) -> str:
        """Adds new items to the warehouse. Specify the category (singular noun) and how many to add. Optionally specify a destination rack."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        if count <= 0:
            return "Error: count must be > 0."
            
        if rack_id is None:
            # Find a rack with enough space
            res = query_db("SELECT rack_id, COUNT(*) as c FROM inventory GROUP BY rack_id")
            rack_counts = {row['rack_id']: row['c'] for row in res}
            # assume racks 1-12
            for r in range(1, 13):
                if rack_counts.get(r, 0) + count <= 600:
                    rack_id = r
                    break
            if rack_id is None:
                return "Error: Cannot find any rack with enough capacity for this insertion."
        else:
            # Check capacity
            res = query_db("SELECT COUNT(*) as c FROM inventory WHERE rack_id = ?", (rack_id,))
            current = res[0]['c'] if res else 0
            if current + count > 600:
                return f"Error: Rack {rack_id} currently has {current} items. Adding {count} exceeds the strict 600 limit."
                
        aisle = _get_physical_aisle(rack_id)
        
        # We use a recursive CTE for fast bulk inserts
        q = f"""
        WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x<={count-1})
        INSERT INTO inventory (name, category, rack_id, physical_aisle, shelf_level, x, y, z)
        SELECT ?, ?, ?, ?, 1, 0, 0, 0 FROM cnt;
        """
        exec_res = execute_db(q, (category, category, rack_id, aisle))
        if exec_res.get("status") == "success":
            return f"Success: Added {count} {category}s to Rack {rack_id} (Aisle {aisle})."
        return f"Database Error: {exec_res.get('message')}"

    @tool
    def remove_inventory(category: str, count: int, rack_id: int = None) -> str:
        """Removes items from the warehouse. Specify the category (singular) and how many to delete. Optionally specify the rack."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        if count <= 0:
            return "Error: count must be > 0."
            
        q = "SELECT id FROM inventory WHERE (category = ? OR name LIKE ?)"
        params = [category, f"%{category}%"]
        if rack_id:
            q += " AND rack_id = ?"
            params.append(rack_id)
            
        q += f" ORDER BY id DESC LIMIT {count}"
        items = query_db(q, tuple(params))
        
        if not items:
            return f"Error: No {category} found to remove."
        if len(items) < count:
            return f"Error: Only {len(items)} {category} found. Refusing to partially delete without confirmation."
            
        ids = [str(row['id']) for row in items]
        del_q = f"DELETE FROM inventory WHERE id IN ({','.join(ids)})"
        
        exec_res = execute_db(del_q)
        if exec_res.get("status") == "success":
            return f"Success: Removed {count} {category}s."
        return f"Database Error: {exec_res.get('message')}"

    @tool
    def move_inventory(category: str, count: int, from_rack: int, to_rack: int) -> str:
        """Moves items from one rack to another. Specify category (singular), count, source rack, and destination rack."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        if count <= 0:
            return "Error: count must be > 0."
            
        # Check from_rack has enough items
        q = "SELECT id FROM inventory WHERE (category = ? OR name LIKE ?) AND rack_id = ? ORDER BY id DESC LIMIT ?"
        items = query_db(q, (category, f"%{category}%", from_rack, count))
        
        if len(items) < count:
            return f"Error: Rack {from_rack} only has {len(items)} {category} items, cannot move {count}."
            
        # Check to_rack capacity
        res = query_db("SELECT COUNT(*) as c FROM inventory WHERE rack_id = ?", (to_rack,))
        current = res[0]['c'] if res else 0
        if current + count > 600:
            return f"Error: Rack {to_rack} currently has {current} items. Adding {count} exceeds the strict 600 limit."
            
        to_aisle = _get_physical_aisle(to_rack)
        ids = [str(row['id']) for row in items]
        
        upd_q = f"UPDATE inventory SET rack_id = ?, physical_aisle = ? WHERE id IN ({','.join(ids)})"
        exec_res = execute_db(upd_q, (to_rack, to_aisle))
        
        if exec_res.get("status") == "success":
            return f"Success: Moved {count} {category}s from Rack {from_rack} to Rack {to_rack} (Aisle {to_aisle})."
        return f"Database Error: {exec_res.get('message')}"

    return [get_inventory, add_inventory, remove_inventory, move_inventory]

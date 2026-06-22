import math
from langchain_core.tools import tool
from typing import Optional, List
from app.sql_manager import query_db, execute_db
from app.db_history import create_snapshot, undo_last_change, get_history, redo_last_change, rollback_to, discard_last_snapshot

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
        """Adds a specific count of items of a category. Provide rack_id to force add them to a specific rack, otherwise it uses greedy logic to find empty space."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
        
        create_snapshot(f"Before adding {count} {category} to warehouse")
            
        if count <= 0:
            discard_last_snapshot()
            return "Error: count must be > 0."
            
        if rack_id is None:
            # Distribute across multiple racks if needed
            rack_info = query_db("SELECT id as rack_id, capacity, physical_aisle FROM racks")
            if not rack_info or ('error' in rack_info[0] if rack_info else False):
                 discard_last_snapshot()
                 return "Error fetching racks."
            
            res = query_db("SELECT rack_id, COUNT(*) as c FROM inventory GROUP BY rack_id")
            rack_counts = {row['rack_id']: row['c'] for row in res}
            
            available_racks = []
            for r in rack_info:
                avail = r['capacity'] - rack_counts.get(r['rack_id'], 0)
                if avail > 0:
                    available_racks.append({'id': r['rack_id'], 'avail': avail, 'aisle': r['physical_aisle']})
                    
            available_racks.sort(key=lambda x: x['avail'], reverse=True)
            
            total_avail = sum(r['avail'] for r in available_racks)
            if total_avail < count:
                discard_last_snapshot()
                return f"Error: Not enough space in the warehouse. Need {count} slots, but only {total_avail} are available."
                
            allocations = []
            remaining = count
            for r in available_racks:
                if remaining <= 0: break
                to_add = min(remaining, r['avail'])
                allocations.append((r['id'], r['aisle'], to_add))
                remaining -= to_add
                
            # Perform inserts for each allocation
            for r_id, aisle, to_add in allocations:
                q = f"""
                WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x<={{to_add-1}})
                INSERT INTO inventory (name, category, rack_id, physical_aisle, shelf_level, x, y, z)
                SELECT ?, ?, ?, ?, 1, 0, 0, 0 FROM cnt;
                """
                # f-string literal braces must be doubled. We inject the dynamic limit directly into the string.
                # Actually, f"x<={to_add-1}" is sufficient if we don't need curly braces in the SQL syntax. 
                # Wait! WITH RECURSIVE does not use curly braces in SQL! So it's just x<={to_add-1}.
                q_fixed = f"""
                WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x<={to_add-1})
                INSERT INTO inventory (name, category, rack_id, physical_aisle, shelf_level, x, y, z)
                SELECT ?, ?, ?, ?, 1, 0, 0, 0 FROM cnt;
                """
                execute_db(q_fixed, (category, category, r_id, aisle))
                
            alloc_strs = [f"{a[2]} in Rack {a[0]}" for a in allocations]
            return f"Success: Added {count} {category}s distributed as follows: " + ", ".join(alloc_strs)
        else:
            # Check capacity for specific rack
            r_info = query_db("SELECT capacity FROM racks WHERE id = ?", (rack_id,))
            if not r_info or 'error' in (r_info[0] if len(r_info)>0 else {}):
                 discard_last_snapshot()
                 return f"Error: Rack {rack_id} does not exist in the racks table."
            max_cap = r_info[0]['capacity']
            
            res = query_db("SELECT COUNT(*) as c FROM inventory WHERE rack_id = ?", (rack_id,))
            current = res[0]['c'] if res else 0
            if current + count > max_cap:
                discard_last_snapshot()
                return f"Error: Rack {rack_id} currently has {current} items. Adding {count} exceeds its {max_cap} limit."
                
            aisle = _get_physical_aisle(rack_id)
            
            # Perform inserts
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
        """Removes a specific count of items of a category. Provide rack_id to only remove from that rack, otherwise it removes from anywhere in the warehouse."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
        
        create_snapshot(f"Before removing {count} {category} from warehouse")
            
        if count <= 0:
            discard_last_snapshot()
            return "Error: count must be > 0."
            
        q = "SELECT id FROM inventory WHERE (category = ? OR name LIKE ?)"
        params = [category, f"%{category}%"]
        if rack_id:
            q += " AND rack_id = ?"
            params.append(rack_id)
            
        q += f" ORDER BY id DESC LIMIT {count}"
        items = query_db(q, tuple(params))
        
        if not items:
            discard_last_snapshot()
            return f"Error: No {category} found to remove."
        if len(items) < count:
            discard_last_snapshot()
            return f"Error: Only {len(items)} {category} found. Refusing to partially delete without confirmation."
            
        ids = [str(row['id']) for row in items]
        del_q = f"DELETE FROM inventory WHERE id IN ({','.join(ids)})"
        
        exec_res = execute_db(del_q)
        if exec_res.get("status") == "success":
            return f"Success: Removed {count} {category}s."
        return f"Database Error: {exec_res.get('message')}"

    @tool
    def move_inventory(from_rack: int, to_rack: int = None, category: str = None, count: int = None) -> str:
        """Moves items between racks. Omitting to_rack scatters items greedily. Omitting category moves all categories. Omitting count moves all matching items."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        create_snapshot(f"Before moving inventory from Rack {from_rack}")
            
        q = "SELECT id, category FROM inventory WHERE rack_id = ?"
        params = [from_rack]
        if category:
            q += " AND (category = ? OR name LIKE ?)"
            params.extend([category, f"%{category}%"])
        q += " ORDER BY id DESC"
        if count is not None and count > 0:
            q += f" LIMIT {count}"
            
        items = query_db(q, tuple(params))
        
        if not items:
            discard_last_snapshot()
            return f"Error: No items found in Rack {from_rack} matching criteria."
            
        actual_count = len(items)
        if count is not None and actual_count < count:
            discard_last_snapshot()
            return f"Error: Only {actual_count} items found, cannot move {count}."
            
        if to_rack is not None:
            # Check capacity
            r_info = query_db("SELECT capacity, physical_aisle FROM racks WHERE id = ?", (to_rack,))
            if not r_info or 'error' in (r_info[0] if len(r_info)>0 else {}):
                 discard_last_snapshot()
                 return f"Error: Destination Rack {to_rack} does not exist."
            max_cap = r_info[0]['capacity']
            to_aisle = r_info[0]['physical_aisle']
            
            res = query_db("SELECT COUNT(*) as c FROM inventory WHERE rack_id = ?", (to_rack,))
            current = res[0]['c'] if res else 0
            if current + actual_count > max_cap:
                discard_last_snapshot()
                return f"Error: Rack {to_rack} currently has {current} items. Adding {actual_count} exceeds its {max_cap} limit."
                
            ids = [str(i['id']) for i in items]
            exec_res = execute_db(f"UPDATE inventory SET rack_id = ?, physical_aisle = ? WHERE id IN ({','.join(ids)})", (to_rack, to_aisle))
            if exec_res.get("status") == "success":
                return f"Success: Moved {actual_count} items from Rack {from_rack} to Rack {to_rack}."
            return f"Database Error: {exec_res.get('message')}"
        else:
            # Distribute greedily
            rack_info = query_db("SELECT id as rack_id, capacity, physical_aisle FROM racks WHERE id != ?", (from_rack,))
            res = query_db("SELECT rack_id, COUNT(*) as c FROM inventory GROUP BY rack_id")
            rack_counts = {row['rack_id']: row['c'] for row in res}
            
            available_racks = []
            for r in rack_info:
                avail = r['capacity'] - rack_counts.get(r['rack_id'], 0)
                if avail > 0:
                    available_racks.append({'id': r['rack_id'], 'avail': avail, 'aisle': r['physical_aisle']})
            available_racks.sort(key=lambda x: x['avail'], reverse=True)
            
            total_avail = sum(r['avail'] for r in available_racks)
            if total_avail < actual_count:
                 discard_last_snapshot()
                 return f"Error: Warehouse limits reached. Need {actual_count} slots, but only {total_avail} are available across other racks."
                 
            allocations = []
            remaining_items = list(items)
            for r in available_racks:
                if not remaining_items: break
                chunk = remaining_items[:r['avail']]
                remaining_items = remaining_items[r['avail']:]
                allocations.append((r['id'], r['aisle'], [str(i['id']) for i in chunk]))
                
            for r_id, aisle, ids in allocations:
                execute_db(f"UPDATE inventory SET rack_id = ?, physical_aisle = ? WHERE id IN ({','.join(ids)})", (r_id, aisle))
                
            alloc_strs = [f"{len(a[2])} to Rack {a[0]}" for a in allocations]
            return f"Success: Moved {actual_count} items from Rack {from_rack} distributed as follows: " + ", ".join(alloc_strs)

    @tool
    def rename_inventory(old_name: str, new_name: str, rack_id: int = None) -> str:
        """Renames a category of items (e.g. 'box' to 'carton'). Can be scoped to a specific rack_id."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        create_snapshot(f"Before renaming {old_name} to {new_name}")
            
        q = "SELECT id FROM inventory WHERE (category = ? OR name = ?)"
        params = [old_name, old_name]
        if rack_id:
            q += " AND rack_id = ?"
            params.append(rack_id)
            
        items = query_db(q, tuple(params))
        if not items:
            discard_last_snapshot()
            return f"Error: No items found with name/category '{old_name}'" + (f" in Rack {rack_id}" if rack_id else "") + " to rename."
            
        ids = [str(row['id']) for row in items]
        upd_q = f"UPDATE inventory SET name = ?, category = ? WHERE id IN ({','.join(ids)})"
        
        exec_res = execute_db(upd_q, (new_name, new_name))
        if exec_res.get("status") == "success":
            return f"Success: Renamed {len(items)} items to '{new_name}'."
        return f"Database Error: {exec_res.get('message')}"
    @tool
    def add_rack(capacity: int = 600, rack_id: int = None) -> str:
        """Adds a new rack to the warehouse. Will auto-assign an ID if not provided."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        create_snapshot(f"Before adding new rack with capacity {capacity}")
        
        if rack_id is not None:
            # Check if it exists
            res = query_db("SELECT id FROM racks WHERE id = ?", (rack_id,))
            if res and len(res) > 0 and 'error' not in res[0]:
                discard_last_snapshot()
                return f"Error: Rack {rack_id} already exists. Do you want to use a different ID/name? Please specify."
                
            # Insert explicitly requested ID
            aisle = math.ceil(rack_id / 2.0)
            exec_res = execute_db("INSERT INTO racks (id, capacity, physical_aisle) VALUES (?, ?, ?)", (rack_id, capacity, aisle))
            if exec_res.get("status") == "success":
                return f"Success: Added Rack {rack_id} with capacity {capacity} in Aisle {aisle}."
            return f"Database Error: {exec_res.get('message')}"
            
        else:
            # Retry loop to handle concurrent tool calls
            for attempt in range(5):
                res = query_db("SELECT MAX(id) as max_id FROM racks")
                next_id = (res[0]['max_id'] or 0) + 1
                aisle = math.ceil(next_id / 2.0)
                exec_res = execute_db("INSERT INTO racks (id, capacity, physical_aisle) VALUES (?, ?, ?)", (next_id, capacity, aisle))
                
                if exec_res.get("status") == "success":
                    return f"Success: Added Rack {next_id} with capacity {capacity} in Aisle {aisle}."
                    
                if "UNIQUE constraint failed" not in str(exec_res.get("message", "")):
                    return f"Database Error: {exec_res.get('message')}"
                    
            discard_last_snapshot()
            return "Error: Failed to automatically assign a new rack ID due to high concurrency. Please specify a rack_id explicitly."

    @tool
    def update_rack_capacity(rack_id: int, new_capacity: int) -> str:
        """Updates the maximum capacity of an existing rack."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        create_snapshot(f"Before updating Rack {rack_id} capacity to {new_capacity}")
            
        res = query_db("SELECT id FROM racks WHERE id = ?", (rack_id,))
        if not res or 'error' in (res[0] if len(res)>0 else {}):
            discard_last_snapshot()
            return f"Error: Rack {rack_id} does not exist."
            
        exec_res = execute_db("UPDATE racks SET capacity = ? WHERE id = ?", (new_capacity, rack_id))
        if exec_res.get("status") == "success":
            return f"Success: Updated Rack {rack_id} capacity to {new_capacity}."
        return f"Database Error: {exec_res.get('message')}"

    @tool
    def get_racks(rack_id: int = None) -> str:
        """Retrieves information about the racks in the warehouse, including their maximum capacities and aisles. Provide a rack_id to check a specific rack, or leave blank to list all racks. Use this to calculate total warehouse capacity."""
        if rack_id is not None:
            res = query_db("SELECT id, capacity, physical_aisle FROM racks WHERE id = ?", (rack_id,))
        else:
            res = query_db("SELECT id, capacity, physical_aisle FROM racks ORDER BY id")
            
        if not res or ('error' in res[0] if len(res)>0 else False):
            return "No racks found or error querying database."
            
        summary = ["Rack Information:"]
        for r in res:
            summary.append(f"- Rack: {r['id']}, Aisle: {r['physical_aisle']}, Capacity: {r['capacity']}")
        return "\n".join(summary)

    @tool
    def delete_rack(rack_id: int) -> str:
        """Deletes an empty rack from the warehouse. The rack must have 0 items in it before it can be deleted."""
        if not allow_changes:
            return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
            
        create_snapshot(f"Before deleting Rack {rack_id}")
            
        # Check if rack exists
        res = query_db("SELECT id FROM racks WHERE id = ?", (rack_id,))
        if not res or 'error' in (res[0] if len(res)>0 else {}):
            discard_last_snapshot()
            return f"Error: Rack {rack_id} does not exist."
            
        # Check if rack is empty
        res = query_db("SELECT COUNT(*) as c FROM inventory WHERE rack_id = ?", (rack_id,))
        count = res[0]['c'] if res else 0
        if count > 0:
            discard_last_snapshot()
            return f"Error: Rack {rack_id} is not empty. It currently contains {count} items. You must move or remove these items before deleting the rack."
            
        exec_res = execute_db("DELETE FROM racks WHERE id = ?", (rack_id,))
        if exec_res.get("status") == "success":
            return f"Success: Rack {rack_id} has been permanently deleted from the warehouse."
        return f"Database Error: {exec_res.get('message')}"

    @tool
    def sort_warehouse() -> str:
        """Sorts the entire warehouse densely. Items of the same category are grouped together sequentially, filling racks to their maximum capacity without any wasted space."""
        if not allow_changes:
             return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
             
        create_snapshot("Before strictly sorting the entire warehouse")
             
        from app.sql_manager import get_connection
        conn = get_connection()
        c = conn.cursor()
        
        # 1. Fetch all items ordered by category
        c.execute("SELECT id, category FROM inventory ORDER BY category, id")
        items = c.fetchall()
        if not items:
            conn.close()
            return "Warehouse is empty."
            
        # 2. Fetch all racks ordered by id
        c.execute("SELECT id, capacity, physical_aisle FROM racks ORDER BY id")
        racks = c.fetchall()
        if not racks:
            conn.close()
            return "No racks found."
            
        total_cap = sum(r['capacity'] for r in racks)
        if total_cap < len(items):
            conn.close()
            discard_last_snapshot()
            return f"Error: Total warehouse capacity ({total_cap}) is less than items ({len(items)}). This shouldn't happen unless database is corrupted."
            
        updates = []
        rack_idx = 0
        current_rack = racks[rack_idx]
        current_rack_fill = 0
        
        for item in items:
            if current_rack_fill >= current_rack['capacity']:
                rack_idx += 1
                current_rack = racks[rack_idx]
                current_rack_fill = 0
                
            updates.append((current_rack['id'], current_rack['physical_aisle'], item['id']))
            current_rack_fill += 1
            
        c.executemany("UPDATE inventory SET rack_id=?, physical_aisle=? WHERE id=?", updates)
        conn.commit()
        conn.close()
        
        return f"Success: Completely sorted {len(items)} items across the warehouse densely by category."

    @tool
    def group_warehouse(auto_expand: bool = False) -> str:
        """Groups similar items into dedicated racks. A rack will strictly contain only one category, even if there is wasted space left over. CRITICAL RULE: You MUST NEVER set auto_expand=True on your first attempt. If it fails due to lack of racks, you MUST stop and ask the user for permission using interactive UI buttons. To render UI buttons, output exact markdown links like this: [Yes](#action-yes) and [No](#action-no). CRITICAL RULE 2: If the user replies with "yes" to your prompt, you MUST immediately call this function again with auto_expand=True. If the user replies "no", acknowledge the cancellation."""
        if not allow_changes:
             return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
             
        if auto_expand:
            create_snapshot("Before grouping the warehouse and auto-expanding racks")
        else:
            create_snapshot("Before grouping the warehouse")
             
        from app.sql_manager import get_connection
        import math
        conn = get_connection()
        c = conn.cursor()
        
        c.execute("SELECT category, COUNT(*) as c FROM inventory GROUP BY category ORDER BY category")
        cats = c.fetchall()
        if not cats:
            conn.close()
            return "Warehouse is empty."
            
        c.execute("SELECT id, capacity, physical_aisle FROM racks ORDER BY id")
        racks = c.fetchall()
        
        alloc_map = {cat_row['category']: [] for cat_row in cats}
        rack_idx = 0
        missing_racks = 0
        
        for cat_row in cats:
            cat = cat_row['category']
            rem = cat_row['c']
            while rem > 0:
                if rack_idx < len(racks):
                    r = racks[rack_idx]
                    alloc_map[cat].append({'id': r['id'], 'aisle': r['physical_aisle'], 'cap': r['capacity'], 'filled': 0})
                    rem -= r['capacity']
                    rack_idx += 1
                else:
                    missing_racks += 1
                    rem -= 600
                    
        if missing_racks > 0 and not auto_expand:
            conn.close()
            discard_last_snapshot()
            return f"Error: Not enough racks to strictly group items! We need {missing_racks} more racks to support isolated categories. Ask the user if they are okay with adding them, and if so, call this tool again with auto_expand=True."
            
        if missing_racks > 0 and auto_expand:
            next_id = max(r['id'] for r in racks) + 1 if racks else 1
            for _ in range(missing_racks):
                aisle = math.ceil(next_id / 2.0)
                c.execute("INSERT INTO racks (id, capacity, physical_aisle) VALUES (?, ?, ?)", (next_id, 600, aisle))
                next_id += 1
            conn.commit()
            
            # Restart allocation strictly with new racks included
            c.execute("SELECT id, capacity, physical_aisle FROM racks ORDER BY id")
            racks = c.fetchall()
            alloc_map = {cat_row['category']: [] for cat_row in cats}
            rack_idx = 0
            for cat_row in cats:
                cat = cat_row['category']
                rem = cat_row['c']
                while rem > 0:
                    r = racks[rack_idx]
                    alloc_map[cat].append({'id': r['id'], 'aisle': r['physical_aisle'], 'cap': r['capacity'], 'filled': 0})
                    rem -= r['capacity']
                    rack_idx += 1
                    
        updates = []
        c.execute("SELECT id, category FROM inventory ORDER BY id")
        for item in c.fetchall():
            cat = item['category']
            target_rack = next(r for r in alloc_map[cat] if r['filled'] < r['cap'])
            updates.append((target_rack['id'], target_rack['aisle'], item['id']))
            target_rack['filled'] += 1
            
        c.executemany("UPDATE inventory SET rack_id=?, physical_aisle=? WHERE id=?", updates)
        conn.commit()
        conn.close()
        
        msg = f"Success: Grouped {len(updates)} items strictly by category."
        if missing_racks > 0:
            msg += f" Automatically created {missing_racks} new racks to accommodate the grouping."
        return msg

    @tool
    def view_history() -> str:
        """View the chronological timeline of database changes. Gives interactive buttons for the user to restore to a past point. CRITICAL RULE: You MUST return the exact raw output of this tool to the user without summarizing, rephrasing, or altering the markdown links."""
        history = get_history()
        undo_stack = history.get("undo_stack", [])
        if not undo_stack:
            return "No history available."
            
        import datetime
        import json
        timeline_data = []
        for entry in undo_stack[-10:]: # Show last 10
            dt = datetime.datetime.fromtimestamp(entry['timestamp']/1000).strftime('%Y-%m-%d %H:%M')
            timeline_data.append({
                "id": entry["id"],
                "date": dt,
                "desc": entry["description"]
            })
        
        json_str = json.dumps(timeline_data)
        return f"""Tell the user: "Here is the interactive timeline:"
Then append this EXACT markdown code block (do not change it):
```timeline
{json_str}
```
"""

    @tool
    def rollback_database() -> str:
        """Undoes the very last change made to the database."""
        if not allow_changes:
             return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
        res = undo_last_change()
        if res["status"] == "success":
            return res["message"]
        return f"Error: {res['message']}"

    @tool
    def redo_database() -> str:
        """Redoes the last undone change, acting like Ctrl+Y."""
        if not allow_changes:
             return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
        res = redo_last_change()
        if res["status"] == "success":
            return res["message"]
        return f"Error: {res['message']}"

    @tool
    def restore_snapshot(snapshot_id: str) -> str:
        """Restores the database to a specific snapshot ID from the timeline (e.g. 'snapshot_1234')."""
        if not allow_changes:
             return "REFUSED: Database Modifying Mode is disabled. Inform the user they must enable it."
        if snapshot_id.startswith("restore_"):
             snapshot_id = snapshot_id.replace("restore_", "")
        res = rollback_to(snapshot_id)
        if res["status"] == "success":
            return res["message"]
        return f"Error: {res['message']}"

    return [get_inventory, get_racks, add_inventory, remove_inventory, move_inventory, rename_inventory, add_rack, update_rack_capacity, delete_rack, sort_warehouse, group_warehouse, view_history, rollback_database, redo_database, restore_snapshot]

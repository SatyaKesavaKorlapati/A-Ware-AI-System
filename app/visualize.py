from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.sql_manager import query_db, execute_db

router = APIRouter()

@router.get("/api/map/layout")
async def get_map_layout():
    """
    Fetches the entire inventory layout mapped by rack_id, physical_aisle, etc.
    Returns a structured hierarchy for the frontend to render the 2D grid.
    """
    items = query_db("SELECT * FROM inventory")
    if len(items) > 0 and "error" in items[0]:
        return {"status": "error", "message": items[0]["error"]}

    # We return the raw items so the frontend React Engine can dynamically cluster them.
    return {"status": "success", "items": items}

class AdjustRequest(BaseModel):
    item_id: int
    action: str # "increment" or "decrement"

@router.post("/api/map/adjust")
async def adjust_item_count(req: AdjustRequest):
    """
    A fast, lightweight endpoint specifically for the UI + and - buttons on the side panel.
    Currently, since each row represents a unique physical item (with unique ID), 
    'decrement' means we delete it. 'increment' means we duplicate its coordinates into a new item.
    """
    item = query_db("SELECT * FROM inventory WHERE id = ?", (req.item_id,))
    if not item or "error" in item[0]:
        return {"status": "error", "message": "Item not found"}
        
    it = item[0]
    
    if req.action == "decrement":
        execute_db("DELETE FROM inventory WHERE id = ?", (req.item_id,))
        return {"status": "success", "message": f"Deleted item {req.item_id}"}
        
    elif req.action == "increment":
        import time
        # Duplicate the item at the exact same location
        execute_db("""
            INSERT INTO inventory (prim_path, name, category, x, y, z, rack_id, physical_aisle, shelf_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            it["prim_path"] + "_copy_" + str(int(time.time()*1000)), # dummy path
            it["name"],
            it["category"],
            it["x"],
            it["y"],
            it["z"],
            it["rack_id"],
            it["physical_aisle"],
            it["shelf_level"]
        ))
        return {"status": "success", "message": "Duplicated item"}

    return {"status": "error", "message": "Invalid action"}

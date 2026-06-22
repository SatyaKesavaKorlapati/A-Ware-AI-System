import sqlite3
import os
import json
import time
import shutil

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "warehouse_inventory.db")
HISTORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "history")
HISTORY_LOG = os.path.join(HISTORY_DIR, "history_log.json")

def _load_log():
    if not os.path.exists(HISTORY_LOG):
        return {"undo_stack": [], "redo_stack": []}
    with open(HISTORY_LOG, "r") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return {"undo_stack": data, "redo_stack": []}
            return data
        except json.JSONDecodeError:
            return {"undo_stack": [], "redo_stack": []}

def _save_log(log):
    with open(HISTORY_LOG, "w") as f:
        json.dump(log, f, indent=4)

def _take_snapshot_file() -> tuple[str, str, int]:
    os.makedirs(HISTORY_DIR, exist_ok=True)
    timestamp = int(time.time() * 1000)
    snapshot_id = f"snapshot_{timestamp}"
    snapshot_path = os.path.join(HISTORY_DIR, f"{snapshot_id}.db")
    
    source = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(snapshot_path)
    with dest:
        source.backup(dest)
    dest.close()
    source.close()
    return snapshot_id, snapshot_path, timestamp

def create_snapshot(description: str):
    """Called before any normal database modification to save state and clear redo stack."""
    try:
        snapshot_id, snapshot_path, timestamp = _take_snapshot_file()
        
        log = _load_log()
        log["undo_stack"].append({
            "id": snapshot_id,
            "description": description,
            "timestamp": timestamp,
            "file": snapshot_path
        })
        
        # Clear redo stack (divergent timeline)
        for entry in log["redo_stack"]:
            if os.path.exists(entry["file"]):
                try:
                    os.remove(entry["file"])
                except OSError:
                    pass
        log["redo_stack"] = []
        
        if len(log["undo_stack"]) > 20:
            oldest = log["undo_stack"].pop(0)
            if os.path.exists(oldest["file"]):
                try:
                    os.remove(oldest["file"])
                except OSError:
                    pass
                
        _save_log(log)
    except Exception as e:
        print(f"Error creating DB snapshot: {e}")

def discard_last_snapshot():
    """Removes the last snapshot from the undo stack if an operation fails, preventing false history."""
    log = _load_log()
    if log["undo_stack"]:
        last = log["undo_stack"].pop()
        if os.path.exists(last["file"]):
            try:
                os.remove(last["file"])
            except OSError:
                pass
        _save_log(log)

def get_history() -> dict:
    return _load_log()

def undo_last_change() -> dict:
    log = _load_log()
    if not log["undo_stack"]:
        return {"status": "error", "message": "No history available to undo."}
        
    target_entry = log["undo_stack"].pop()
    
    if not os.path.exists(target_entry["file"]):
        return {"status": "error", "message": "Snapshot file missing."}
        
    try:
        # 1. Take snapshot of CURRENT state before undoing
        snap_id, snap_path, ts = _take_snapshot_file()
        log["redo_stack"].append({
            "id": snap_id,
            "description": target_entry["description"], 
            "timestamp": ts,
            "file": snap_path
        })
        
        # 2. Overwrite DB with target
        shutil.copy2(target_entry["file"], DB_PATH)
        
        _save_log(log)
        return {"status": "success", "message": f"Successfully undone: '{target_entry['description']}'"}
    except Exception as e:
        return {"status": "error", "message": f"Undo failed: {e}"}

def redo_last_change() -> dict:
    log = _load_log()
    if not log["redo_stack"]:
        return {"status": "error", "message": "No redo history available."}
        
    target_entry = log["redo_stack"].pop()
    
    if not os.path.exists(target_entry["file"]):
        return {"status": "error", "message": "Snapshot file missing."}
        
    try:
        # 1. Take snapshot of CURRENT state before redoing (which goes into undo stack)
        snap_id, snap_path, ts = _take_snapshot_file()
        log["undo_stack"].append({
            "id": snap_id,
            "description": target_entry["description"], 
            "timestamp": ts,
            "file": snap_path
        })
        
        # 2. Overwrite DB with target
        shutil.copy2(target_entry["file"], DB_PATH)
        
        _save_log(log)
        return {"status": "success", "message": f"Successfully redone: '{target_entry['description']}'"}
    except Exception as e:
        return {"status": "error", "message": f"Redo failed: {e}"}

def rollback_to(snapshot_id: str) -> dict:
    log = _load_log()
    
    target_idx = -1
    for i, entry in enumerate(log["undo_stack"]):
        if entry["id"] == snapshot_id:
            target_idx = i
            break
            
    if target_idx == -1:
        return {"status": "error", "message": "Snapshot not found in undo history."}
        
    # Undo repeatedly until we hit the snapshot
    num_undos = len(log["undo_stack"]) - target_idx
    for _ in range(num_undos):
        res = undo_last_change()
        if res["status"] != "success":
            return res
            
    return {"status": "success", "message": f"Successfully rolled back to past timeline."}

import os
import json
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import AWereEngine

def get_ground_truth(query_type: str, sql: str = None) -> str:
    if query_type == "sql":
        conn = sqlite3.connect('database/warehouse_inventory.db')
        try:
            res = conn.execute(sql).fetchall()
            return str(res)
        except Exception as e:
            return f"SQL Error: {e}"
    return "See Document"

queries = [
    # Basic Aggregations
    {"q": "How many pallets are currently registered in the warehouse?", "type": "sql", "truth": "SELECT count(*) FROM inventory WHERE category = 'pallet';"},
    {"q": "Give me a breakdown of all the signs organized by rack.", "type": "sql", "truth": "SELECT rack_id, count(*) FROM inventory WHERE category = 'sign' GROUP BY rack_id;"},
    {"q": "What are the exact coordinate locations (x, y, z) and physical aisles of the fire extinguishers?", "type": "sql", "truth": "SELECT x, y, z, physical_aisle, shelf_level FROM inventory WHERE category = 'extinguisher';"},
    {"q": "What is the total number of items stored in Rack 12 across all categories?", "type": "sql", "truth": "SELECT count(*) FROM inventory WHERE rack_id = 12;"},
    
    # Advanced Aggregations (Added)
    {"q": "What is the average shelf level of all crates in the warehouse?", "type": "sql", "truth": "SELECT AVG(shelf_level) FROM inventory WHERE category = 'crate';"},
    {"q": "Which physical aisle contains the maximum number of items overall? Give me the aisle and count.", "type": "sql", "truth": "SELECT physical_aisle, count(*) as c FROM inventory GROUP BY physical_aisle ORDER BY c DESC LIMIT 1;"},
    {"q": "Are there more signs or bottles in the warehouse?", "type": "sql", "truth": "SELECT category, count(*) FROM inventory WHERE category IN ('sign', 'bottle') GROUP BY category;"},

    # RAG Queries
    {"q": "What is the official procedure for forklift maintenance according to the system manual?", "type": "rag", "truth": None},
    {"q": "Who is the listed owner/administrator of this warehouse system?", "type": "rag", "truth": None},
    {"q": "Who is the primary author of the A-Ware Research report?", "type": "rag", "truth": None},
    {"q": "What was the final YOLO mAP50 precision score achieved during training?", "type": "rag", "truth": None},
    {"q": "According to the README, what specific embedding model is used under the hood?", "type": "rag", "truth": None},

    # Math
    {"q": "If I take half of the total boxes in the warehouse (which is 1844) and multiply it by 3, what is the exact mathematical result?", "type": "math", "truth": None},
]

# CRUD Tests
crud_queries = [
    {"q": "Move 5 boxes from Rack 1 to Rack 2.", "allow_changes": False},
    {"q": "Register a brand new 'forklift' at Rack 5, Aisle 3, shelf level 1.", "allow_changes": True},
    {"q": "Delete the forklift we just registered from Rack 5.", "allow_changes": True}
]

# Context Tests
context_queries = [
    "How many crates do we have in Aisle 4?",
    "Can you list their exact rack locations?",
    "What about the barrels there?"
]

def run_tests():
    print("Initializing Engine...")
    engine = AWereEngine()
    
    results = []

    print("\\n--- Running Standard Tests ---")
    for item in queries:
        print(f"\\nQ: {item['q']}")
        gt = get_ground_truth(item["type"], item["truth"]) if item["type"] == "sql" else "Doc/Math"
        
        events = list(engine.process_query(item["q"], [], [], allow_changes=False))
        ans = events[-1][1].get("final_response", "")
        
        print(f"GT: {gt}")
        print(f"AI: {ans[:200]}...")
        
        results.append({
            "Question": item['q'],
            "Ground Truth": gt,
            "AI Output": ans
        })

    print("\\n--- Running Context Tests ---")
    history = []
    for q in context_queries:
        print(f"\\nQ: {q}")
        events = list(engine.process_query(q, [], history, allow_changes=False))
        # state extraction
        for node_name, state in events:
            if node_name == "contextualize":
                print("Contextualized to:", state.get("standalone_query"))
        
        ans = events[-1][1].get("final_response", "")
        print(f"AI: {ans[:200]}...")
        
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": ans})
        
        results.append({
            "Question": f"[Context] {q}",
            "Ground Truth": "Contextual routing",
            "AI Output": ans
        })

    print("\\n--- Running CRUD Tests ---")
    for item in crud_queries:
        print(f"\\nQ: {item['q']} (Allow Changes: {item['allow_changes']})")
        events = list(engine.process_query(item["q"], [], [], allow_changes=item["allow_changes"]))
        ans = events[-1][1].get("final_response", "")
        print(f"AI: {ans[:200]}...")
        
        results.append({
            "Question": f"[CRUD allow={item['allow_changes']}] {item['q']}",
            "Ground Truth": "Depends on toggle",
            "AI Output": ans
        })

    # Generate Markdown Report
    print("\\nGenerating Report...")
    with open("C:/Users/korla/.gemini/antigravity/brain/c903fb22-efd1-454d-b587-e0e533a45000/experiment_results.md", "w", encoding="utf-8") as f:
        f.write("# Backend Testing Report\\n\\n")
        f.write("## Ground Truth vs. App Output\\n\\n")
        for r in results:
            f.write(f"### Q: {r['Question']}\\n")
            f.write(f"**Ground Truth:** `{r['Ground Truth']}`\\n\\n")
            f.write(f"**AI Output:**\\n{r['AI Output']}\\n\\n")
            f.write("---\\n")
        f.write("## Reflection\\n")
        f.write("*(Reflection will be populated by the AI agent based on this report)*\\n")
        
    print("Testing Complete.")

if __name__ == "__main__":
    run_tests()

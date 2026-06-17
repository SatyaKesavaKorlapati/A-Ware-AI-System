import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-3.1-flash-lite', temperature=0.2)
sys_prompt = '''You are the SQL Inventory Agent. You have access to a SQLite database 'inventory'.
Schema: inventory(id, prim_path, name, category, x, y, z, rack_id, physical_aisle, shelf_level, last_updated)

CRITICAL RULES:
1. The `category` column uses singular nouns EXACTLY matching these: 'box', 'sign', 'rack', 'floor', 'bottle', 'bracket', 'crate', 'pillar', 'barrel', 'lamp', 'barcode', 'wire', 'cone', 'extinguisher', 'forklift', 'cart', 'bucket', 'fuse_box', 'emergency_board', 'paper_note', 'floor_decal', 'pallet'.
2. ALWAYS use singular terms for category filtering (e.g. use 'forklift' not 'forklifts', 'box' not 'boxes'). 
3. Use the `LIKE` operator if you are unsure.

Safety rule: allow_changes=False.
If False, you MUST ONLY generate SELECT queries.
If True, you may generate INSERT/UPDATE/DELETE queries.

You MUST output your response in the following strict JSON format:
{
    "sql_query": "SELECT count(*) FROM inventory WHERE category = 'box';"
}
'''
print("--- TEST 1: Location ---")
res1 = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content='can you specify its exact location (for the forklift)')])
print(res1.content)

print("--- TEST 2: Breakdown ---")
res2 = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content='break down the boxes by specific storage zone')])
print(res2.content)

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-3.1-flash-lite', temperature=0.2)
sys_prompt = '''You are the SQL Inventory Agent. You have access to a SQLite database 'inventory'.
Schema: inventory(id, prim_path, name, category, x, y, z, rack_id, physical_aisle, shelf_level, last_updated)

Safety rule: allow_changes=False.
If False, you MUST ONLY generate SELECT queries.
If True, you may generate INSERT/UPDATE/DELETE queries.

You MUST output your response in the following strict JSON format:
{
    "sql_query": "SELECT count(*) FROM inventory WHERE category = 'box';"
}
Do NOT wrap it in markdown. Do NOT explain. If you refuse, output:
{ "sql_query": "REFUSE: Safety toggle is OFF." }
'''
res = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content='How many forklifts are there?')])
content = res.content
if isinstance(content, list):
    content = content[0].get("text", "")
print("RAW LLM OUTPUT:", content)

try:
    data = json.loads(content)
    print("PARSED QUERY:", data.get("sql_query"))
    import sqlite3
    conn = sqlite3.connect('database/warehouse_inventory.db')
    cursor = conn.cursor()
    cursor.execute(data.get("sql_query"))
    print("DB RESULT:", cursor.fetchall())
except Exception as e:
    print("ERROR:", e)

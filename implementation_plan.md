# Migrate to SQL and Multi-Agent Architecture

This plan outlines the major architectural upgrade to shift the A-Ware system from a static JSON+ChromaDB approach to a dynamic SQL database managed by a Multi-Agent LangGraph system, while repurposing RAG (ChromaDB) for unstructured knowledge.

## Background & Problem
Currently, the system relies on parsing a large `metadata.json` file and indexing it into ChromaDB. While ChromaDB is excellent for semantic search on unstructured text, it is not ideal for structured, tabular data (like inventory counts, spatial coordinates, and rack assignments). Furthermore, RAG systems are read-only; they cannot dynamically update state. By migrating to a SQL database for inventory, we unlock CRUD capabilities.

At the same time, we want the system to be able to answer questions about its own architecture, the warehouse details, and its capabilities to impress evaluators. For this unstructured knowledge, we will generate synthetic manuals and keep ChromaDB.

## Proposed Architecture: Parallel Multi-Agent LangGraph

Instead of a linear pipeline, we will build an advanced **Multi-Agent LangGraph**. A Supervisor (Router) Agent will interpret the user's intent and can delegate to **multiple specialized sub-agents simultaneously** if the query is complex.

1. **SQL Inventory Agent:** Equipped with tools to dynamically query, insert, update, or delete rows in the SQL database.
2. **Vision Agent:** Analyzes uploaded images for objects using YOLO.
3. **Knowledge / RAG Agent:** Queries ChromaDB to answer questions based on ingested manuals.

### Parallel & Sequential Execution
If a user asks a multi-intent query like: *"Who owns this warehouse and how many boxes are in rack 5?"*
1. **Parallel:** The Supervisor will identify both intents and trigger the `SQL_Agent` and `RAG_Agent` to run **in parallel**. 
2. **Sequential Synthesis:** Once both parallel agents finish gathering their respective data, the graph will converge sequentially on a `Synthesis_Agent` (or Final Response Node) to combine the database numbers and the manual text into one cohesive, natural answer for the user.

## Proposed Changes

### 1. Database Layer (SQL for Inventory)
#### [NEW] `database/sql_manager.py`
Create a new module to handle SQLite connections. It will define the schema:
- `id` (Primary Key)
- `prim_path` (Text)
- `name` (Text)
- `category` (Text)
- `x`, `y`, `z` (Real - Coordinates)
- `rack_id` (Integer)
- `physical_aisle` (Integer)
- `shelf_level` (Integer)
- `last_updated` (Timestamp)

#### [NEW] `database/migrate_json_to_sql.py`
A script to read `MDta/warehouse_rag_metadata_full.json` and perform the initial bulk insert into the new SQLite database.

### 2. Knowledge Base (RAG for Manuals)
#### [NEW] `data/manuals/system_manual.md`
Generate synthetic documentation containing:
- **Warehouse Name:** KHouse
- **Owner:** SatyaKesava
- **Location:** Amaravathi
- **Sim Env:** NVIDIA Isaac Sim
- **Project Details:** Capabilities, functions, architecture, and implementation details.

#### [MODIFY] `data/data_ingestion.py`
Update ingestion to index the `system_manual.md` into ChromaDB instead of the massive `metadata.json`.

### 3. Multi-Agent Engine
#### [MODIFY] `app/engine.py`
Refactor the LangGraph implementation:
- Define SQL Tool functions.
- Create `SQL_Agent`, `Vision_Agent`, and `RAG_Agent` nodes.
- **[NEW]** Create a `Supervisor` node that outputs a list of required agents (e.g., `["sql", "rag"]`). LangGraph will use this list to broadcast execution to those nodes in parallel.
- **[NEW]** Create a `Final_Synthesis` node that runs sequentially after the specialized agents finish to format the final answer.

### 4. Backend Integration
#### [MODIFY] `app/main.py`
Update the streaming endpoints to handle parallel node execution and stream status accurately to the frontend (e.g., "Running SQL & RAG Agents...").

## Verification Plan
### Automated & Manual Verification
1. Run `migrate_json_to_sql.py` and verify all items are in SQLite.
2. Run `data_ingestion.py` to ingest the new manuals into ChromaDB.
3. Query the frontend: "How many boxes are in rack 8?" (Verify ONLY SQL Agent triggers).
4. Query the frontend: "Who is the owner of this warehouse and what technologies are used?" (Verify ONLY RAG Agent triggers).
5. **Complex Query:** "Who owns this warehouse and how many pallets are in aisle 2?" (Verify BOTH SQL and RAG Agents trigger in parallel, and synthesis node combines them).

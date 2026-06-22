# A-Ware AI: Feature Compendium

This document is a comprehensive technical reference for every feature, skill, and capability built into the A-Ware System across its Backend, Frontend, and Multi-Agent infrastructure.

---

## 🧠 Backend Capabilities & Agentic RAG
The core logic runs on a sophisticated **Multi-Agent LangGraph Supervisor**, dynamically routing user intents across parallel workers.

### 🤖 Specialized Sub-Agents
1. **SQL Inventory Agent:** Direct CRUD access to the SQLite spatial database.
2. **Vision Agent (YOLO):** Inspects incoming image feeds using a custom-trained YOLO model to detect boxes, pallets, and warehouse geometry.
3. **RAG Specs Agent:** Queries ChromaDB specifically for hardware limitations, maximum weights, and dimensional specifications.
4. **RAG Manuals Agent:** Queries ChromaDB for standard operating procedures, assembly steps, and safety protocols.

### 🛡️ Core Engine Mechanics
- **Parallel Execution:** Can dispatch multiple agents simultaneously for compound questions.
- **Synthesizer Node:** Takes raw outputs from multiple agents and weaves them into a conversational final response.
- **Database Modifying Mode Lock:** A global variable flag that physically prevents the SQL Agent from executing mutating commands if the user toggles safety mode off.
- **Automatic History Tracking:** The engine maintains an automatic `db_history.py` shadow log that records snapshots before and after major mutations.

---

## 💾 SQL Skills (Inventory Management)
The `app/sql_skills.py` defines the absolute limits of what the SQL Agent can physically achieve. Every "drop" of logic is listed here:

1. `get_inventory`: Fetches item details, optionally filtered by category or rack.
2. `add_inventory`: Inserts items. Uses **Greedy Distribution** to automatically split massive shipments across multiple available racks if a single rack hits its capacity limit.
3. `remove_inventory`: Safely deletes rows. Will actively refuse to partially delete if count mismatches without user confirmation.
4. `move_inventory`: Transfers items physically from one rack ID to another.
5. `rename_inventory`: Updates the `category` string for matching items (mass renaming).
6. `add_rack`: Spawns a new rack in the environment, enforcing unique ID constraints and calculating physical spatial aisles.
7. `update_rack_capacity`: Dynamically overrides the default 600-item physical limitation of a rack.
8. `get_racks`: Audits racks to show current capacities and item occupancies.
9. `delete_rack`: Deletes a rack, but strictly refuses to delete if the rack is not completely empty.
10. `sort_warehouse`: An advanced algorithm that dense-packs the entire warehouse, shifting items mathematically to free up as many empty racks as possible.
11. `group_warehouse`: Iterates over every category and isolates them so one rack holds *only* one item type. Features an **Interactive Permission Request** loop if it runs out of physical rack space during calculation.
12. `view_history`: Dumps the JSON metadata of all historical snapshots taken during the current session.
13. `rollback_database`: Standard Undo command. Reverts the DB to the previous snapshot.
14. `redo_database`: Standard Redo command. Re-applies the last reverted snapshot.
15. `restore_snapshot`: Directly targets a specific snapshot ID to instantly revert the warehouse to that exact point in time.

### 🌐 General Skills & Web Access
The AI features built-in tools to seamlessly connect to the outside internet, granting it live web access:
1. `calculate`: A safe math evaluation sandbox.
2. `get_current_time`: Injects system chronos.
3. `search_wikipedia`: Standard Wikipedia integration.
4. `web_search`: Live Web Search tool (Tavily API integration) allowing the AI to scrape live websites, search for external data, and answer real-time queries outside its RAG knowledge base.

---

## 🖥️ Frontend Architecture & UI Elements

### 🎨 Visual & Interactive Aesthetic
- **Glassmorphism UI:** Complete overhaul using Vanilla CSS to implement frosted glass panels, translucent dark modes, and soft blurring.
- **Dynamic Rainbow Glow:** Edge-lit indicators that pulse and spin while the LLM is actively streaming a response.
- **Smart Chat Typist:** Message typing animations for real-time streaming, with instant-load logic when scrolling up into historical messages.

### 🧩 Custom Markdown Interceptors (ReactMarkdown)
Instead of rendering plain text, the frontend actively parses the AI's output strings to inject **interactive React components** into the chat stream:
- **Interactive Timeline Widget:** When the AI outputs a markdown block tagged with `timeline`, the UI intercepts it and renders a full-fledged Glassmorphism interface. Users can click on database snapshots, view timestamps, and press a physical "Restore State" button that dispatches a silent command back to the LLM.
- **Interactive Prompt Buttons:** When the AI needs permission (like adding racks during a grouping loop), it outputs `[Yes]` and `[No]` markdown links. The UI catches these and styles them as interactive, colored UI buttons that automatically submit the decision to the backend.

### 🗺️ Map & Control Panel
- **Real-Time 2D Warehouse Map:** A visual grid rendering of the SQLite database coordinates, showing spatial relationships of racks and aisles.
- **5-Second Polling & Force Refresh:** The map automatically pings the SQLite backend every 5 seconds to show items moving in real-time as the AI executes SQL skills.
- **Dynamic Visual Legend:** A sidebar that analyzes the database to assign unique visual color-hashes and shape icons to categories dynamically as they are created.
- **Voice Mode:** Integrated browser Speech Recognition API. Users can click the microphone icon to transcribe spoken commands natively.

### 🗨️ Chat Session Management
- **Session History:** The application persists previous conversations and loads them instantly.
- **Custom Renaming & Emojis:** The UI auto-generates titles and emojis for new chats, but users can interactively rename their sessions and pick custom icons using an animated emoji picker.

---

## 🔍 Vision System (YOLO26 Integration)
The intelligence platform is supported by a state-of-the-art synthetic vision model:
- **YOLO26-L Architecture**: High-resolution (1280px) training ensures hyper-accurate detection of warehouse assets.
- **Structural Class Filtering**: The pipeline dynamically filters out non-essential structural classes (floor, wall, ceiling, background) to boost item recall by 2.3x.
- **Aerial & Multi-View Detection**: Uses data from 22 static warehouse cameras and 1 scripted drone camera to allow the AI to "see" the warehouse from all angles.

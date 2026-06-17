# A-Ware System Manual & Architecture Guide

## 1. Overview
Welcome to the A-Ware System. This system is a Multimodal Warehouse Intelligence Platform.

## 2. General Information
- **Warehouse Name:** KHouse
- **Warehouse Owner:** SatyaKesava
- **Warehouse Location:** Amaravathi
- **Simulation Environment:** NVIDIA Isaac Sim
- **Architecture:** Parallel Multi-Agent LangGraph System
- **Core LLM:** gemini-3.1-flash-lite

## 3. Capabilities & Functions
The system is capable of:
- **Vision Processing:** Upload images of the warehouse and the system uses YOLO26-L to detect objects and answer spatial questions based on those detections.
- **SQL Inventory Management:** Querying, inserting, updating, and deleting structured inventory records stored in SQLite. (Requires "Allow Changes" permission to modify).
- **RAG Knowledge Retrieval:** Reading from manuals and unstructured documentation to answer questions about the warehouse's owner, structure, or technologies using ChromaDB.

## 4. Technical Stack

### Frontend
- **Framework:** Next.js, React
- **Styling:** CSS3 Glassmorphism

### Backend
- **Framework:** Python, FastAPI
- **Database:** ChromaDB (Vector DB), SQLite (Inventory DB)
- **Simulation:** NVIDIA Isaac Sim, USD, omni.replicator.core

### 🤖 AI Models Config
- **LLM:** gemini-3.1-flash-lite
- **Embedding:** gemini-embedding-2
- **Vision:** YOLO26-L (LAR1r)

## 5. Security & Safety
- Database modification tools are restricted unless the explicit `allow_changes` flag is set by the user from the frontend. Read-only queries are always permitted.

## 6. Advanced Engine Features
The Cognitive Engine natively supports complex, multi-step CRUD operations utilizing robust SQL subqueries and dynamic arrays:
- **Multi-Query Execution**: Automatically chains multiple SQL queries into a unified atomic action for complex spatial reasoning and bulk operations.
- **Mass Shifts**: Seamlessly relocates bulk subsets of items (e.g., relocating entire categories) while dynamically remapping `physical_aisle` relations.
- **Mass Deletion**: Securely isolates and purges specific items via parameter-based subsets.
- **Complex Multi-Spacing**: Generates precision positional updates across the X, Y, and Z axes incrementally to avoid shelf collisions.

## 7. UI Features & Usage
The application interface provides several advanced interactive features:
- **Apple-Style Glassmorphism UI:** A sleek, fully responsive dark-mode chat interface with frosted glass sidebars.
- **Image Upload:** You can drag and drop images or use the attachment button to upload warehouse photos. The Vision Agent will automatically analyze these images.
- **Safety Toggle (Allow Changes):** A dedicated toggle switch to grant or revoke write permissions to the database. When enabled, you can ask the agent to add, move, or delete inventory.
- **Dynamic Rainbow Glow:** A beautiful, non-intrusive animated rainbow edge glow that can be toggled via the user profile.
- **Custom Chat Emojis:** Sessions automatically assign custom emojis, which you can manually edit with a 15+ animated emoji picker.
- **Interactive Sidebar:** Drag-to-resize support, compact-mode collapsing, and centered adaptive layouts to manage chat sessions.

## 8. Visual Item Mapping (100+ Classes)
The warehouse map UI dynamically supports an infinite number of item categories. Instead of hardcoding visual representations, the system uses a **deterministic hashing algorithm** to map any given item category to a unique combination of **10 Shapes** and **10 Colors**.
This creates 100 distinct visual classes for rendering on the physical layout map. 
The mapping can be viewed in real-time using the **Legend** button on the bottom right of the map, which displays a directory-style breakdown of all currently active items in the warehouse grouped by their assigned Shape and Color.

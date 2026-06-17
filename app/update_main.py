import re

def update_main():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "allow_changes: bool = Form(False)" not in content:
        content = content.replace(
            "use_yolo_only: bool = Form(False),",
            "use_yolo_only: bool = Form(False),\n    allow_changes: bool = Form(False),"
        )
        content = content.replace(
            "engine.process_query(query, images_to_process, parsed_history, use_yolo_only):",
            "engine.process_query(query, images_to_process, parsed_history, use_yolo_only, allow_changes):"
        )
        
        status_map_old = """        status_map = {
            "analyze_vision": "Running Vision Agent (YOLO/ReAct)...",
            "retrieve_context": "Retrieving spatial context from ChromaDB...",
            "generate_response": "Synthesizing response with Gemini 3.1..."
        }"""
        
        status_map_new = """        status_map = {
            "supervisor": "Supervisor routing query...",
            "sql_agent": "SQL Agent querying inventory database...",
            "rag_agent": "RAG Agent retrieving system manuals...",
            "vision_agent": "Vision Agent analyzing images with YOLO...",
            "final_synthesis": "Synthesizing final response..."
        }"""
        
        content = content.replace(status_map_old, status_map_new)
        
        # In case the old status map was slightly different
        if "Supervisor routing query" not in content:
            content = content.replace('"analyze_vision":', '"supervisor": "Supervisor routing query...",\n            "sql_agent": "SQL Agent querying inventory database...",\n            "rag_agent": "RAG Agent retrieving system manuals...",\n            "vision_agent": "Vision Agent analyzing images with YOLO...",\n            "final_synthesis": "Synthesizing final response...",\n            "analyze_vision":')

    with open("app/main.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_main()

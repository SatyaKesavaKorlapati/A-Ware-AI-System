import os

def rewrite_engine():
    with open("app/engine.py", "r", encoding="utf-8") as f:
        content = f.read()

    tools_code = """
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

@tool
def calculate(expression: str) -> str:
    \"\"\"Evaluates a mathematical expression (e.g., '10 + 5 * 2'). Do not use this for SQL database operations.\"\"\"
    try:
        return str(eval(expression, {"__builtins__": None}, {}))
    except Exception as e:
        return f"Error evaluating math: {e}"

@tool
def get_current_time() -> str:
    \"\"\"Returns the current local date and time.\"\"\"
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

TOOLS = [calculate, get_current_time]
"""

    if "def calculate(" not in content:
        # insert right after YOLO_TO_METADATA_CATEGORY
        content = content.replace("def reducer_list(a: list, b: list) -> list:", tools_code + "\ndef reducer_list(a: list, b: list) -> list:")

    old_synthesis_body = """
        response = self._extract_text(self.llm.invoke(messages).content)
        return {"final_response": response}
"""

    new_synthesis_body = """
        agent = create_react_agent(self.llm, TOOLS)
        result = agent.invoke({"messages": messages})
        response = self._extract_text(result["messages"][-1].content)
        return {"final_response": response}
"""

    content = content.replace(old_synthesis_body, new_synthesis_body)

    with open("app/engine.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    rewrite_engine()
    print("Added tools to final synthesis.")

import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

@tool
def calculate(expression: str) -> str:
    """Evaluates a basic mathematical expression using python's eval()."""
    try:
        return str(eval(expression, {"__builtins__": None}, {}))
    except Exception as e:
        return f"Error: {e}"

@tool
def get_current_time() -> str:
    """Returns the current date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

llm = ChatGoogleGenerativeAI(model='gemini-3.1-flash-lite', temperature=0.2)
tools = [calculate, get_current_time]
agent = create_react_agent(llm, tools)

res = agent.invoke({"messages": [HumanMessage(content="What is 154 * 82? Also what time is it?")]})
print("Final Output:", res["messages"][-1].content)

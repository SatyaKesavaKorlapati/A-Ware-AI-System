from langchain_core.tools import tool
import requests
from bs4 import BeautifulSoup
import wikipediaapi
from datetime import datetime

@tool
def calculate(expression: str) -> str:
    """Safely evaluates a mathematical expression."""
    try:
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return "Error: Invalid characters in math expression."
        return str(eval(expression, {"__builtins__": None}, {}))
    except Exception as e:
        return f"Calculation error: {e}"

@tool
def get_current_time() -> str:
    """Returns the current local date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def search_wikipedia(query: str) -> str:
    """Searches Wikipedia for general knowledge information."""
    try:
        wiki = wikipediaapi.Wikipedia('A-Ware Assistant (support@example.com)', 'en')
        # We should use web_search as a fallback, but here we can try a simple heuristic or just warn
        page = wiki.page(query)
        if not page.exists():
            return "No exact Wikipedia page found. Consider using the web_search tool instead for complex queries."
        return page.summary[0:1500]
    except Exception as e:
        return f"Could not find information on Wikipedia: {e}"

@tool
def web_search(query: str) -> str:
    """Searches the web for current events, news, or facts using Tavily."""
    try:
        import requests
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: TAVILY_API_KEY not found in environment."
            
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 3
        }
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
        
        data = res.json()
        results = data.get("results", [])
        
        if not results:
            return "No results found on the web."
            
        out = []
        for r in results:
            title = r.get("title", "Result").strip()
            snippet = r.get("content", "").strip()
            # Truncate overly long snippets just in case
            if len(snippet) > 500:
                snippet = snippet[:497] + "..."
            out.append(f"{title}: {snippet}")
            
        return "\n".join(out)
    except Exception as e:
        return f"Web search failed: {e}"

# Export all available general tools
GENERAL_TOOLS = [calculate, get_current_time, search_wikipedia, web_search]

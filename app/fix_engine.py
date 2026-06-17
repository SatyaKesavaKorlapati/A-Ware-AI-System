import os

def fix_engine():
    with open("app/engine.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Add _extract_text helper
    helper = """
    def _extract_text(self, content) -> str:
        if isinstance(content, list):
            return content[0].get("text", "")
        return str(content)
"""
    if "_extract_text" not in content:
        content = content.replace(
            "def _extract_categories(self, query: str) -> list[str]:",
            helper.strip() + "\n\n    def _extract_categories(self, query: str) -> list[str]:"
        )

    # Fix node_supervisor
    content = content.replace(
        "response = self.llm.invoke(messages).content.strip()",
        "response = self._extract_text(self.llm.invoke(messages).content).strip()"
    )

    # Fix node_sql_agent
    content = content.replace(
        "response = self.llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=query)]).content.strip()",
        "response = self._extract_text(self.llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=query)]).content).strip()"
    )

    # Fix node_final_synthesis
    content = content.replace(
        "response = self.llm.invoke(messages).content",
        "response = self._extract_text(self.llm.invoke(messages).content)"
    )

    with open("app/engine.py", "w", encoding="utf-8") as f:
        f.write(content)

def fix_main():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    old_prompt = "Summarize this query into a concise 2-4 word Title for a chat session. Do not use quotes or punctuation. Return ONLY the title. Query:"
    new_prompt = "Summarize this query into a concise 2-4 word Title for a chat session, and prepend a single relevant emoji. Do not use quotes or punctuation. Return ONLY the emoji and title. Query:"
    
    content = content.replace(old_prompt, new_prompt)
    
    with open("app/main.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    fix_engine()
    fix_main()
    print("Fixed engine.py and main.py")

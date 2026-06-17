import sys
from app.sql_skills import create_sql_tools

def test_skills():
    print("Testing SQL Skills Logic Directly...")
    
    tools_allow = {t.name: t for t in create_sql_tools(allow_changes=True)}
    tools_deny = {t.name: t for t in create_sql_tools(allow_changes=False)}
    
    print("\n--- 1. Test Get (Empty or Current) ---")
    print(tools_allow["get_inventory"].invoke({"category": "laptop"}))
    
    print("\n--- 2. Test Safe Add (100 laptops) ---")
    print(tools_allow["add_inventory"].invoke({"category": "laptop", "count": 100, "rack_id": 1}))
    
    print("\n--- 3. Test Overflow Add (600 laptops to same rack) ---")
    print(tools_allow["add_inventory"].invoke({"category": "laptop", "count": 600, "rack_id": 1}))
    
    print("\n--- 4. Test Get After Add ---")
    print(tools_allow["get_inventory"].invoke({"category": "laptop"}))
    
    print("\n--- 5. Test Move (50 laptops to Rack 2) ---")
    print(tools_allow["move_inventory"].invoke({"category": "laptop", "count": 50, "from_rack": 1, "to_rack": 2}))
    
    print("\n--- 6. Test Get After Move ---")
    print(tools_allow["get_inventory"].invoke({"category": "laptop"}))
    
    print("\n--- 7. Test Remove (150 laptops) ---")
    print(tools_allow["remove_inventory"].invoke({"category": "laptop", "count": 150}))
    
    print("\n--- 8. Test Safety Toggle (Denied Add) ---")
    print(tools_deny["add_inventory"].invoke({"category": "laptop", "count": 10}))
    
    print("\n--- DONE ---")

if __name__ == "__main__":
    test_skills()

# A-Ware AI: Demo Script & Interview Questions

This document contains 40 solid, battle-tested questions and commands that perfectly showcase the complex reasoning, system logic, and dynamic SQL tools built into the A-Ware AI. You can use these during your interview or product demo to prove the robustness of the engine.

They are divided into **Easy**, **Medium**, and **Hard** categories. Expected answers are provided so you know exactly how the system will react during a live demo.

---

## 🟢 Easy: Basic Operations
*These questions demonstrate the core CRUD (Create, Read, Update, Delete) capabilities of the AI without requiring multi-step logic.*

1. **User:** "How many items are currently in Rack 5?"
   * **Expected Answer:** "Inventory Found: - Category: [ItemName], Rack: 5, Aisle: [X], Count: [Y]..."
2. **User:** "Add 250 'Laptops' to the warehouse."
   * **Expected Answer:** "Success: Added 250 Laptops (250 in Rack [X])."
3. **User:** "Remove 100 'Laptops' from the inventory."
   * **Expected Answer:** "Success: Removed 100 Laptops."
4. **User:** "What is the current maximum capacity of Rack 12?"
   * **Expected Answer:** "The current maximum capacity for Rack 12 is 600 items."
5. **User:** "Move 50 'Keyboards' from Rack 1 to Rack 2."
   * **Expected Answer:** "Success: Moved 50 Keyboards from Rack 1 to Rack 2."
6. **User:** "Create a new empty rack."
   * **Expected Answer:** "Success: Added Rack [Next_Available_ID] with capacity 600 in Aisle [X]."
7. **User:** "Rename all 'boxes' to 'shipping boxes'."
   * **Expected Answer:** "Success: Renamed [X] 'boxes' items to 'shipping boxes'."
8. **User:** "Give me a complete summary of all inventory in the warehouse."
   * **Expected Answer:** *Provides a complete bulleted list of all items grouped by Category and Rack.*
9. **User:** "Delete Rack 15." *(Assuming it is empty)*
   * **Expected Answer:** "Success: Rack 15 has been permanently deleted from the warehouse."
10. **User:** "Update the capacity of Rack 4 to 800."
    * **Expected Answer:** "Success: Updated Rack 4 capacity to 800."
11. **User:** "Are there any 'Pencils' in the warehouse right now?"
    * **Expected Answer:** *Lists the racks containing pencils or replies "No items found matching the criteria."*
12. **User:** "Add 500 'Mice' specifically to Rack 6."
    * **Expected Answer:** "Success: Added 500 Mice to Rack 6."
13. **User:** "Remove all 'shipping boxes' from Rack 2 specifically."
    * **Expected Answer:** "Success: Removed [X] shipping boxes."
14. **User:** "Move all items from Rack 3 to Rack 4."
    * **Expected Answer:** "Success: Moved [X] items from Rack 3 to Rack 4."
15. **User:** "Rename 'Mice' to 'Computer Mice' only in Rack 6."
    * **Expected Answer:** "Success: Renamed [X] 'Mice' items to 'Computer Mice'."

---

## 🟡 Medium: Multi-Step & System Logic
*These questions trigger the AI's safety rails, collision detection, and algorithms.*

16. **User:** "Create a new Rack 20 with a custom capacity of 1000."
    * **Expected Answer:** "Success: Added Rack 20 with capacity 1000 in Aisle 10."
17. **User:** "Add 3000 'Staples' to the warehouse."
    * **Expected Answer:** "Success: Added 3000 Staples ([X] in Rack 1, [Y] in Rack 2...)." *(Shows Greedy Auto-Distribution)*
18. **User:** "Add 800 'Desks' to Rack 1."
    * **Expected Answer:** "Error: Rack 1 currently has [X] items. Adding 800 exceeds its 600 limit."
19. **User:** "Remove 500 'Monitors'." *(When only 400 exist)*
    * **Expected Answer:** "Error: Only 400 Monitors found. Refusing to partially delete without confirmation."
20. **User:** "Empty Rack 5 completely and distribute its contents across the warehouse."
    * **Expected Answer:** "Success: Moved [X] items from Rack 5 ([Y] to Rack 1, [Z] to Rack 2...)."
21. **User:** "Delete Rack 2." *(When it still has items in it)*
    * **Expected Answer:** "Error: Rack 2 is not empty. It currently contains [X] items. You must move or remove these items before deleting the rack."
22. **User:** "Create a new Rack 1."
    * **Expected Answer:** "Error: Rack 1 already exists. Do you want to use a different ID/name? Please specify."
23. **User:** "Add 400 'Chairs' to Rack 3, then immediately move 200 of them to Rack 4."
    * **Expected Answer:** "I have added 400 Chairs to Rack 3, and then successfully moved 200 of them to Rack 4."
24. **User:** "Increase the capacity of Racks 1, 2, and 3 to 1000 each."
    * **Expected Answer:** "Success: Updated capacity to 1000 for Racks 1, 2, and 3."
25. **User:** "Find the rack with the most 'Notebooks' and rename them to 'Spiral Notebooks'."
    * **Expected Answer:** "I found that Rack [X] has the most Notebooks. I have successfully renamed them to Spiral Notebooks."
26. **User:** "Delete Rack 15, but only if it is completely empty."
    * **Expected Answer:** "Rack 15 is empty, so I have successfully deleted it." *(or)* "Rack 15 currently holds items, so I did not delete it."
27. **User:** "Move exactly 150 'Pencils' from Rack 13 to Rack 14."
    * **Expected Answer:** "Success: Moved 150 Pencils from Rack 13 to Rack 14."
28. **User:** "Add 500 'Backpacks' to Rack 7. If it hits the capacity limit, increase the limit to 800 and try again."
    * **Expected Answer:** "I initially hit the capacity limit, so I increased Rack 7's capacity to 800. The 500 Backpacks have now been successfully added."
29. **User:** "Re-categorize all 'Pens' and 'Pencils' under a single category called 'Writing Utensils'."
    * **Expected Answer:** "I have successfully renamed [X] Pens and [Y] Pencils to 'Writing Utensils'."
30. **User:** "Empty Rack 10 and then permanently delete it from the system."
    * **Expected Answer:** "I have distributed the items from Rack 10 to other available racks. Now that it is empty, I have permanently deleted Rack 10."

---

## 🔴 Hard: Advanced Scenarios & Deep Reasoning
*These questions represent the absolute peak of the AI's capabilities, chaining together dynamic capacity manipulation, context awareness, and multi-step conditionals.*

> [!TIP]
> **The Crayon Saga**
> The following four questions represent a continuous, highly complex conversational flow that you should run sequentially in your demo. The answers provided are the exact expected behaviors.

31. **User:** "Create a new rack 14."
    * **Expected Answer:** "Rack 14 has been successfully created with a capacity of 600."
32. **User:** "Can you add 650 'Crayons' to rack 14 by increasing its capacity to 700?"
    * **Expected Answer:** "Rack 14's capacity has been increased to 700, and 650 crayons have been successfully added."
33. **User:** "Add 56 crayons to rack 13."
    * **Expected Answer:** "Done! I've added 56 crayons to rack 13 for you."
34. **User:** "Now remove all the crayons in the inventory and delete the whole rack if it becomes empty by removing the crayons."
    * **Expected Answer:** "All crayons have been removed from the inventory. Rack 14 was empty after the removal and has been deleted, while Rack 13 remains as it still contains pencils."

### More Hard Questions:
35. **User:** "The warehouse is receiving a massive shipment of 5000 'Water Bottles'. Automatically create enough new racks with 1000 capacity each to hold them, then add the items."
    * **Expected Answer:** "I have created 5 new racks (Racks 21-25) each with 1000 capacity, and successfully distributed the 5000 Water Bottles into them."
36. **User:** "Find all racks that are currently at exactly 100% capacity, and increase their capacities by 200 to give them breathing room."
    * **Expected Answer:** "I found that Racks [X] and [Y] were at 100% capacity. I have updated both of their capacities to [Old Capacity + 200]."
37. **User:** "Consolidate all 'Safety Goggles' scattered across the warehouse into Rack 1. If Rack 1 cannot hold them all, increase its capacity to exactly match the total count of Safety Goggles."
    * **Expected Answer:** "There are [Total] Safety Goggles. I increased Rack 1's capacity to [Total] and moved all Safety Goggles into Rack 1."
38. **User:** "I want to clear out Aisle 1 (Racks 1 and 2). Automatically distribute all their items to the rest of the warehouse, and then delete both racks."
    * **Expected Answer:** "I have successfully moved all items out of Racks 1 and 2 to other locations in the warehouse. Both racks are now empty and have been deleted."
39. **User:** "Attempt to create Rack 5. When it fails, catch the error, find the next available sequential Rack ID, create it with 1200 capacity, and fill it entirely with 'Hard Drives'."
    * **Expected Answer:** "As expected, creating Rack 5 failed because it already exists. Instead, I created Rack [Next_ID] with 1200 capacity and added 1200 Hard Drives to it."
40. **User:** "Run a complete audit: Tell me the total number of items, the total unused capacity in the warehouse, and the ID of the rack with the most empty space."
    * **Expected Answer:** "Audit Complete: The warehouse currently holds [X] total items. There is [Y] total unused capacity across all racks. The rack with the most empty space is Rack [Z] with [W] available slots."
41. **User:** "We just received 1,000,000 'Microchips'. Calculate how much overflow space we need beyond our current capacity, automatically create enough new racks at 10,000 capacity each to cover the overflow, and distribute the entire shipment."
    * **Expected Answer:** "The warehouse only had [X] available slots, meaning we had an overflow of [Y]. I successfully created [Z] new racks with a capacity of 10,000 each, and distributed all 1,000,000 Microchips perfectly across the warehouse."

---

## 🟣 Interactive UI & Timeline Actions
*These questions demonstrate the latest additions to A-Ware: rich React Markdown component injection (Glass UI widgets) and interactive permission handling.*

42. **User:** "Show me the timeline of recent database changes."
    * **Expected Answer:** *(An interactive Glassmorphism Timeline Widget appears in the chat, displaying all snapshot history. The user can click any historical snapshot and press "Restore State" to instantly revert the SQL database to that point in time).*
43. **User:** "Group all the items in the warehouse by their categories into dedicated racks."
    * **Expected Answer:** "I attempted to group the items... but there aren't enough racks to keep each category isolated... Would you like me to proceed with adding the necessary racks and grouping the items? [Yes] [No]" *(If the user clicks the interactive [Yes] button, the agent automatically executes the command with auto-expansion enabled).*

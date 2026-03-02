import json
import os
from services.ollama_client import OllamaClient

def test_npc_interactions():
    client = OllamaClient()
    
    # 載入 NPC 數據
    with open("data/npcs.json", "r", encoding="utf-8") as f:
        npcs = json.load(f)
        
    test_cases = [
        {
            "npc_id": "npc_staff_filch",
            "quest_name": "擦拭大理石地板",
            "result_data": {"success": True, "rewards": {"money": 10, "exp": 20}}
        },
        {
            "npc_id": "npc_assistant_ron",
            "quest_name": "魔植分類",
            "result_data": {"success": True, "rewards": {"money": 20, "exp": 30, "stat_increase": "INT +1"}}
        },
        {
            "npc_id": "npc_professor_snape",
            "quest_name": "討伐後山史萊姆",
            "result_data": {"success": True, "rewards": {"money": 100, "exp": 100}}
        }
    ]
    
    print("=== NPC 互動敘事測試 ===\n")
    
    for case in test_cases:
        npc_data = npcs.get(case["npc_id"])
        print(f"--- 測試 NPC: {npc_data['name']} ({npc_data['title']}) ---")
        narrative = client.generate_quest_narrative(case["quest_name"], npc_data, case["result_data"])
        print(f"敘事回饋:\n{narrative}\n")

if __name__ == "__main__":
    test_npc_interactions()

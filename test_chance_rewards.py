import sys
import os
from unittest.mock import patch

sys.path.append(os.getcwd())

from core.character import Character
from core.quest_manager import QuestManager
from core.dice import Dice

def test_chance_stat_increase():
    print("=== 驗證機率屬性獎勵機制 ===\n")
    qm = QuestManager()
    quest_id = "quest_assist_krenz"
    
    # --- 測試案例 1: 機率觸發成功 ---
    print("[測試 1] 模擬擲骰成功 (點數 <= 機率)")
    player1 = Character(name="Lucky Student")
    initial_int1 = player1.stats.get("INT", 10)
    
    qm.accept_quest(quest_id)
    qm.active_quests[quest_id]["current_amount"] = 1
    qm.active_quests[quest_id]["completed"] = True
    
    # 模擬必定成功 (回傳 True)
    with patch('core.dice.Dice.check_d100', return_value=True):
        result1 = qm.resolve_quest(player1, quest_id)
        
    print(f"結算結果: {result1.get('rewards')}")
    if player1.stats.get("INT") != initial_int1 + 1:
        print("❌ 測試失敗: 未正確發放屬性獎勵")
        sys.exit(1)
    if "機率觸發" not in result1.get("rewards", {}).get("stat_increase", ""):
        print("❌ 測試失敗: 缺少對應提示訊息")
        sys.exit(1)
    print("✅ 測試通過: 成功獲得 INT +1\n")
    
    # --- 測試案例 2: 機率觸發失敗 ---
    print("[測試 2] 模擬擲骰失敗 (點數 > 機率)")
    player2 = Character(name="Unlucky Student")
    initial_int2 = player2.stats.get("INT", 10)
    
    qm.accept_quest(quest_id)
    qm.active_quests[quest_id]["current_amount"] = 1
    qm.active_quests[quest_id]["completed"] = True
    
    # 模擬必定失敗 (回傳 False)
    with patch('core.dice.Dice.check_d100', return_value=False):
        result2 = qm.resolve_quest(player2, quest_id)
        
    print(f"結算結果: {result2.get('rewards')}")
    if player2.stats.get("INT") != initial_int2:
        print("❌ 測試失敗: 不應發放屬性獎勵但屬性改變了")
        sys.exit(1)
    if "stat_increase" in result2.get("rewards", {}):
        print("❌ 測試失敗: 結算訊息不應包含屬性提升")
        sys.exit(1)
    print("✅ 測試通過: 未獲得 INT，符合機率失敗邏輯\n")
    
    print("✨ 所有驗證測試皆已通過！")

if __name__ == "__main__":
    test_chance_stat_increase()

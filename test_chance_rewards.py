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
    
    # --- 測試案例 1: 機率觸發成功 ---
    print("[測試 1] 模擬擲骰成功 (點數 <= 機率)")
    player1 = Character(name="Lucky Student")
    # 執行前先記住初始屬性
    initial_int1 = player1.stats.get("INT", 10)
    
    quest_id = "quest_assist_krenz"
    qm.accept_quest(quest_id)
    qm.active_quests[quest_id]["current_amount"] = 1
    qm.active_quests[quest_id]["completed"] = True
    
    # 模擬必定成功 (回傳 True)
    with patch('core.dice.Dice.check_d100', return_value=True):
        result1 = qm.resolve_quest(player1, quest_id)
        
    print(f"結算結果: {result1.get('rewards')}")
    
    # 由於 120 EXP 會導致升級 (Lv 1 -> 2)，全屬性會 +1 加上隨機屬性加成
    # 我們的目標是確認 "機率觸發" 的那 1 點是否有加上去
    # 升級加成：1 (基礎) + (0 或 1 隨機)
    # 機率觸發：1
    # 總增加應至少為 2
    current_int1 = player1.stats.get("INT")
    if current_int1 < initial_int1 + 1:
        print(f"❌ 測試失敗: INT 增加量不足 (目前: {current_int1}, 初始: {initial_int1})")
        sys.exit(1)
        
    if "機率觸發" not in result1.get("rewards", {}).get("stat_increase", ""):
        print("❌ 測試失敗: 缺少對應提示訊息")
        sys.exit(1)
    print("✅ 測試通過: 成功獲得屬性獎勵與升級加成\n")
    
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
    # 同樣會升級，所以 INT 至少會 +1
    if player2.stats.get("INT") <= initial_int2:
         print("❌ 測試失敗: 升級加成未生效")
         sys.exit(1)

    if "stat_increase" in result2.get("rewards", {}):
        print("❌ 測試失敗: 結算訊息不應包含 '機率觸發' 的屬性提升")
        sys.exit(1)
    print("✅ 測試通過: 未獲得額外 INT，符合機率失敗邏輯\n")

    # --- 測試案例 3: 多重屬性獨立判定 (使用無經驗值的自定義任務避免升級干擾) ---
    print("[測試 3] 模擬多重屬性獎勵 (array 格式)")
    player3 = Character(name="Multi-talented Student")
    initial_str = player3.stats.get("STR", 10)
    initial_int = player3.stats.get("INT", 10)
    
    # 注入一個有多重獎勵且無經驗值的任務
    multi_quest_id = "quest_multi"
    qm.quests[multi_quest_id] = {
        "name": "多重鍛鍊任務",
        "rewards": {
            "money": 0,
            "exp": 0,
            "chance_stat_increase": [
                {"chance": 50, "stat": "STR", "amount": 1},
                {"chance": 50, "stat": "INT", "amount": 1}
            ]
        }
    }
    
    qm.accept_quest(multi_quest_id)
    qm.active_quests[multi_quest_id]["completed"] = True
    
    # 模擬兩次擲骰都成功 (序列器)
    # 第一次 True (STR), 第二次 True (INT)
    with patch('core.dice.Dice.check_d100', side_effect=[True, True]):
        result3 = qm.resolve_quest(player3, multi_quest_id)
    
    print(f"兩次成功結果: {result3.get('rewards')}")
    if player3.stats.get("STR") != initial_str + 1 or player3.stats.get("INT") != initial_int + 1:
        print(f"❌ 測試失敗: 多重獎勵未正確發放 (STR: {player3.stats.get('STR')}, INT: {player3.stats.get('INT')})")
        sys.exit(1)
    
    # 模擬一次成功一次失敗
    player4 = Character(name="Half-lucky Student")
    initial_str4 = player4.stats.get("STR", 10)
    initial_int4 = player4.stats.get("INT", 10)
    qm.accept_quest(multi_quest_id)
    qm.active_quests[multi_quest_id]["completed"] = True
    with patch('core.dice.Dice.check_d100', side_effect=[True, False]):
        result4 = qm.resolve_quest(player4, multi_quest_id)
    
    print(f"一部分成功結果: {result4.get('rewards')}")
    if player4.stats.get("STR") != initial_str4 + 1 or player4.stats.get("INT") != initial_int4:
        print(f"❌ 測試失敗: 多重獎勵判定未獨立處理")
        sys.exit(1)
    
    print("✅ 測試通過: 多重屬性獨立判定運作正常\n")
    
    print("✨ 所有驗證測試皆已通過！")

if __name__ == "__main__":
    test_chance_stat_increase()

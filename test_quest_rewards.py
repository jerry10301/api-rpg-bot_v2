import sys
import os

sys.path.append(os.getcwd())

from core.character import Character
from core.quest_manager import QuestManager

def test_quest_rewards():
    print("=== 驗證 K大課件任務與屬性獎勵發放 ===\n")
    
    qm = QuestManager()
    player = Character(name="Test Student")
    
    # 記錄初始狀態
    initial_money = player.money
    initial_exp = player.exp
    initial_int = player.stats.get("INT", 10)
    
    print(f"初始狀態: Money={initial_money}, Exp={initial_exp}, INT={initial_int}")
    
    # 接取任務
    quest_id = "quest_assist_krenz"
    print(f"\n[1] 接取任務: {quest_id}")
    msg = qm.accept_quest(quest_id)
    print(msg)
    
    if quest_id not in qm.active_quests:
        print("❌ 任務接取失敗")
        sys.exit(1)
        
    # 模擬完成任務目標
    print("\n[2] 模擬達成目標")
    qm.active_quests[quest_id]["current_amount"] = 1
    qm.active_quests[quest_id]["completed"] = True
    
    # 回報任務
    print("\n[3] 任務回報結算")
    result = qm.resolve_quest(player, quest_id)
    
    print("\n結算結果字典:")
    print(result)
    
    # 驗證獎勵是否正確發放
    print(f"\n當前狀態: Money={player.money}, Exp={player.exp}, INT={player.stats.get('INT')}")
    
    passed = True
    
    if not result.get("success"):
        print("❌ 任務回報失敗")
        passed = False
        
    if player.money != initial_money + 80:
        print(f"❌ 金錢發放錯誤: 預期 {initial_money + 80}, 實際 {player.money}")
        passed = False
        
    # 預期：初始 exp 0 + 獲得 120 = 120。
    # 達到 100 時升一級 (Lv1 -> Lv2)，扣除 100。剩餘 exp = 20。
    expected_exp = 20
    if player.exp != expected_exp:
        print(f"❌ 經驗發放錯誤: 預期 {expected_exp}, 實際 {player.exp}")
        passed = False
    
    if player.level != 2:
        print(f"❌ 等級提升錯誤: 預期等級 2, 實際 {player.level}")
        passed = False
        
    if player.stats.get("INT") != initial_int + 1:
        print(f"❌ 屬性發放錯誤: 預期 INT={initial_int + 1}, 實際 {player.stats.get('INT')}")
        passed = False
        
    if "INT +1" not in result.get("rewards", {}).get("stat_increase", ""):
        print("❌ 結算訊息缺少屬性提升資訊")
        passed = False
        
    if passed:
        print("\n✨ 所有驗證測試皆已通過！")
    else:
        sys.exit(1)

if __name__ == "__main__":
    test_quest_rewards()

import json
import os
import random
from core.character import Character
from core.dice import Dice

class QuestManager:
    def __init__(self, quests_file: str = "data/quests.json", npcs_file: str = "data/npcs.json"):
        # 確保路徑以目前工作目錄為基準
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.quests_path = os.path.join(base_dir, quests_file)
        self.npcs_path = os.path.join(base_dir, npcs_file)
        
        self.quests = self._load_data(self.quests_path)
        self.npcs = self._load_data(self.npcs_path)
        self.active_quests = {} # {quest_id: {"name": str, "target_type": str, "target_amount": int, "current_amount": int, "completed": bool}}

    def _load_data(self, filepath: str) -> dict:
        if not os.path.exists(filepath):
            print(f"警告: 找不到檔案 {filepath}")
            return {}
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_quest(self, quest_id: str) -> dict:
        return self.quests.get(quest_id)

    def get_npc_data(self, npc_id: str) -> dict:
        return self.npcs.get(npc_id, {})

    def get_random_quest(self) -> dict:
        if not self.quests:
            return None
        quest_id = random.choice(list(self.quests.keys()))
        quest = self.quests[quest_id].copy()
        quest['id'] = quest_id
        return quest

    def accept_quest(self, quest_id: str) -> str:
        """接取任務並存入進行中清單"""
        if quest_id in self.active_quests:
            return f"你已經接取了這個任務。"
        
        quest = self.get_quest(quest_id)
        if not quest:
            return f"找不到任務 ID: {quest_id}"
            
        # 支援新格式 target_monsters（陣列）或舊格式 target_monster（字串）
        target_monsters = quest.get("target_monsters")
        if target_monsters is None:
            single = quest.get("target_monster")
            target_monsters = [single] if single else None

        # 讀取任務自訂的目標數量，預設為 1
        target_amount = quest.get("target_amount", 1)

        self.active_quests[quest_id] = {
            "name": quest["name"],
            "target_type": quest.get("type", "work"),
            "target_monsters": target_monsters,  # None 表示任意怪物均可
            "target_amount": target_amount,
            "current_amount": 0,
            "completed": False
        }
        
        if target_monsters:
            hint = f"（目標：{' / '.join(target_monsters)}，共 {target_amount} 隻）"
        else:
            hint = ""
        return f"已接取任務：【{quest['name']}】{hint}。請輸入 /questlog 查看進度。"

    def get_quest_log(self) -> str:
        """回傳目前任務清單與進度"""
        if not self.active_quests:
            return "目前沒有進行中的任務。"
            
        report = "=== 任務日誌 ===\n"
        for qid, data in self.active_quests.items():
            status = "可回報 (/turnin)" if data["completed"] else f"進行中 ({data['current_amount']}/{data['target_amount']})"
            report += f"[{qid}] {data['name']} - {status}\n"
        return report

    def update_quest_progress(self, target_type: str, increment: int = 1, monster_id: str = None) -> list:
        """根據遇遇戰或行動結果更新進度
        
        Args:
            target_type: 任務類型，如 "combat"、"work"
            increment: 進度增加量
            monster_id: 擊殺的怪物 ID（只適用於 combat 任務）
        """
        messages = []
        for qid, data in self.active_quests.items():
            if not data["completed"] and data["target_type"] == target_type:
                # combat 任務：若任務指定了 target_monsters 清單，則比對怪物 ID 是否在清單內
                quest_target_monsters = data.get("target_monsters")  # None 表示不限制怪物種類
                if quest_target_monsters is not None:
                    if monster_id not in quest_target_monsters:
                        # 怪物不在指定清單內，跳過
                        continue
                
                data["current_amount"] += increment
                if data["current_amount"] >= data["target_amount"]:
                    data["current_amount"] = data["target_amount"]
                    data["completed"] = True
                    msg = f"*(系統)* 任務【{data['name']}】目標達成！請回報給發布者。"
                    print(msg)
                    messages.append(msg)
        return messages

    def resolve_quest(self, character: Character, quest_id: str) -> dict:
        """任務回報：結算獎勵。不再負責屬性判定，屬性判定已移至獨立的戰鬥引擎與遭遇戰"""
        quest = self.get_quest(quest_id)
        if not quest:
            return {"success": False, "error": "Quest not found"}
            
        active = self.active_quests.get(quest_id)
        if not active or not active["completed"]:
            return {"success": False, "error": "任務尚未完成或尚未接取"}

        # 領取獎勵並從清單中移除
        result_data = {
            "quest_name": quest["name"],
            "success": True,
            "rewards": {}
        }

        rewards = quest.get("rewards", {})
        money = rewards.get("money", 0)
        exp = rewards.get("exp", 0)
        
        if money > 0:
            character.gain_money(money)
            result_data["rewards"]["money"] = money
        if exp > 0:
            character.gain_exp(exp)
            result_data["rewards"]["exp"] = exp
            
        # 處理機率獲得的屬性
        if "chance_stat_increase" in rewards:
            csi = rewards["chance_stat_increase"]
            # 統一轉換為清單處理
            if isinstance(csi, dict):
                csi_list = [csi]
            elif isinstance(csi, list):
                csi_list = csi
            else:
                csi_list = []

            increases = []
            for entry in csi_list:
                chance = entry.get("chance", 0)
                if Dice.check_d100(chance):
                    stat = entry.get("stat")
                    amount = entry.get("amount", 1)
                    if stat:
                        character.update_stat(stat, amount)
                        increases.append(f"{stat} +{amount}")
            
            if increases:
                result_data["rewards"]["stat_increase"] = ", ".join(increases) + " (機率觸發)"
        else:
            # 原有的隨機屬性提升邏輯 (兼容舊設定)
            stat_req = quest.get("difficulty_stat", "LUK")
            if Dice.check_d100(30):
                character.update_stat(stat_req, 1)
                result_data["rewards"]["stat_increase"] = f"{stat_req} +1"

        del self.active_quests[quest_id]
        return result_data

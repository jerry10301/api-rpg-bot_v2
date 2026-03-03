import os
import json
from core.character import Character
from core.dice import Dice
from core.quest_manager import QuestManager
from services.ollama_client import OllamaClient
from services.battle_engine import BattleEngine
from db.player_repository import PlayerRepository
from db.database import DB_PATH, init_db


class GameEngine:
    def __init__(self, discord_user_id: str = "__local__"):
        self.discord_user_id = discord_user_id
        init_db(DB_PATH) # 確保資料表與欄位存在
        self._repo = PlayerRepository(DB_PATH)
        self.llm = OllamaClient()
        self.skills_db = self._load_json("data/skills.json")
        self.items_db = self._load_json("data/items.json")

        # ── 從 DB 載入或建立玩家 ──────────────────────────────────────
        player = self._repo.load_player(discord_user_id)
        if player is None:
            # 本地 CLI 模式：自動建立預設角色
            player = self._repo.create_player(discord_user_id, "年輕的學徒")

        self.player = player

        # ── QuestManager：從 DB 還原任務進度 ─────────────────────────
        self.qm = QuestManager()
        self.qm.active_quests = self._repo.load_active_quests(discord_user_id)

        # ── BattleEngine：從 DB 還原戰鬥狀態 ─────────────────────────
        self.battle = BattleEngine(self.llm)
        self.battle.current_monster = self._repo.load_battle_state(discord_user_id)

    # ─────────────────────────────────────────────────────────────────
    # 狀態持久化
    # ─────────────────────────────────────────────────────────────────

    def save_state(self):
        """將目前玩家、任務、戰鬥狀態同步至 DB"""
        self._repo.save_player(self.discord_user_id, self.player)
        self._repo.save_active_quests(self.discord_user_id, self.qm.active_quests)
        self._repo.save_battle_state(self.discord_user_id, self.battle.current_monster)

    # ─────────────────────────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────────────────────────

    def _load_json(self, filepath: str) -> dict:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, filepath)
        if not os.path.exists(full_path):
            return {}
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # ─────────────────────────────────────────────────────────────────
    # 指令處理器（邏輯與原版相同）
    # ─────────────────────────────────────────────────────────────────

    def handle_status(self) -> str:
        return self.player.get_status_report()

    def handle_items(self) -> str:
        """查看物品欄"""
        if not self.player.inventory:
            return "你的物品欄空空如也。"
        
        report = "=== 物品欄 ===\n"
        for item_id, amount in self.player.inventory.items():
            # 嘗試從 DB 找名稱
            item_data = self.items_db.get(item_id, {})
            name = item_data.get("name", item_id)
            desc = item_data.get("description", "")
            report += f"• {name} x{amount} | {desc} (ID: {item_id})\n"
        return report

    def handle_skills(self) -> str:
        """查看技能清單"""
        if not self.player.skills:
            return "你還沒有學會任何技能。"
        
        report = "=== 技能清單 ===\n"
        for skill_id, lv in self.player.skills.items():
            skill_data = self.skills_db.get(skill_id, {})
            name = skill_data.get("name", skill_id)
            mp = skill_data.get("mp_cost", 0)
            desc = skill_data.get("description", "")
            report += f"• {name} (Lv.{lv}) | MP消耗: {mp} | {desc}\n"
        return report

    def handle_use_item(self, item_id: str) -> str:
        """使用物品"""
        if item_id not in self.player.inventory:
            # 嘗試模糊比對（以名稱找 ID）
            found_id = None
            for tid, data in self.items_db.items():
                if data.get("name") == item_id:
                    found_id = tid
                    break
            if found_id and found_id in self.player.inventory:
                item_id = found_id
            else:
                return f"你的物品欄中沒有【{item_id}】。"

        item_data = self.items_db.get(item_id)
        if not item_data:
            return f"系統錯誤：找不到物品資料 {item_id}"

        # 執行效果
        hp_gain = item_data.get("hp_restore", 0)
        mp_gain = item_data.get("mp_restore", 0)
        
        old_hp = self.player.hp
        old_mp = self.player.mp
        self.player.heal(hp_amount=hp_gain, mp_amount=mp_gain)
        
        actual_hp = self.player.hp - old_hp
        actual_mp = self.player.mp - old_mp
        
        self.player.remove_item(item_id, 1)
        
        msg = f"你使用了【{item_data['name']}】。"
        if actual_hp > 0: msg += f" 恢復了 {actual_hp} 點 HP。"
        if actual_mp > 0: msg += f" 恢復了 {actual_mp} 點 MP。"
        
        return msg

    def handle_questlog(self) -> str:
        return self.qm.get_quest_log()

    def handle_quest(self, quest_id: str) -> str:
        """接取任務"""
        return self.qm.accept_quest(quest_id)

    def handle_random_quest(self) -> str:
        quest = self.qm.get_random_quest()
        if not quest:
            return "目前沒有可用的任務。"
        return self.qm.accept_quest(quest['id'])

    def handle_findmonst(self) -> str:
        """尋找怪物並進入戰鬥"""
        if self.battle.is_in_battle():
            return "你已經在戰鬥中了！請先解決眼前的敵人。"
        return self.battle.start_battle()

    def handle_turnin(self, quest_id: str) -> str:
        """回報任務"""
        quest = self.qm.get_quest(quest_id)
        if not quest:
            return f"找不到任務 ID: {quest_id}"

        result_data = self.qm.resolve_quest(self.player, quest_id)
        if not result_data.get("success"):
            return f"無法回報任務：{result_data.get('error')}"

        npc_data = self.qm.get_npc_data(quest.get("provider_id"))

        print(f"*(系統)* 正在呼叫 {self.llm.model} 生成回報敘事...")
        narrative = self.llm.generate_quest_narrative(quest.get("name"), npc_data, result_data)

        sys_msg = "[任務回報結算] 成功！"
        if result_data.get('rewards'):
            sys_msg += f" 獲得: {result_data['rewards']}"

        return f"{narrative}\n\n{sys_msg}"

    def handle_work(self, quest_id: str = None) -> str:
        """執行非討伐類型的任務 (工作)"""
        if not quest_id:
            for qid, data in self.qm.active_quests.items():
                if not data["completed"] and data["target_type"] == "work":
                    quest_id = qid
                    break

        if not quest_id:
            return "目前沒有進行中的工作任務 (type=work)，或請使用 /work [id] 指定任務。"

        active = self.qm.active_quests.get(quest_id)
        if not active or active["completed"]:
            return f"找不到進行中的任務或該任務已完成：{quest_id}"

        if active["target_type"] != "work":
            return f"該任務不是一般工作任務 (目前為 {active['target_type']})。"

        quest_data = self.qm.get_quest(quest_id)
        stat_req = quest_data.get("difficulty_stat", "STR")
        stat_val = self.player.stats.get(stat_req, 10)
        # 基礎成功率從 (stat * 5) 上調，增加 +15% 基礎命中
        target_chance = max(1, min(99, (stat_val * 5) + 15))

        roll = Dice.roll_d100()
        success = roll <= target_chance

        if success:
            active["current_amount"] += 1
            if active["current_amount"] >= active["target_amount"]:
                active["completed"] = True
                print(f"\n*(系統)* 任務【{quest_data['name']}】目標達成！請回報給發布者。")

        print(f"*(系統)* 正在呼叫 {self.llm.model} 生成工作敘事...")
        system_prompt = '''
你是一個奇幻世界 TRPG 遊戲的旁白。
玩家正在執行指派的工作任務。請根據任務名稱與結果，用生動、有趣的文字描述玩家執行過程與結果。
請包含以下細節：
1. 玩家努力做了什麼。
2. 結果是成功還是失敗。
請使用繁體中文，字數限制在 50-100 字內，敘事節奏明快。
'''
        prompt = f"任務名稱：{quest_data['name']}\n檢定屬性：{stat_req}\n檢定結果：{'成功' if success else '失敗'}"
        narrative = self.llm._generate(prompt, system_prompt=system_prompt)

        sys_msg = f"[工作判定] 進行 {stat_req} 檢定 (目標<={target_chance}, 實際擲出 {roll}) -> "
        sys_msg += "【成功】進度增加！" if success else "【失敗】進度毫無寸進。"

        return f"{narrative}\n\n{sys_msg}"

    def handle_rest(self) -> str:
        """完全恢復 HP 與 MP"""
        self.player.full_rest()
        return f"😴 {self.player.name} 好好休息了一番，HP 與 MP 完全恢復！\nHP: {self.player.hp}/{self.player.max_hp} | MP: {self.player.mp}/{self.player.max_mp}"

    def handle_action(self, action_text: str) -> str:
        """處理一般行動或戰鬥攻擊"""
        if not self.battle.is_in_battle():
            return "⚠️ 系統提示：你目前不在戰鬥中！此指令僅能在遭遇戰中使用。\n非戰鬥狀態下，請使用 `/explore` 探索，或 `/work` 執行工作任務。"

        available_skills = list(self.player.skills.keys())

        print(f"*(系統)* 正在解析動作意圖...")
        intent = self.llm.parse_intent(action_text, available_skills)

        if not intent.get("is_valid", False):
            return f"動作無效: {intent.get('reason')}"

        action_type = intent.get("action_type")
        req_stat = intent.get("required_stat", "STR")
        stat_val = self.player.stats.get(req_stat, 10)
        skill_bonus = 0

        if action_type == "magic" and intent.get("skill_used"):
            skill_name = intent.get("skill_used")
            skill_bonus = self.player.skills.get(skill_name, 0)
            mp_cost = self.skills_db.get(skill_name, {}).get("mp_cost", 0)
            if self.player.mp < mp_cost:
                return f"系統提示: MP 不足！無法施放 {skill_name}。"
            self.player.mp -= mp_cost

        # 基礎成功率從 (stat * 5) 上調，增加 +15% 基礎命中
        target_chance = max(1, min(99, (stat_val * 5) + (skill_bonus * 10) + 15))
        roll = Dice.roll_d100()
        success = roll <= target_chance

        # 1. 在戰鬥中，交由 BattleEngine 處理回合
        narrative, monster_dead = self.battle.process_turn(self.player, action_text, intent, roll, success)
        if monster_dead:
            quest_msgs = self.qm.update_quest_progress("combat", 1)
            if quest_msgs:
                narrative += "\n" + "\n".join(quest_msgs)
        return narrative

    def handle_escape(self) -> str:
        """處理逃跑指令 (繞過 LLM 解析)"""
        if not self.battle.is_in_battle():
            return "你目前並不在戰鬥中！"

        print(f"*(系統)* 玩家嘗試逃跑...")
        intent = {
            "action_type": "flee",
            "required_stat": "DEX",
            "is_valid": True
        }
        
        stat_val = self.player.stats.get("DEX", 10)
        # 逃跑基礎成功率調整，依賴敏捷
        target_chance = max(1, min(99, (stat_val * 6) + 20))
        roll = Dice.roll_d100()
        success = roll <= target_chance

        action_text = "我轉身就跑！"
        narrative, monster_dead = self.battle.process_turn(self.player, action_text, intent, roll, success)
        return narrative

import os
import json
from core.character import Character
from core.dice import Dice
from core.quest_manager import QuestManager
from services.ollama_client import OllamaClient
from services.battle_engine import BattleEngine
from db.player_repository import PlayerRepository
from db.database import DB_PATH


class GameEngine:
    def __init__(self, discord_user_id: str = "__local__"):
        self.discord_user_id = discord_user_id
        self._repo = PlayerRepository(DB_PATH)
        self.llm = OllamaClient()
        self.skills_db = self._load_json("data/skills.json")

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

        # 1. 若在戰鬥中，交由 BattleEngine 處理回合
        if self.battle.is_in_battle():
            narrative, monster_dead = self.battle.process_turn(self.player, action_text, intent, roll, success)
            if monster_dead:
                quest_msgs = self.qm.update_quest_progress("combat", 1)
                if quest_msgs:
                    narrative += "\n" + "\n".join(quest_msgs)
            return narrative

        # 2. 不在戰鬥中，執行一般判定
        result_data = {
            "intent": intent,
            "target_chance": target_chance,
            "roll": roll,
            "success": success
        }
        
        # 非戰鬥狀態防呆提醒
        non_combat_notice = "⚠️ **(系統提醒：目前不在戰鬥狀態，此行動將作為一般冒險行動判定)**\n\n"

        if success and action_type == "magic" and intent.get("skill_used"):
            skill_name = intent.get("skill_used")
            skill_data = self.skills_db.get(skill_name, {})
            if skill_data.get("is_healing"):
                heal_dice = skill_data.get("heal_dice", "1d6")
                base_heal = Dice.roll(heal_dice)
                heal_multiplier = skill_data.get("heal_multiplier", 1.0)
                heal_amount = int(base_heal * heal_multiplier)
                self.player.heal(hp_amount=heal_amount)
                print(f"*(系統)* 玩家使用了 {skill_name}，恢復了 {heal_amount} 點 HP。")
                result_data["effect_applied"] = f"恢復了 {heal_amount} 點 HP"

        print(f"*(系統)* 正在生成動作敘事...")
        narrative = self.llm.generate_combat_narrative(action_text, result_data)

        sys_msg = f"[系統判定] 進行 {req_stat} 檢定 (目標<={target_chance}, 實際擲出 {roll}) -> "
        sys_msg += "【成功】\n" if success else "【失敗】\n"

        if success and "effect_applied" in result_data:
            sys_msg += f"[效果生效] {result_data['effect_applied']}\n"

        if success:
            quest_msgs = self.qm.update_quest_progress("action", 1)
            if quest_msgs:
                sys_msg += "\n" + "\n".join(quest_msgs)

        return f"{non_combat_notice}{narrative}\n\n{sys_msg}"

import os
import json
from core.character import Character
from core.dice import Dice
from core.quest_manager import QuestManager
from core.pvp_manager import PvPManager
from services.ollama_client import OllamaClient
from services.battle_engine import BattleEngine
from services.pvp_engine import PvPEngine
from db.player_repository import PlayerRepository
from db.database import DB_PATH, init_db

# 全域單例：PvP 邀請狀態（跨 GameEngine 實例共享）
_pvp_manager = PvPManager()


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

        # ── PvP：使用全域 manager 與本地 engine ────────────────────────
        self.pvp_manager = _pvp_manager
        self.pvp_engine = PvPEngine(self.skills_db)

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
            if item_id.startswith("Note:"):
                skill_id = item_id[5:]
                skill_name = self.skills_db.get(skill_id, {}).get("name", skill_id)
                name = "心得筆記"
                desc = f"記載著【{skill_name}】的學習心得。"
            else:
                item_data = self.items_db.get(item_id, {})
                name = item_data.get("name", item_id)
                desc = item_data.get("description", "")
            report += f"• {name} x{amount} | {desc} (ID: `{item_id}`)\n"
        return report

    def handle_skills(self) -> str:
        """查看技能清單（詳細版）"""
        if not self.player.skills:
            return "你還沒有學會任何技能。"
        
        lines = [f"=== 📜 {self.player.name} 的技能書 ==="]
        for skill_id, skill_lvl_data in self.player.skills.items():
            skill_data = self.skills_db.get(skill_id, {})
            name = skill_data.get("name", skill_id)
            mp = skill_data.get("mp_cost", 0)
            desc = skill_data.get("description", "")
            level = skill_lvl_data.get("level", 1)
            exp = skill_lvl_data.get("exp", 0)
            req_exp = level * 100
            
            # 命中率計算: (屬性 * 1.5) + (技能等級 * 3) + 65 + 技能命中修正
            req_stat = skill_data.get("required_stat", "STR")
            stat_val = self.player.stats.get(req_stat, 10)
            accuracy_penalty = skill_data.get("accuracy_penalty", 0)
            hit_chance = max(1, min(99, int(65 + stat_val * 1.5 + level * 3 + accuracy_penalty)))
            hit_str = f"{hit_chance}%"
            if accuracy_penalty < 0:
                hit_str += f" (含修正 {accuracy_penalty}%)"
            
            # 傷害資訊
            dmg_dice = skill_data.get("damage_dice", "")
            dmg_mult = skill_data.get("damage_multiplier", 1.0)
            level_bonus_pct = int((level - 1) * 15)
            
            # 元素
            element = skill_data.get("element", "none")
            element_icons = {
                "fire": "🔥", "water": "💧", "wind": "🌀", "earth": "🌍",
                "thunder": "⚡", "ice": "❄️", "light": "✨", "dark": "🌑", "none": ""
            }
            icon = element_icons.get(element, "🗡️")
            
            # 狀態效果
            status_effect = skill_data.get("status_effect")
            effect_chance = skill_data.get("effect_chance", 0)
            
            # 發明者
            creator = skill_data.get("creator")
            
            # 是否為治癒技能
            is_healing = skill_data.get("is_healing", False)
            
            lines.append(f"")
            lines.append(f"{icon or '🗡️'} **{name}** (`{skill_id}`)")
            lines.append(f"Lv.{level} | 熟練度: {exp}/{req_exp} | 消耗: {mp} MP")
            if is_healing:
                heal_dice = skill_data.get("heal_dice", "")
                lines.append(f"• 效果: 恢復 {heal_dice} 點 HP")
            elif dmg_dice:
                lines.append(f"• 威力: {dmg_dice} × {dmg_mult} (+等級加成 {level_bonus_pct}%)")
            lines.append(f"• 命中率: {hit_str}")
            if element and element != "none":
                lines.append(f"• 元素: {element}")
            if status_effect and effect_chance:
                lines.append(f"• 效果: {effect_chance}% 機率造成【{status_effect}】")
            if creator:
                lines.append(f"• 發明者: {creator}")
            lines.append(f"• 描述: {desc}")
        
        lines.append(f"")
        lines.append(f"─── 使用 `/skill <技能ID> <動作描述>` 來施放技能 ───")
        return "\n".join(lines)

    def handle_use_item(self, item_id: str, extra_arg: str = None) -> str:
        """使用物品"""
        if item_id not in self.player.inventory:
            # 嘗試模糊比對（以名稱找 ID）
            found_id = None
            for tid, data in self.items_db.items():
                if data.get("name") == item_id:
                    if tid in self.player.inventory:
                        found_id = tid
                        break
            
            if not found_id and item_id == "心得筆記":
                for tid in self.player.inventory:
                    if tid.startswith("Note:"):
                        found_id = tid
                        break
            
            if found_id and found_id in self.player.inventory:
                item_id = found_id
            else:
                return f"你的物品欄中沒有【{item_id}】。"

        if item_id.startswith("Note:"):
            skill_id = item_id[5:]
            skill_data = self.skills_db.get(skill_id)
            if not skill_data:
                return f"❌ 系統錯誤：找不到技能資料 {skill_id}"
            
            skill_name = skill_data.get("name", skill_id)
            if skill_id in self.player.skills:
                return f"❌ 你已經學會【{skill_name}】了，無法再透過心得筆記學習。"
            
            self.player.learn_skill(skill_id, 1)
            self.player.remove_item(item_id, 1)
            return f"📖 你閱讀了心得筆記... 恭喜！你學會了新技能：**【{skill_name}】**！"

        item_data = self.items_db.get(item_id)
        if not item_data:
            return f"系統錯誤：找不到物品資料 {item_id}"

        if item_id == "SkillNotebook":
            if not extra_arg:
                return "❌ 請指定要寫入的技能名稱或 ID。例如：`/use 技能筆記本 火球術`"
            
            target_skill_id = None
            if extra_arg in self.player.skills:
                target_skill_id = extra_arg
            else:
                for sid, data in self.skills_db.items():
                    if data.get("name") == extra_arg and sid in self.player.skills:
                        target_skill_id = sid
                        break
            
            if not target_skill_id:
                return f"❌ 你沒有學會技能【{extra_arg}】。"
            
            skill_name = self.skills_db.get(target_skill_id, {}).get("name", target_skill_id)
            
            self.player.remove_item(item_id, 1)
            note_id = f"Note:{target_skill_id}"
            self.player.add_item(note_id, 1)
            return f"✍️ 你將【{skill_name}】的奧秘寫入了筆記本。獲得了一本「心得筆記」！"

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

    def handle_give_coin(self, target_user_id: str, amount: int) -> str:
        """轉移金幣給其他玩家"""
        if amount <= 0:
            return "❌ 金額必須大於 0。"
        if self.discord_user_id == target_user_id:
            return "❌ 你不能將金幣轉移給自己。"

        target_player = self._repo.load_player(target_user_id)
        if not target_player:
            return "❌ 找不到指定的玩家。"

        if self.player.transfer_money(target_player, amount):
            self._repo.save_player(target_user_id, target_player)
            return f"💸 你成功轉移了 {amount} 金幣給 {target_player.name}！"
        else:
            return f"❌ 餘額不足！你目前只有 {self.player.money} 金幣。"

    def handle_give_item(self, target_user_id: str, item_id_or_name: str, amount: int) -> str:
        """轉移物品給其他玩家"""
        if amount <= 0:
            return "❌ 數量必須大於 0。"
        if self.discord_user_id == target_user_id:
            return "❌ 你不能將物品轉移給自己。"

        target_player = self._repo.load_player(target_user_id)
        if not target_player:
            return "❌ 找不到指定的玩家。"

        # 嘗試以 ID 或 名稱 尋找物品
        item_id = None
        if item_id_or_name in self.player.inventory:
            item_id = item_id_or_name
        else:
            for tid, data in self.items_db.items():
                if data.get("name") == item_id_or_name and tid in self.player.inventory:
                    item_id = tid
                    break
        
        if not item_id:
            return f"❌ 你沒有【{item_id_or_name}】。"

        item_name = self.items_db.get(item_id, {}).get("name", item_id)

        if self.player.transfer_item(target_player, item_id, amount):
            self._repo.save_player(target_user_id, target_player)
            return f"📦 你成功將 {amount} 個【{item_name}】交給了 {target_player.name}！"
        else:
            owned = self.player.inventory.get(item_id, 0)
            return f"❌ 物品數量不足！你目前只有 {owned} 個【{item_name}】。"

    def handle_shop_list(self) -> str:
        """查看商店商品清單"""
        lines = ["=== 🛒 商店商品清單 ==="]
        lines.append(f"你目前擁有: {self.player.money} 金幣")
        lines.append("")
        
        has_items = False
        for item_id, data in self.items_db.items():
            price = data.get("price")
            if price is not None and price > 0:
                has_items = True
                name = data.get("name", item_id)
                desc = data.get("description", "")
                sell_price = max(1, price // 10)
                lines.append(f"• **{name}** (ID: `{item_id}`)")
                lines.append(f"  💰 購買: {price} 金幣 | 販售: {sell_price} 金幣")
                lines.append(f"  📝 {desc}")
                
        if not has_items:
            return "目前商店沒有販售任何商品。"
            
        lines.append("")
        lines.append("💡 使用 `/shop buy <物品> [數量]` 來購買")
        lines.append("💡 使用 `/shop sell <物品> [數量]` 來販售 (獲得購買價值的 1/10)")
        return "\n".join(lines)

    def handle_shop_buy(self, item_name_or_id: str, amount: int = 1) -> str:
        """從商店購買物品"""
        if amount <= 0:
            return "❌ 購買數量必須大於 0。"
            
        # 尋找物品
        item_id = None
        if item_name_or_id in self.items_db and self.items_db[item_name_or_id].get("price"):
            item_id = item_name_or_id
        else:
            for tid, data in self.items_db.items():
                if data.get("name") == item_name_or_id and data.get("price"):
                    item_id = tid
                    break
                    
        if not item_id:
            return f"❌ 商店沒有販售【{item_name_or_id}】。"
            
        item_data = self.items_db[item_id]
        price = item_data.get("price", 0)
        total_cost = price * amount
        
        if self.player.money < total_cost:
            return f"❌ 金幣不足！【{item_data.get('name', item_id)}】x{amount} 需要 {total_cost} 金幣，你目前只有 {self.player.money} 金幣。"
            
        # 扣錢給物品
        self.player.money -= total_cost
        self.player.add_item(item_id, amount)
        
        return f"🛒 交易成功！你花費了 {total_cost} 金幣購買了 {amount} 個【{item_data.get('name', item_id)}】。"

    def handle_shop_sell(self, item_name_or_id: str, amount: int = 1) -> str:
        """賣出物品給商店"""
        if amount <= 0:
            return "❌ 販售數量必須大於 0。"
            
        # 在玩家物品欄中尋找
        item_id = None
        if item_name_or_id in self.player.inventory:
            item_id = item_name_or_id
        else:
            for tid, data in self.items_db.items():
                if data.get("name") == item_name_or_id and tid in self.player.inventory:
                    item_id = tid
                    break
                    
        if not item_id:
            return f"❌ 你的物品欄中沒有【{item_name_or_id}】。"
            
        owned_amount = self.player.inventory.get(item_id, 0)
        if owned_amount < amount:
            item_name = self.items_db.get(item_id, {}).get("name", item_id)
            return f"❌ 數量不足！你目前只有 {owned_amount} 個【{item_name}】。"
            
        # 計算金幣
        item_data = self.items_db.get(item_id, {})
        buy_price = item_data.get("price", 0)
        if buy_price <= 0:
            return f"❌ 【{item_data.get('name', item_id)}】無法販售。"
            
        sell_price_per_item = max(1, buy_price // 10)
        total_earned = sell_price_per_item * amount
        item_name = item_data.get("name", item_id)
        
        # 扣除物品、增加金幣
        if self.player.remove_item(item_id, amount):
            self.player.gain_money(total_earned)
            return f"💰 收購成功！你賣出了 {amount} 個【{item_name}】，獲得了 {total_earned} 金幣。"
        else:
            return "❌ 系統錯誤：無法扣除物品。"

    def handle_questlog(self) -> str:
        return self.qm.get_quest_log()

    def handle_forget_skill(self, skill_id_or_name: str) -> str:
        """玩家遺忘技能（僅移除個人清單，不影響全域 skills.json）"""
        # 先嘗試以 skill_id 找，再以中文名找
        target_id = None
        if skill_id_or_name in self.player.skills:
            target_id = skill_id_or_name
        else:
            for sid, data in self.skills_db.items():
                if data.get("name") == skill_id_or_name and sid in self.player.skills:
                    target_id = sid
                    break
        
        if not target_id:
            return f"❌ 你沒有學會技能【{skill_id_or_name}】。"
        
        skill_name = self.skills_db.get(target_id, {}).get("name", target_id)
        del self.player.skills[target_id]
        return (
            f"😶 你選擇遺忘了技能【{skill_name}】。\n"
            f"這個技能仍然存在於世界之中，說不定未來某天你會再次習得它。"
        )

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
        # 基礎成功率
        target_chance = max(1, min(95, int(50 + stat_val * 2)))

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
        print(f"*(系統)* 意圖解析結果: {json.dumps(intent, ensure_ascii=False)}")

        # is_valid 團已由 LLM 後處理強制為 True，這裡指主要拿來抦掉意圖解析完全失敗的稏有狀況
        if not intent.get("is_valid", False):
            return f"動作無效: {intent.get('reason')}"

        action_type = intent.get("action_type")
        req_stat = intent.get("required_stat", "STR")
        stat_val = self.player.stats.get(req_stat, 10)
        accuracy_penalty = 0

        if action_type == "magic" and intent.get("skill_used"):
            skill_name = intent.get("skill_used")
            skill_def = self.skills_db.get(skill_name, {})
            accuracy_penalty = skill_def.get("accuracy_penalty", 0)

            # 只有已學會的技能才會消耗 MP。未學会的技能則当一般動作處理。
            if skill_name in self.player.skills and skill_def:
                mp_cost = skill_def.get("mp_cost", 0)
                if self.player.mp < mp_cost:
                    return f"系統提示: MP 不足！無法施放【{skill_def.get('name', skill_name)}】（需要 {mp_cost} MP）。"
                self.player.mp -= mp_cost

        # 命中率公式：65 + (屬性 * 1.5) + (技能等級 * 3) + 技能命中修正
        skill_level = self.player.skills.get(intent.get("skill_used", ""), {}).get("level", 1) if intent.get("skill_used") else 1
        target_chance = max(1, min(99, int(65 + (stat_val * 1.5) + (skill_level * 3) + accuracy_penalty)))
        roll = Dice.roll_d100()
        success = roll <= target_chance
        
        print(f"*(系統)* 命中判定: 需求 {target_chance}% | 擲骰 {roll} | {'成功' if success else '失敗'}")

        def _sync_skill(skill_id: str, skill_data: dict):
            """新發明技能後同步 engine 的 skills_db"""
            self.skills_db[skill_id] = skill_data

        # 1. 在戰鬥中，交由 BattleEngine 處理回合
        narrative, monster_dead = self.battle.process_turn(
            self.player, action_text, intent, roll, success,
            on_skill_learned=_sync_skill
        )
        if monster_dead:
            killed_id = self.battle.last_killed_monster_id
            quest_msgs = self.qm.update_quest_progress("combat", 1, monster_id=killed_id)
            if quest_msgs:
                narrative += "\n" + "\n".join(quest_msgs)
        return narrative

    def handle_skill_use(self, skill_id_or_name: str, action_text: str) -> str:
        """在戰鬥中強制指定使用特定技能"""
        if not self.battle.is_in_battle():
            return "⚠️ 你目前不在戰鬥中！"

        # 解析 skill_id
        target_id = None
        if skill_id_or_name in self.player.skills:
            target_id = skill_id_or_name
        else:
            for sid, data in self.skills_db.items():
                if data.get("name") == skill_id_or_name and sid in self.player.skills:
                    target_id = sid
                    break

        if not target_id:
            return f"❌ 你沒有學會技能【{skill_id_or_name}】，或該技能不在資料庫中。"

        skill_data = self.skills_db.get(target_id, {})
        skill_name = skill_data.get("name", target_id)
        req_stat = skill_data.get("required_stat", "STR")
        mp_cost = skill_data.get("mp_cost", 0)
        accuracy_penalty = skill_data.get("accuracy_penalty", 0)

        if self.player.mp < mp_cost:
            return f"❌ MP 不足！施放【{skill_name}】需要 {mp_cost} MP，你目前只有 {self.player.mp} MP。"
        self.player.mp -= mp_cost

        stat_val = self.player.stats.get(req_stat, 10)
        skill_level = self.player.skills[target_id].get("level", 1)
        target_chance = max(1, min(99, int(65 + stat_val * 1.5 + skill_level * 3 + accuracy_penalty)))
        roll = Dice.roll_d100()
        success = roll <= target_chance

        intent = {
            "action_type": "magic",
            "skill_used": target_id,
            "is_valid": True,
            "required_stat": req_stat,
            "difficulty": target_chance,
            "reason": f"玩家強制施放技能 {skill_name}"
        }

        def _sync_skill(skill_id: str, skill_data: dict):
            self.skills_db[skill_id] = skill_data

        narrative, monster_dead = self.battle.process_turn(
            self.player, action_text or f"施放{skill_name}！", intent, roll, success,
            on_skill_learned=_sync_skill
        )
        if monster_dead:
            killed_id = self.battle.last_killed_monster_id
            quest_msgs = self.qm.update_quest_progress("combat", 1, monster_id=killed_id)
            if quest_msgs:
                narrative += "\n" + "\n".join(quest_msgs)
        return narrative

    def handle_rank_level(self, limit: int = 10) -> list[dict]:
        """取得等級排行榜"""
        return self._repo.get_top_players_by_level(limit=limit)

    def handle_rank_coin(self, limit: int = 10) -> list[dict]:
        """取得財富排行榜"""
        return self._repo.get_top_players_by_coin(limit=limit)

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
        target_chance = max(1, min(90, int(50 + stat_val * 2)))
        roll = Dice.roll_d100()
        success = roll <= target_chance

        action_text = "我轉身就跑！"
        narrative, monster_dead = self.battle.process_turn(self.player, action_text, intent, roll, success)
        return narrative

    # ─────────────────────────────────────────────────────────────────
    # PvP 指令處理器
    # ─────────────────────────────────────────────────────────────────

    def handle_pk_invite(self, target_user_id: str) -> str:
        """
        向 target_user_id 玩家發送決鬥邀請。
        呼叫者為 self.discord_user_id。
        """
        if self.discord_user_id == target_user_id:
            return "❌ 你不能向自己發送決鬥邀請。"

        # 若自己正在戰鬥中，禁止挑戰
        if self.battle.is_in_battle():
            return "❌ 你目前正在與怪物交戰，無法發送決鬥邀請！請先解決眼前的戰鬥。"

        target_player = self._repo.load_player(target_user_id)
        if not target_player:
            return "❌ 找不到指定的玩家，對方可能尚未建立角色。"

        self.pvp_manager.send_invite(self.discord_user_id, target_user_id)
        return (
            f"⚔️ 【{self.player.name}】向【{target_player.name}】發出決鬥挑戰！\n"
            f"【{target_player.name}】請使用 `/pk allow` 接受，或 `/pk deny` 拒絕。"
        )

    def handle_pk_allow(self) -> tuple[str, str]:
        """
        接受決鬥邀請，執行自動戰鬥模擬並由 LLM 渲染結果。
        回傳 (narrative, sys_result) 兩段訊息。
        """
        inviter_id = self.pvp_manager.get_invite(self.discord_user_id)
        if not inviter_id:
            return ("❌ 你目前沒有待處理的決鬥邀請。", "")

        inviter_player = self._repo.load_player(inviter_id)
        if not inviter_player:
            self.pvp_manager.remove_invite(self.discord_user_id)
            return ("❌ 邀請者的角色資料已不存在，邀請已失效。", "")

        # 移除邀請
        self.pvp_manager.remove_invite(self.discord_user_id)

        # ── 自動戰鬥推演 ──
        print(f"*(系統)* PvP 推演開始：{inviter_player.name} vs {self.player.name}")
        result = self.pvp_engine.simulate(inviter_player, self.player)

        winner = result["winner"]
        loser = result["loser"]
        turns = result["turns"]
        draw = result["draw"]
        battle_log = result["battle_log"]

        winner_name = winner.name if winner else None

        # ── LLM 渲染敘事 ──
        print(f"*(系統)* 正在生成 PvP 決鬥敘事...")
        narrative = self.llm.generate_pvp_narrative(
            p1_name=inviter_player.name,
            p2_name=self.player.name,
            battle_log=battle_log,
            winner_name=winner_name,
            turns=turns,
        )

        # ── 結算訊息 ──
        if draw:
            sys_result = (
                f"\n[決鬥結算] ⚖️ 平局！\n"
                f"【{inviter_player.name}】vs 【{self.player.name}】歷經 {turns} 回合，雙方勢均力敵，決鬥以平局收場。"
            )
        else:
            sys_result = (
                f"\n[決鬥結算] 🏆 勝者：【{winner_name}】\n"
                f"歷經 {turns} 回合激戰，【{winner_name}】技高一籌，成功擊敗了【{loser.name}】！"
            )

        full_output = f"{narrative}\n{sys_result}"
        return (full_output, sys_result)

    def handle_pk_deny(self) -> str:
        """
        拒絕決鬥邀請。
        """
        inviter_id = self.pvp_manager.get_invite(self.discord_user_id)
        if not inviter_id:
            return "❌ 你目前沒有待處理的決鬥邀請。"

        inviter_player = self._repo.load_player(inviter_id)
        inviter_name = inviter_player.name if inviter_player else inviter_id
        self.pvp_manager.remove_invite(self.discord_user_id)
        return (
            f"🛡️ 【{self.player.name}】拒絕了【{inviter_name}】的決鬥挑戰。\n"
            f"【{inviter_name}】的挑戰已被婉拒。"
        )

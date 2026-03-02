import json
import os
import random
from core.character import Character
from core.dice import Dice
from services.ollama_client import OllamaClient

class BattleEngine:
    def __init__(self, ollama_client: OllamaClient):
        self.llm = ollama_client
        self.monsters_db = self._load_data("data/monsters.json")
        self.skills_db = self._load_data("data/skills.json")
        self.current_monster = None

    def _load_data(self, filepath: str) -> dict:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, filepath)
        if not os.path.exists(full_path):
            return {}
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def is_in_battle(self) -> bool:
        return self.current_monster is not None

    def start_battle(self, specific_monster: str = None) -> str:
        """開始戰鬥，若無指定則隨機挑選怪物"""
        if not self.monsters_db:
            return "目前沒有可遭遇的怪物。"
            
        monster_id = specific_monster
        if not monster_id or monster_id not in self.monsters_db:
            monster_id = random.choice(list(self.monsters_db.keys()))
            
        monster_data = self.monsters_db[monster_id].copy()
        
        # 動態為怪物生成當前 HP
        self.current_monster = {
            "id": monster_id,
            "name": monster_data["name"],
            "max_hp": monster_data["hp"],
            "current_hp": monster_data["hp"],
            "max_mp": monster_data.get("mp", 0),
            "current_mp": monster_data.get("mp", 0),
            "attack": monster_data["attack"],
            "defense": monster_data.get("defense", 0),
            "description": monster_data.get("description", ""),
            "skills": monster_data.get("skills", []),
            "exp_reward": monster_data.get("exp_reward", 10 + monster_data["hp"] // 5),
            "money_reward": monster_data.get("money_reward", random.randint(1, 5) + monster_data["attack"])
        }
        
        return f"\n⚠️ 遭遇戰開始！\n你遇到了一隻【{self.current_monster['name']}】({self.current_monster['description']})！\nHP: {self.current_monster['current_hp']}/{self.current_monster['max_hp']} | 攻擊力: {self.current_monster['attack']}\n(請使用 /attack [動作] 來攻擊牠！)"

    def process_turn(self, player: Character, action_text: str, player_intent: dict, player_roll: int, player_success: bool) -> tuple[str, bool]:
        """
        處理戰鬥的一個回合：玩家先手，若怪物沒死則怪物反擊。
        回傳: (敘事字串, 戰鬥是否結束)
        """
        if not self.is_in_battle():
            return ("不在戰鬥中。", False)
            
        m = self.current_monster
        is_battle_over = False
        combat_log = []
        
        # ======= 1. 玩家回合結算 =======
        action_type = player_intent.get("action_type", "physical")
        is_fleeing = (action_type == "flee")
        is_defending = (action_type == "defend")
        
        player_damage = 0
        if is_fleeing:
            if player_success:
                combat_log.append("玩家逃跑成功！")
                is_battle_over = True
            else:
                combat_log.append("玩家逃跑失敗！")
        elif is_defending:
            if player_success:
                combat_log.append("玩家防禦成功，準備抵禦攻擊。")
            else:
                combat_log.append("玩家防禦失敗，破綻百出。")
        else:
            if player_success:
                # 基礎傷害邏輯
                skill_name = player_intent.get("skill_used")
                skill_data = self.skills_db.get(skill_name, {}) if skill_name else {}
                
                is_healing = skill_data.get("is_healing", False)
                
                if is_healing:
                    heal_dice = skill_data.get("heal_dice", "1d6")
                    base_heal = Dice.roll(heal_dice)
                    
                    # 應用治癒倍率
                    heal_multiplier = skill_data.get("heal_multiplier", 1.0)
                    heal_amount = int(base_heal * heal_multiplier)
                    
                    player.heal(hp_amount=heal_amount)
                    combat_log.append(f"玩家施展 {skill_name}，恢復了 {heal_amount} 點 HP。")
                else:
                    # 攻擊傷害計算
                    dmg_dice = skill_data.get("damage_dice", "1d6")
                    base_dmg = Dice.roll(dmg_dice)
                    
                    stat_bonus = player.stats.get(player_intent.get("required_stat", "STR"), 10) // 5
                    
                    raw_damage = base_dmg + stat_bonus
                    
                    # 應用倍率
                    multiplier = skill_data.get("damage_multiplier", 1.0)
                    raw_damage = int(raw_damage * multiplier)
                    
                    if action_type == "magic":
                        skill_bonus = player.skills.get(skill_name, 0)
                        raw_damage += skill_bonus * 2
                    
                    # 扣除怪防禦
                    player_damage = max(1, raw_damage - m["defense"])
                    m["current_hp"] -= player_damage
                    combat_log.append(f"玩家攻擊成功！造成 {player_damage} 點傷害。")
            else:
                combat_log.append("玩家動作失敗。")

        # 怪物是否死亡？
        monster_dead = m["current_hp"] <= 0
        
        # ======= 2. 怪物回合結算 =======
        monster_damage = 0
        if not monster_dead and not is_battle_over:
            # 怪物反擊簡易判定：依據玩家敏捷閃避 (基礎加乘3倍)
            dodge_chance = player.stats.get("DEX", 10) * 3
            if Dice.check_d100(dodge_chance):
                combat_log.append(f"{m['name']} 嘗試反擊，但被玩家閃避了！")
            else:
                # 嘗試施放技能：需有技能列表且 MP 充足，且 40% 機率觸發
                used_skill = False
                monster_skills = m.get("skills", [])
                if monster_skills and m["current_mp"] > 0:
                    if random.random() < 0.4:  # 40% 機率施法
                        skill_name = random.choice(monster_skills)
                        skill_data = self.skills_db.get(skill_name, {})
                        mp_cost = skill_data.get("mp_cost", 0)
                        if mp_cost <= m["current_mp"]:
                            # 扣除 MP 並計算魔法傷害
                            m["current_mp"] -= mp_cost
                            dmg_dice = skill_data.get("damage_dice", "1d4")
                            base_dmg = Dice.roll(dmg_dice)
                            multiplier = skill_data.get("damage_multiplier", 1.0)
                            monster_damage = max(0, int(base_dmg * multiplier))
                            player.hp -= monster_damage
                            skill_display = skill_data.get("name", skill_name)
                            combat_log.append(
                                f"{m['name']} 施放【{skill_display}】！對玩家造成 {monster_damage} 點魔法傷害。"
                            )
                            used_skill = True

                if not used_skill:
                    # 普通物理攻擊
                    raw_dmg = m["attack"] + random.randint(0, 2)
                    # 簡易玩家防禦
                    player_def = 2
                    if is_defending and player_success:
                        player_def += 5  # 防禦成功減傷增加
                    monster_damage = max(0, raw_dmg - player_def)
                    player.hp -= monster_damage
                    combat_log.append(f"{m['name']} 反擊命中！對玩家造成 {monster_damage} 點傷害。")

                if player.hp < 0:
                    player.hp = 0

        # ======= 3. 交由 LLM 生成回合敘事 =======
        battle_data = {
            "monster_name": m["name"],
            "monster_dead": monster_dead,
            "player_action": action_text,
            "action_type": action_type,
            "player_success": player_success,
            "player_damage": player_damage,
            "monster_damage": monster_damage,
            "monster_current_hp": max(0, m["current_hp"]),
            "player_current_hp": player.hp,
            "player_fled": is_battle_over and is_fleeing
        }
        
        print(f"*(系統)* 正在生成回合敘事...")
        narrative = self.llm.generate_combat_narrative(action_text, battle_data)
        
        # 結算顯示
        sys_msg = (
            f"\n[回合結算] "
            f"{m['name']} HP: {max(0, m['current_hp'])}/{m['max_hp']} | MP: {m['current_mp']}/{m['max_mp']}"
            f"  ///  "
            f"{player.name} HP: {player.hp}/{player.max_hp} | MP: {player.mp}/{player.max_mp}"
        )
        
        if monster_dead:
            exp_gain = m.get("exp_reward", 15)
            money_gain = m.get("money_reward", 5)
            
            player.gain_exp(exp_gain)
            player.gain_money(money_gain)
            
            sys_msg += f"\n🏆 戰鬥結束！你擊敗了 {m['name']}！\n獲得 {exp_gain} 點經驗與 {money_gain} 枚金幣。"
            is_battle_over = True
        elif player.hp <= 0:
            sys_msg += f"\n💀 戰鬥結束...你被 {m['name']} 擊倒了。"
            is_battle_over = True
            
        if is_battle_over:
            self.current_monster = None # 清除怪物狀態
            
        full_narrative = f"{narrative}\n{sys_msg}"
        return full_narrative, monster_dead

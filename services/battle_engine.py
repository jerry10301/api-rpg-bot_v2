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
        self.last_killed_monster_id: str | None = None  # 最後擊杀的怪物 ID

    def _load_data(self, filepath: str) -> dict:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, filepath)
        if not os.path.exists(full_path):
            return {}
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_skills_db(self):
        """將 skills_db 存回 data/skills.json（原子寫入，防止崩潰導致 JSON 損壞）"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, "data/skills.json")
        tmp_path = full_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(self.skills_db, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, full_path)

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
            "element": monster_data.get("element"),
            "description": monster_data.get("description", ""),
            "skills": monster_data.get("skills", []),
            "status_effects": {}, # 怪物異常狀態 { "狀態名稱": 剩餘回合 }
            "exp_reward": monster_data.get("exp_reward", 10 + monster_data["hp"] // 5),
            "money_reward": monster_data.get("money_reward", random.randint(1, 5) + monster_data["attack"])
        }
        
        return f"\n⚠️ 遭遇戰開始！\n你遇到了一隻【{self.current_monster['name']}】({self.current_monster['description']})！\nHP: {self.current_monster['current_hp']}/{self.current_monster['max_hp']} | 攻擊力: {self.current_monster['attack']}\n(請使用 `/attack <動作>` 來發起攻擊，或使用 `/escape` 嘗試逃跑！)"

    def _calculate_hit_chance(self, stat_value: int, skill_level: int, accuracy_penalty: int = 0) -> int:
        """
        計算命中率 (%)
        公式：(相關屬性 * 5) + (技能等級 * 10) + 15 + 命中修正
        範圍：1-99
        """
        chance = (stat_value * 5) + (skill_level * 10) + 15 + accuracy_penalty
        return max(1, min(99, chance))

    def process_turn(self, player: Character, action_text: str, player_intent: dict, player_roll: int, player_success: bool, on_skill_learned=None) -> tuple[str, bool]:
        """
        處理戰鬥的一個回合：玩家先手，若怪物沒死則怪物反擊。
        on_skill_learned: 可選的 callback(skill_id, skill_data)，用於通知 engine 同步 skills_db。
        回傳: (敘事字串, 戰鬥是否結束)
        """
        if not self.is_in_battle():
            return ("不在戰鬥中。", False)
            
        m = self.current_monster
        # 確保怪物有 status_effects 和 element 欄位 (向下相容)
        m.setdefault("status_effects", {})
        m.setdefault("element", None)
        is_battle_over = False
        combat_log = []
        
        # ------- 0. 回合開始狀態結算 -------
        # 玩家狀態處理
        player_status_msgs = player.process_status_effects()
        combat_log.extend(player_status_msgs)
        if player.hp <= 0:
            is_battle_over = True
            
        # 怪物狀態處理
        if not is_battle_over:
            m_status_msgs = self._process_monster_status_effects(m)
            combat_log.extend(m_status_msgs)
            if m["current_hp"] <= 0:
                is_battle_over = True
                
        # 檢查玩家是否可以行動 (受凍結、石化等影響)
        can_player_act = not any(s in player.status_effects for s in ["凍結", "石化"])
        if can_player_act and "麻痺" in player.status_effects:
            if random.random() < 0.5: # 麻痺 50% 跳過
                can_player_act = False
                combat_log.append("玩家因麻痺而無法動彈！")
        
        # ======= 1. 玩家回合結算 =======
        action_type = player_intent.get("action_type", "physical")
        is_fleeing = (action_type == "flee")
        is_defending = (action_type == "defend")
        
        player_damage = 0
        skill_learned_msg = None  # 學習/發明技能的訊息

        if is_battle_over:
            pass # 略過
        elif not can_player_act and not is_fleeing and not is_defending:
            combat_log.append("玩家目前的狀態無法發起攻擊。")
        elif action_type == "flee": # 改用 elif 避免干擾
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
                    
                    # 技能等級加成
                    skill_level = 1
                    if action_type == "magic" and skill_name in player.skills:
                        skill_level = player.skills[skill_name].get("level", 1)
                        # 給予技能熟練度
                        lvl_msg = player.gain_skill_exp(skill_name, 10)
                        if lvl_msg:
                            combat_log.append(lvl_msg)
                            
                    level_multiplier = 1.0 + (skill_level - 1) * 0.15
                    heal_amount = int(heal_amount * level_multiplier)
                    
                    player.heal(hp_amount=heal_amount)
                    combat_log.append(f"玩家施展 {skill_name}，恢復了 {heal_amount} 點 HP。")
                    
                    # 魔法治癒成功後也有 5% 機率學習技能
                    skill_learned_msg = self._attempt_skill_learning(player, action_text, on_skill_learned)
                else:
                    # ── 攻擊傷害計算 ──
                    skill_level = 1
                    is_known_skill = (skill_name is not None and skill_name in player.skills and skill_data)

                    if is_known_skill:
                        # [技能動作] 套用技能倍率 + 等級加成
                        dmg_dice = skill_data.get("damage_dice", "1d6")
                        base_dmg = Dice.roll(dmg_dice)
                        stat_bonus = player.stats.get(player_intent.get("required_stat", "STR"), 10) // 5
                        raw_damage = base_dmg + stat_bonus

                        multiplier = skill_data.get("damage_multiplier", 1.0)
                        raw_damage = int(raw_damage * multiplier)

                        skill_level = player.skills[skill_name].get("level", 1)
                        # 給予技能熟練度
                        lvl_msg = player.gain_skill_exp(skill_name, 10)
                        if lvl_msg:
                            combat_log.append(lvl_msg)

                        # 魔法額外固定加成
                        if action_type == "magic":
                            raw_damage += skill_level * 2

                        level_multiplier = 1.0 + (skill_level - 1) * 0.15
                        raw_damage = int(raw_damage * level_multiplier)
                    else:
                        # [一般動作] 僅基礎倍率 1.0
                        dmg_dice = "1d8"
                        base_dmg = Dice.roll(dmg_dice)
                        stat_bonus = player.stats.get(player_intent.get("required_stat", "STR"), 10) // 4
                        raw_damage = base_dmg + stat_bonus
                        # 基礎倍率 1.0，不套用技能加成
                    
                    # 元素相剋計算
                    skill_element = skill_data.get("element") if skill_data else None
                    monster_element = m.get("element")
                    element_mult = self._get_element_multiplier(skill_element, monster_element)
                    raw_damage = int(raw_damage * element_mult)
                    if element_mult > 1.0:
                        combat_log.append(f"元素克制！傷害提升。")
                    elif element_mult < 1.0:
                        combat_log.append(f"元素被克...傷害降低。")
                    
                    # 扣除怪防禦
                    player_damage = max(1, raw_damage - m["defense"])
                    m["current_hp"] -= player_damage
                    combat_log.append(f"玩家攻擊成功！造成 {player_damage} 點傷害。")
                    
                    # 異常狀態賦予
                    status_to_apply = skill_data.get("status_effect") if skill_data else None
                    if status_to_apply and Dice.check_d100(skill_data.get("effect_chance", 0)):
                        duration = 3
                        if status_to_apply == "凍結": duration = random.randint(1, 2)
                        elif status_to_apply == "混亂": duration = 2
                        m["status_effects"][status_to_apply] = max(m["status_effects"].get(status_to_apply, 0), duration)
                        combat_log.append(f"成功使目標進入【{status_to_apply}】狀態！")

                    # 攻擊成功後（物理與魔法），5% 機率學習技能
                    skill_learned_msg = self._attempt_skill_learning(player, action_text, on_skill_learned)
            else:
                combat_log.append("玩家動作失敗。")

        # 怪物是否死亡？
        monster_dead = m["current_hp"] <= 0
        
        # ======= 2. 怪物回合結算 =======
        monster_damage = 0
        
        # 檢查怪物是否可以行動
        can_monster_act = not any(s in m["status_effects"] for s in ["凍結", "石化"])
        if can_monster_act and "麻痺" in m["status_effects"]:
            if random.random() < 0.5:
                can_monster_act = False
                combat_log.append(f"{m['name']} 因麻痺而無法動彈！")

        if not monster_dead and not is_battle_over and can_monster_act:
            # 怪物反擊簡易判定：依據玩家敏捷閃避 (防禦成功不影響閃避率，最高閃避上限為 60%)
            dodge_chance = int(min(60, 5 + player.stats.get("DEX", 10) * 1.5))
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
                            # 扣除 MP 並計算魔法傷害（同樣扣除玩家防禦，魔法防禦看 WIS）
                            m["current_mp"] -= mp_cost
                            dmg_dice = skill_data.get("damage_dice", "1d4")
                            base_dmg = Dice.roll(dmg_dice)
                            multiplier = skill_data.get("damage_multiplier", 1.0)
                            raw_skill_dmg = max(0, int(base_dmg * multiplier))
                            player_magic_def = max(2, player.stats.get("WIS", 10) // 4)
                            monster_damage = max(0, raw_skill_dmg - player_magic_def)
                            player.hp -= monster_damage
                            skill_display = skill_data.get("name", skill_name)
                            combat_log.append(
                                f"{m['name']} 施放【{skill_display}】！對玩家造成 {monster_damage} 點魔法傷害。"
                            )
                            used_skill = True

                if not used_skill:
                    # 普通物理攻擊
                    raw_dmg = m["attack"] + random.randint(0, 2)
                    # 玩家防禦由 CON 決定（快節奏平衡公式）
                    player_def = max(2, player.stats.get("CON", 10) // 4)
                    if is_defending and player_success:
                        player_def += 5  # 防禦成功額外減傷
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
            f"{m['name']} HP: {max(0, m['current_hp'])}/{m.get('max_hp', m.get('hp', 0))} | MP: {m['current_mp']}/{m.get('max_mp', m.get('mp', 0))}"
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
            if monster_dead and self.current_monster:
                self.last_killed_monster_id = self.current_monster["id"]  # 記錄擊杀的怪物 ID
            else:
                self.last_killed_monster_id = None
            self.current_monster = None # 清除怪物狀態
            
        # 加入學習/發明訊息
        if skill_learned_msg:
            combat_log.append(skill_learned_msg)

        full_narrative = f"{narrative}\n{sys_msg}\n" + "\n".join(combat_log)
        return full_narrative, monster_dead

    def _attempt_skill_learning(self, player: Character, action_text: str, on_skill_learned=None) -> str | None:
        """
        攻擊成功後，10% 機率學會現有技能或發明新技能（現在由 LLM 決定最貼切的技能）。
        - 若 LLM 建議的現有技能玩家已學過 → 給予雙倍熟練 EXP
        - 若 LLM 發明的新技能與現有技能名稱+描述高度相似 → 退回學習最相似現有技能
        回傳描述訊息或 None。
        """
        roll = random.random()
        print(f"*(系統)* 技能學習判定: 隨機數 {roll:.4f} (需 <= 0.10 才能觸發)")
        if roll > 0.10:
            return None

        # 整理玩家尚未學過的技能資訊，供 LLM 參考
        unlearned_skills = []
        all_skills_summary = []
        for sid, sdata in self.skills_db.items():
            entry = {
                "id": sid,
                "name": sdata.get("name", sid),
                "description": sdata.get("description", "")
            }
            all_skills_summary.append(entry)
            if sid not in player.skills:
                unlearned_skills.append(entry)

        print("*(系統)* 觸發技能領悟判定，正在呼叫 LLM 決定最貼近描述的技能...")
        decision = self.llm.decide_learned_skill(
            player_name=player.name,
            player_action=action_text,
            player_level=player.level,
            player_stats=player.stats,
            unlearned_skills=unlearned_skills,
            all_skills_summary=all_skills_summary
        )

        if not decision:
            return None

        learn_type = decision.get("learn_type", "new")

        if learn_type == "existing" and decision.get("skill_id") in self.skills_db:
            skill_id = decision["skill_id"]
            skill_name = self.skills_db[skill_id].get("name", skill_id)
            # 已學過 → 給雙倍熟練 EXP
            if skill_id in player.skills:
                lvl_msg = player.gain_skill_exp(skill_id, 20)  # 雙倍 EXP
                bonus_msg = f"💡 【技能感悟】你對【{skill_name}】有了更深的理解，獲得雙倍熟練經驗！"
                if lvl_msg:
                    bonus_msg += f"\n{lvl_msg}"
                return bonus_msg
            # 未學過 → 正常學習
            player.learn_skill(skill_id)
            return f"💡 【技能習得】在戰鬥中，你悟出了新技能【{skill_name}】！"

        else:
            # 發明新技能
            skill_id = decision.get("skill_id", "")
            # 確保 skill_id 是合法字串（防止 LLM 或 Mock 回傳非字串）
            if not isinstance(skill_id, str) or not skill_id or skill_id in self.skills_db:
                # ID 衝突或無效 → 若有未學技能則隨機挑一個，否則放棄
                if unlearned_skills:
                    fallback = random.choice(unlearned_skills)
                    skill_id = fallback["id"]
                    player.learn_skill(skill_id)
                    return f"💡 【技能習得】在戰鬥中，你悟出了新技能【{fallback['name']}】！"
                return None

            # 本地重複偵測：若中文名稱+描述同時高度相似則視為重複
            duplicate_id = self._is_duplicate_skill(decision)
            if duplicate_id:
                dup_name = self.skills_db[duplicate_id].get("name", duplicate_id)
                print(f"*(系統)* 新技能與 [{duplicate_id}] 高度相似，改為學習現有技能。")
                if duplicate_id in player.skills:
                    lvl_msg = player.gain_skill_exp(duplicate_id, 20)  # 雙倍 EXP
                    bonus_msg = f"💡 【技能感悟】你對【{dup_name}】有了更深的理解，獲得雙倍熟練經驗！"
                    if lvl_msg:
                        bonus_msg += f"\n{lvl_msg}"
                    return bonus_msg
                player.learn_skill(duplicate_id)
                return f"💡 【技能習得】在戰鬥中，你悟出了新技能【{dup_name}】！"

            # 將新技能存入 skills_db
            skill_entry = {
                "name": decision.get("name", skill_id),
                "mp_cost": int(decision.get("mp_cost", 5)),
                "required_stat": decision.get("required_stat", "STR"),
                "damage_dice": decision.get("damage_dice", "1d6"),
                "damage_multiplier": float(decision.get("damage_multiplier", 1.0)),
                "accuracy_penalty": int(decision.get("accuracy_penalty", 0)),
                "element": decision.get("element", "none"),
                "status_effect": decision.get("status_effect"),
                "effect_chance": int(decision.get("effect_chance", 0)),
                "description": decision.get("description", ""),
                "creator": player.name
            }
            self.skills_db[skill_id] = skill_entry
            self._save_skills_db()

            # 通知 engine 同步記憶體
            if on_skill_learned:
                on_skill_learned(skill_id, skill_entry)

            player.learn_skill(skill_id)
            skill_name = skill_entry["name"]
            penalty_str = f"（命中修正 {skill_entry['accuracy_penalty']}%）" if skill_entry["accuracy_penalty"] else ""
            return (
                f"✨ 【技能發明】在戰鬥的靈光一閃中，你發明了全新技能【{skill_name}】！"
                f"{penalty_str}\n"
                f"MP消耗: {skill_entry['mp_cost']} | {skill_entry['description']}\n"
                f"你成為了【{skill_name}】技能在這個世界的第一位發明者！"
            )

    def _is_duplicate_skill(self, new_skill: dict) -> str | None:
        """
        判斷新技能是否與現有技能高度重複。
        規則：中文名稱相似度 >= 80% 且 描述相似度 >= 80% 時視為重複。
        回傳最相似的現有技能 skill_id，或 None（不重複）。
        """
        from difflib import SequenceMatcher

        def similarity(a: str, b: str) -> float:
            if not a or not b:
                return 0.0
            return SequenceMatcher(None, a, b).ratio()

        new_name = new_skill.get("name", "")
        new_desc = new_skill.get("description", "")

        best_id = None
        best_score = 0.0

        for sid, sdata in self.skills_db.items():
            existing_name = sdata.get("name", "")
            existing_desc = sdata.get("description", "")
            name_sim = similarity(new_name, existing_name)
            desc_sim = similarity(new_desc, existing_desc)
            # 名稱 AND 描述同時高度相似才視為重複
            if name_sim >= 0.80 and desc_sim >= 0.80:
                combined = name_sim + desc_sim
                if combined > best_score:
                    best_score = combined
                    best_id = sid

        if best_id:
            print(f"*(系統)* 重複偵測命中：新技能「{new_name}」與現有技能「{self.skills_db[best_id].get('name')}」({best_id}) 高度相似，相似分={best_score:.2f}")
        return best_id

    def _get_element_multiplier(self, attacker_elem: str, defender_elem: str) -> float:
        """獲取元素傷害倍率"""
        if not attacker_elem or not defender_elem:
            return 1.0
            
        counters = {
            "fire": ["wind", "ice"],
            "water": ["fire"],
            "wind": ["earth"],
            "earth": ["water", "thunder"],
            "thunder": ["water"],
            "ice": ["wind"],
            "light": ["dark"],
            "dark": ["light"]
        }
        
        if defender_elem in counters.get(attacker_elem, []):
            return 1.5
            
        # 逆向克制 (被克制傷害減半, 可選)
        if attacker_elem in counters.get(defender_elem, []):
            return 0.75
            
        return 1.0

    def _process_monster_status_effects(self, m: dict) -> list:
        """處理怪物異常狀態"""
        messages = []
        to_remove = []
        max_hp = m.get("max_hp", m.get("hp", 100))
        for effect, duration in m["status_effects"].items():
            if effect == "燃燒":
                dmg = max(1, int(max_hp * 0.05))
                m["current_hp"] -= dmg
                messages.append(f"{m['name']} 受到燃燒傷害 {dmg} 點。")
            elif effect == "中毒":
                dmg = max(1, int(max_hp * 0.08))  # 比例制：8% 最大 HP
                m["current_hp"] -= dmg
                messages.append(f"{m['name']} 受到中毒傷害 {dmg} 點。")
                
            m["status_effects"][effect] -= 1
            if m["status_effects"][effect] <= 0:
                to_remove.append(effect)
                messages.append(f"{m['name']} 的【{effect}】狀態解除。")
                
        for effect in to_remove:
            del m["status_effects"][effect]
        return messages

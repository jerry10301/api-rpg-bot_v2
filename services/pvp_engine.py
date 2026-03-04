"""
services/pvp_engine.py
PvP 自動戰鬥推演引擎。
先根據雙方屬性與技能推演整場戰鬥，再將戰鬥紀錄交由 LLM 渲染輸出。
"""
import random
from typing import Optional
from core.character import Character
from core.dice import Dice


class PvPEngine:
    """
    PvP 戰鬥模擬器。
    戰鬥為回合制：先手由 DEX 決定，雙方輪流出手，直到一方 HP<=0。
    """

    MAX_TURNS = 20  # HP 降低後 20 回合足夠决出勝負

    def __init__(self, skills_db: dict):
        self.skills_db = skills_db

    # ──────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────

    def simulate(
        self,
        p1: Character,
        p2: Character,
    ) -> dict:
        """
        模擬 PvP 戰鬥，回傳結果字典：
        {
            "winner": Character,
            "loser": Character,
            "battle_log": [str, ...],   # 逐回合事件描述
            "turns": int,
            "draw": bool
        }
        """
        # 深拷貝以免修改到真實角色資料
        import copy
        a = copy.deepcopy(p1)
        b = copy.deepcopy(p2)

        # 確保 HP 滿血進場
        a.hp = a.max_hp
        b.hp = b.max_hp

        # 由 DEX 决定先手；同 DEX 時隨機公平決定
        if a.stats.get("DEX", 10) > b.stats.get("DEX", 10):
            first, second = a, b
        elif a.stats.get("DEX", 10) < b.stats.get("DEX", 10):
            first, second = b, a
        else:
            first, second = random.choice([(a, b), (b, a)])

        log: list[str] = [
            f"⚔️ 決鬥開始！【{a.name}】(HP:{a.hp}) vs 【{b.name}】(HP:{b.hp})",
            f"🎲 先手：【{first.name}】（敏捷 {first.stats.get('DEX', 10)} 勝出）"
        ]

        turn = 0
        draw = False

        while True:
            turn += 1
            if turn > self.MAX_TURNS:
                draw = True
                log.append(f"💨 戰鬥超過 {self.MAX_TURNS} 回合，判定為平局！")
                break

            log.append(f"\n── 第 {turn} 回合 ──")

            # 先手攻擊
            alive_after = self._do_attack(first, second, log)
            if not alive_after:
                break

            # 後手攻擊
            alive_after = self._do_attack(second, first, log)
            if not alive_after:
                break

        if draw:
            return {
                "winner": None,
                "loser": None,
                "battle_log": log,
                "turns": turn,
                "draw": True,
                # 把原始角色名對應最終 HP 附上，方便 LLM 渲染
                "final_hp": {a.name: a.hp, b.name: b.hp}
            }

        # 判斷勝負（以原始物件名字比對）
        if first.hp <= 0:
            winner_orig = p2 if first.name == p1.name else p1
            loser_orig = p1 if first.name == p1.name else p2
        else:
            winner_orig = p1 if second.name == p2.name else p2
            loser_orig = p2 if second.name == p2.name else p1

        result = {
            "winner": winner_orig,
            "loser": loser_orig,
            "battle_log": log,
            "turns": turn,
            "draw": False,
            "final_hp": {a.name: a.hp, b.name: b.hp}
        }

        # 勝負獎懲：勝利方獲得 EXP，敗北方 HP 減半
        exp_gain = max(10, winner_orig.level * 25)
        winner_orig.gain_exp(exp_gain)
        loser_orig.hp = max(1, loser_orig.max_hp // 2)
        result["exp_gain"] = exp_gain

        return result


    # ──────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────

    def _do_attack(self, attacker: Character, defender: Character, log: list) -> bool:
        """
        執行一次攻擊，將事件加入 log。
        回傳 True=防守方仍存活，False=防守方死亡。
        """
        skill_id, skill_data = self._pick_skill(attacker)

        if skill_id and skill_data:
            # 消耗 MP
            mp_cost = skill_data.get("mp_cost", 0)
            attacker.mp = max(0, attacker.mp - mp_cost)
            skill_name = skill_data.get("name", skill_id)
            req_stat = skill_data.get("required_stat", "STR")
            action_label = f"施展【{skill_name}】"
        else:
            req_stat = "STR"
            action_label = "普通攻擊"

        # 命中判定
        stat_val = attacker.stats.get(req_stat, 10)
        skill_level = attacker.skills.get(skill_id, {}).get("level", 1) if skill_id else 1
        accuracy_penalty = skill_data.get("accuracy_penalty", 0) if skill_data else 0
        hit_chance = max(1, min(99, stat_val * 5 + skill_level * 10 + 15 + accuracy_penalty))
        roll = Dice.roll_d100()
        hit = roll <= hit_chance

        if not hit:
            log.append(f"  ❌ 【{attacker.name}】{action_label}，但被【{defender.name}】閃避了！（擲 {roll} > {hit_chance}）")
            return True

        # 傷害計算
        damage = self._calc_damage(attacker, defender, skill_id, skill_data)
        defender.hp = max(0, defender.hp - damage)
        log.append(
            f"  ✅ 【{attacker.name}】{action_label}，命中！對【{defender.name}】造成 {damage} 點傷害。"
            f"（{defender.name} HP: {defender.hp}/{defender.max_hp}）"
        )

        if defender.hp <= 0:
            log.append(f"💀 【{defender.name}】的 HP 歸零，倒下了！")
            return False
        return True

    def _pick_skill(self, character: Character) -> tuple[Optional[str], Optional[dict]]:
        """
        選取技能：優先選擇自己擁有、MP 足夠、且傷害最高的技能。
        若無合適技能，回傳 (None, None) 代表普通攻擊。
        """
        best_skill_id = None
        best_power = -1.0

        for skill_id, skill_lvl_data in character.skills.items():
            skill_data = self.skills_db.get(skill_id)
            if not skill_data:
                continue
            # 治癒技能在 PvP 中跳過（可依需求調整）
            if skill_data.get("is_healing", False):
                continue
            mp_cost = skill_data.get("mp_cost", 0)
            if character.mp < mp_cost:
                continue  # MP 不足

            # 粗估「威力」 = damage_multiplier * level_bonus
            multiplier = skill_data.get("damage_multiplier", 1.0)
            level = skill_lvl_data.get("level", 1)
            level_bonus = 1.0 + (level - 1) * 0.15
            power = multiplier * level_bonus

            if power > best_power:
                best_power = power
                best_skill_id = skill_id

        if best_skill_id:
            return best_skill_id, self.skills_db[best_skill_id]
        return None, None

    def _calc_damage(
        self,
        attacker: Character,
        defender: Character,
        skill_id: Optional[str],
        skill_data: Optional[dict],
    ) -> int:
        """計算傷害值"""
        if skill_data:
            dmg_dice = skill_data.get("damage_dice", "1d6")
            base_dmg = Dice.roll(dmg_dice)
            req_stat = skill_data.get("required_stat", "STR")
            stat_bonus = attacker.stats.get(req_stat, 10) // 5
            raw = base_dmg + stat_bonus

            multiplier = skill_data.get("damage_multiplier", 1.0)
            raw = int(raw * multiplier)

            level = attacker.skills.get(skill_id, {}).get("level", 1)
            level_mult = 1.0 + (level - 1) * 0.15
            raw = int(raw * level_mult)
        else:
            # 普通攻擊
            base_dmg = Dice.roll("1d8")
            stat_bonus = attacker.stats.get("STR", 10) // 4
            raw = base_dmg + stat_bonus

        # 防禦減傷（玩家對玩家，用 CON 當防禦，與 PvE 公式一致）
        defender_def = max(2, defender.stats.get("CON", 10) // 4)
        return max(1, raw - defender_def)

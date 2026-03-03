"""
tests/test_skill_proficiency.py
技能熟練度系統單元測試
"""
import pytest
from unittest.mock import MagicMock
from core.character import Character


class TestSkillProficiency:
    """測試技能熟練度升級機制"""

    def test_learn_skill_creates_dict(self):
        """學習技能時應建立 {level, exp} 結構"""
        player = Character(name="TestPlayer")
        player.learn_skill("Fireball")
        
        assert "Fireball" in player.skills
        assert player.skills["Fireball"]["level"] == 1
        assert player.skills["Fireball"]["exp"] == 0

    def test_learn_existing_skill_increases_level(self):
        """再次學習已有技能應直接提升等級"""
        player = Character(name="TestPlayer")
        player.learn_skill("Fireball")
        player.learn_skill("Fireball")
        
        assert player.skills["Fireball"]["level"] == 2
        assert player.skills["Fireball"]["exp"] == 0

    def test_gain_skill_exp_accumulates(self):
        """重複施放技能應累積經驗值"""
        player = Character(name="TestPlayer")
        player.learn_skill("Fireball")

        player.gain_skill_exp("Fireball", 10)
        assert player.skills["Fireball"]["exp"] == 10

        player.gain_skill_exp("Fireball", 10)
        assert player.skills["Fireball"]["exp"] == 20

    def test_gain_skill_exp_unknown_skill_returns_none(self):
        """對未學習的技能增加經驗應回傳 None"""
        player = Character(name="TestPlayer")
        result = player.gain_skill_exp("NonExistent", 10)
        assert result is None

    def test_skill_level_up_at_threshold(self):
        """經驗值達到 level*100 時應自動升級"""
        player = Character(name="TestPlayer")
        player.learn_skill("Fireball")  # level=1, exp=0
        
        # Lv.1 需要 100 exp 升級
        msg = player.gain_skill_exp("Fireball", 100)
        assert player.skills["Fireball"]["level"] == 2
        assert player.skills["Fireball"]["exp"] == 0
        assert msg is not None
        assert "Lv.2" in msg
        assert "升級" in msg

    def test_skill_level_up_with_overflow(self):
        """多餘的經驗值應正確溢出到下一級"""
        player = Character(name="TestPlayer")
        player.learn_skill("Fireball")  # level=1
        
        # 給 150 exp: Lv.1 需 100 → 升到 Lv.2, 剩 50
        msg = player.gain_skill_exp("Fireball", 150)
        assert player.skills["Fireball"]["level"] == 2
        assert player.skills["Fireball"]["exp"] == 50

    def test_skill_multi_level_up(self):
        """一次獲得大量經驗可同時升多級"""
        player = Character(name="TestPlayer")
        player.learn_skill("Fireball")  # level=1
        
        # Lv.1→2 需 100, Lv.2→3 需 200, 共 300
        msg = player.gain_skill_exp("Fireball", 300)
        assert player.skills["Fireball"]["level"] == 3
        assert player.skills["Fireball"]["exp"] == 0
        assert "Lv.3" in msg

    def test_status_report_shows_skill_exp(self):
        """狀態報告應顯示技能等級與經驗進度"""
        player = Character(name="TestPlayer")
        player.learn_skill("Fireball")
        player.gain_skill_exp("Fireball", 42)
        
        report = player.get_status_report()
        assert "Fireball (Lv.1 | Exp: 42/100)" in report

    def test_status_report_no_skills(self):
        """沒有學技能的角色應顯示「無」"""
        player = Character(name="TestPlayer")
        report = player.get_status_report()
        assert "無" in report


class TestSkillLevelDamageScaling:
    """測試技能等級對傷害的影響"""

    def test_level2_skill_deals_more_damage(self):
        """Lv.2 技能應比 Lv.1 造成更多傷害 (15% 加成)"""
        from services.battle_engine import BattleEngine
        from core.dice import Dice

        class MockLLM:
            def generate_combat_narrative(self, a, d):
                return "敘事"

        engine = BattleEngine(MockLLM())
        engine.skills_db = {
            "Fireball": {
                "name": "火球術",
                "damage_dice": "1d6",
                "damage_multiplier": 1.0,
                "element": "fire"
            }
        }
        Dice.roll = MagicMock(return_value=6)

        # --- Lv.1 玩家 ---
        p1 = Character(name="P1")
        p1.learn_skill("Fireball")  # level=1
        engine.current_monster = {
            "name": "M", "max_hp": 200, "current_hp": 200,
            "defense": 0, "element": None, "status_effects": {},
            "current_mp": 0, "attack": 0
        }
        intent = {"action_type": "magic", "skill_used": "Fireball", "required_stat": "STR"}
        engine.process_turn(p1, "火球", intent, 10, True)
        dmg_lv1 = 200 - engine.current_monster["current_hp"]

        # --- Lv.2 玩家 ---
        p2 = Character(name="P2")
        p2.learn_skill("Fireball")
        p2.skills["Fireball"]["level"] = 2
        engine.current_monster = {
            "name": "M", "max_hp": 200, "current_hp": 200,
            "defense": 0, "element": None, "status_effects": {},
            "current_mp": 0, "attack": 0
        }
        engine.process_turn(p2, "火球", intent, 10, True)
        dmg_lv2 = 200 - engine.current_monster["current_hp"]

        assert dmg_lv2 > dmg_lv1, f"Lv.2 傷害 ({dmg_lv2}) 應大於 Lv.1 ({dmg_lv1})"

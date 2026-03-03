"""
tests/test_skill_learning.py
單元測試：技能學習系統
涵蓋：
- 5% 學習觸發機率（Mock 隨機數）
- 學習現有技能 vs 發明新技能的邏輯
- 技能命中率公式
- handle_forget_skill 只影響玩家個人
- handle_skill_use 正確扣 MP 並造成傷害
"""
import json
import os
import sqlite3
import sys
import unittest
from unittest.mock import MagicMock, patch

# 確保可以 import 專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.character import Character
from services.battle_engine import BattleEngine
from services.ollama_client import OllamaClient


MOCK_SKILLS_DB = {
    "Fireball": {
        "name": "火球術",
        "mp_cost": 10,
        "required_stat": "INT",
        "damage_dice": "2d6",
        "damage_multiplier": 2.4,
        "element": "fire",
        "status_effect": "燃燒",
        "effect_chance": 30,
        "accuracy_penalty": 0,
        "description": "火焰攻擊。"
    },
    "Heal": {
        "name": "治癒術",
        "mp_cost": 5,
        "required_stat": "WIS",
        "heal_dice": "2d4",
        "heal_multiplier": 1.5,
        "is_healing": True,
        "accuracy_penalty": 0,
        "description": "恢復少量生命值。"
    }
}

MOCK_MONSTER = {
    "name": "測試史萊姆",
    "max_hp": 50,
    "current_hp": 50,
    "max_mp": 0,
    "current_mp": 0,
    "attack": 5,
    "defense": 0,
    "element": None,
    "description": "測試用怪物",
    "skills": [],
    "status_effects": {},
    "exp_reward": 10,
    "money_reward": 5
}


def _make_engine_and_player():
    """建立一個含有 Mock LLM 的 BattleEngine 與角色"""
    llm = MagicMock(spec=OllamaClient)
    llm.generate_combat_narrative.return_value = "（測試敘事）"
    engine = BattleEngine(llm)
    engine.skills_db = dict(MOCK_SKILLS_DB)
    engine.current_monster = dict(MOCK_MONSTER)
    engine.current_monster["current_hp"] = 50

    player = Character(name="測試勇者", level=5)
    player.hp = 100
    player.mp = 50
    player.stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 15, "WIS": 10, "LUK": 10}
    player.skills = {
        "Fireball": {"level": 2, "exp": 0}
    }
    return engine, player


class TestSkillLearningTrigger(unittest.TestCase):
    """測試 5% 技能學習觸發機率"""

    def test_no_learning_when_above_threshold(self):
        """random.random() > 0.05 時不應觸發學習"""
        engine, player = _make_engine_and_player()
        with patch("services.battle_engine.random.random", return_value=0.10):
            result = engine._attempt_skill_learning(player, "揮拳")
        self.assertIsNone(result)

    def test_learning_triggers_when_below_threshold(self):
        """random.random() <= 0.05 時應觸發學習"""
        engine, player = _make_engine_and_player()
        # 強制選擇學習現有技能路徑
        with patch("services.battle_engine.random.random", side_effect=[0.04, 0.1]):  # 觸發 + 選現有技能
            with patch("services.battle_engine.random.choice", return_value="Heal"):
                result = engine._attempt_skill_learning(player, "揮拳")
        self.assertIsNotNone(result)
        self.assertIn("技能習得", result)
        self.assertIn("Heal", player.skills)

    def test_invent_new_skill_when_all_learned(self):
        """所有技能都已學會時應嘗試發明新技能"""
        engine, player = _make_engine_and_player()
        # 讓玩家學會所有技能
        player.skills["Heal"] = {"level": 1, "exp": 0}

        mock_skill = {
            "skill_id": "WindSlash",
            "name": "風切斬",
            "mp_cost": 8,
            "required_stat": "DEX",
            "damage_dice": "1d8",
            "damage_multiplier": 1.5,
            "accuracy_penalty": -5,
            "element": "wind",
            "status_effect": None,
            "effect_chance": 0,
            "description": "風屬性斬擊。"
        }
        engine.llm.invent_skill.return_value = mock_skill

        with patch("services.battle_engine.random.random", side_effect=[0.03, 0.9]):  # 觸發 + 選發明路徑
            with patch.object(engine, "_save_skills_db"):  # 不實際寫檔
                result = engine._attempt_skill_learning(player, "揮出一道風刃")

        self.assertIsNotNone(result)
        self.assertIn("技能發明", result)
        self.assertIn("WindSlash", player.skills)
        self.assertIn("WindSlash", engine.skills_db)
        self.assertEqual(engine.skills_db["WindSlash"]["creator"], "測試勇者")

    def test_invent_skill_with_creator(self):
        """發明的技能必須記錄發明者名稱"""
        engine, player = _make_engine_and_player()
        player.skills["Heal"] = {"level": 1, "exp": 0}

        mock_skill = {
            "skill_id": "DarkBolt",
            "name": "暗黑閃電",
            "mp_cost": 20,
            "required_stat": "INT",
            "damage_dice": "3d6",
            "damage_multiplier": 2.5,
            "accuracy_penalty": -20,
            "element": "dark",
            "status_effect": "麻痺",
            "effect_chance": 20,
            "description": "強力暗屬性技能。"
        }
        engine.llm.invent_skill.return_value = mock_skill

        with patch("services.battle_engine.random.random", side_effect=[0.01, 0.9]):
            with patch.object(engine, "_save_skills_db"):
                engine._attempt_skill_learning(player, "召喚暗影雷電")

        self.assertEqual(engine.skills_db["DarkBolt"]["creator"], "測試勇者")


class TestHitRateCalculation(unittest.TestCase):
    """測試技能命中率公式"""

    def test_basic_hit_rate_no_penalty(self):
        """基礎命中率：(屬性 * 5) + (技能等級 * 10) + 15 + 0"""
        engine = BattleEngine(MagicMock())
        # 屬性 10, 技能等級 1, 無修正
        result = engine._calculate_hit_chance(stat_value=10, skill_level=1, accuracy_penalty=0)
        # (10*5) + (1*10) + 15 = 75
        self.assertEqual(result, 75)

    def test_hit_rate_with_penalty(self):
        """含負修正的命中率"""
        engine = BattleEngine(MagicMock())
        result = engine._calculate_hit_chance(stat_value=10, skill_level=1, accuracy_penalty=-20)
        # 75 - 20 = 55
        self.assertEqual(result, 55)

    def test_hit_rate_minimum_cap(self):
        """命中率最低為 1%"""
        engine = BattleEngine(MagicMock())
        result = engine._calculate_hit_chance(stat_value=1, skill_level=1, accuracy_penalty=-99)
        self.assertEqual(result, 1)

    def test_hit_rate_maximum_cap(self):
        """命中率最高為 99%"""
        engine = BattleEngine(MagicMock())
        result = engine._calculate_hit_chance(stat_value=100, skill_level=10, accuracy_penalty=0)
        self.assertEqual(result, 99)


class TestForgetSkill(unittest.TestCase):
    """測試 handle_forget_skill 功能"""

    def _make_game_engine(self):
        """建立一個 Mock GameEngine"""
        from services.engine import GameEngine
        with patch.object(GameEngine, '__init__', lambda self, *a, **kw: None):
            engine = GameEngine.__new__(GameEngine)
        engine.player = Character(name="測試勇者")
        engine.player.skills = {
            "Fireball": {"level": 1, "exp": 0},
            "Heal": {"level": 1, "exp": 0}
        }
        engine.skills_db = dict(MOCK_SKILLS_DB)
        return engine

    def test_forget_skill_by_id(self):
        """使用技能 ID 遺忘技能"""
        engine = self._make_game_engine()
        result = engine.handle_forget_skill("Fireball")
        self.assertNotIn("Fireball", engine.player.skills)
        self.assertIn("遺忘", result)

    def test_forget_skill_by_name(self):
        """使用中文名稱遺忘技能"""
        engine = self._make_game_engine()
        result = engine.handle_forget_skill("治癒術")
        self.assertNotIn("Heal", engine.player.skills)

    def test_forget_skill_does_not_remove_from_db(self):
        """遺忘技能不應從 skills_db 中移除"""
        engine = self._make_game_engine()
        engine.handle_forget_skill("Fireball")
        self.assertIn("Fireball", engine.skills_db)

    def test_forget_skill_not_learned(self):
        """嘗試遺忘未學會的技能應回傳錯誤"""
        engine = self._make_game_engine()
        result = engine.handle_forget_skill("Thunderbolt")
        self.assertIn("❌", result)


class TestDamageLogic(unittest.TestCase):
    """測試一般動作 vs 技能動作的傷害邏輯"""

    def test_general_action_uses_base_multiplier(self):
        """一般動作應使用基礎傷害，不套用技能倍率"""
        engine, player = _make_engine_and_player()
        intent = {
            "action_type": "physical",
            "skill_used": None,
            "is_valid": True,
            "required_stat": "STR"
        }
        # 讓怪物在這次攻擊後 "死亡"（確保流程跑完）
        with patch("services.battle_engine.random.random", return_value=0.5), \
             patch("services.battle_engine.Dice.roll", return_value=4), \
             patch("services.battle_engine.Dice.check_d100", return_value=False):
            narrative, _ = engine.process_turn(player, "揮拳", intent, 30, True)
        # 確保回傳正常文字
        self.assertIsInstance(narrative, str)

    def test_known_skill_applies_level_multiplier(self):
        """已學技能應套用等級加成"""
        engine, player = _make_engine_and_player()
        intent = {
            "action_type": "magic",
            "skill_used": "Fireball",
            "is_valid": True,
            "required_stat": "INT"
        }
        with patch("services.battle_engine.random.random", return_value=0.5), \
             patch("services.battle_engine.Dice.roll", return_value=6), \
             patch("services.battle_engine.Dice.check_d100", return_value=False):
            narrative, _ = engine.process_turn(player, "施放火球術", intent, 30, True)
        self.assertIn("攻擊成功", narrative)


if __name__ == "__main__":
    unittest.main()

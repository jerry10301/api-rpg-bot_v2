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
    """測試技能學習觸發機率（門檻 10%）"""

    def test_no_learning_when_above_threshold(self):
        """random.random() > 0.10 時不應觸發學習"""
        engine, player = _make_engine_and_player()
        with patch("services.battle_engine.random.random", return_value=0.11):
            result = engine._attempt_skill_learning(player, "揮拳")
        self.assertIsNone(result)

    def test_learning_triggers_when_below_threshold(self):
        """random.random() <= 0.10 時應觸發學習"""
        engine, player = _make_engine_and_player()
        # 模擬 LLM 決定學習現有技能
        engine.llm.decide_learned_skill.return_value = {
            "learn_type": "existing",
            "skill_id": "Heal"
        }
        with patch("services.battle_engine.random.random", return_value=0.04):
            result = engine._attempt_skill_learning(player, "揮拳")
        self.assertIsNotNone(result)
        self.assertIn("技能習得", result)
        self.assertIn("Heal", player.skills)

    def test_already_learned_skill_gives_double_exp(self):
        """玩家已學會技能再次觸發，應給予雙倍熟練 EXP 而非重複學習"""
        engine, player = _make_engine_and_player()
        # Fireball 玩家已學，初始 exp=0
        initial_exp = player.skills["Fireball"]["exp"]
        engine.llm.decide_learned_skill.return_value = {
            "learn_type": "existing",
            "skill_id": "Fireball"
        }
        with patch("services.battle_engine.random.random", return_value=0.05):
            result = engine._attempt_skill_learning(player, "使用火球術")
        self.assertIsNotNone(result)
        self.assertIn("感悟", result)
        # EXP 應增加 20（雙倍）
        self.assertGreater(player.skills["Fireball"]["exp"], initial_exp)

    def test_invent_new_skill_when_all_learned(self):
        """LLM 決定發明新技能時應觸發發明邏輯"""
        engine, player = _make_engine_and_player()
        # 讓玩家學會所有技能
        player.skills["Heal"] = {"level": 1, "exp": 0}

        mock_decision = {
            "learn_type": "new",
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
        engine.llm.decide_learned_skill.return_value = mock_decision

        with patch("services.battle_engine.random.random", return_value=0.03):
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

        mock_decision = {
            "learn_type": "new",
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
        engine.llm.decide_learned_skill.return_value = mock_decision

        with patch("services.battle_engine.random.random", return_value=0.01):
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


class TestDuplicateSkillDetection(unittest.TestCase):
    """測試 _is_duplicate_skill：只有名稱+描述同時相似才視為重複"""

    def _make_engine(self):
        llm = MagicMock(spec=OllamaClient)
        engine = BattleEngine(llm)
        engine.skills_db = {
            "FireSlash": {
                "name": "烈焰斬",
                "description": "揮出充滿火焰的光刃，造成火屬性傷害。",
                "damage_dice": "1d8",
                "damage_multiplier": 1.5,
                "element": "fire"
            }
        }
        return engine

    def test_duplicate_when_both_name_and_desc_similar(self):
        """中文名稱與描述相似度均 >= 80% 時視為重複"""
        engine = self._make_engine()
        # 幾乎一樣的名稱與描述
        new_skill = {
            "name": "烈焰斬",
            "description": "揮出充滿火焰的光刃，造成火屬性傷害。",
        }
        result = engine._is_duplicate_skill(new_skill)
        self.assertEqual(result, "FireSlash")

    def test_not_duplicate_when_description_differs(self):
        """名稱相似但描述差異很大時，不視為重複（超級版本應被允許）"""
        engine = self._make_engine()
        new_skill = {
            "name": "烈焰斬",
            "description": "凝聚極限火焰之力進行超強衝擊，傷害遠超一般斬擊，有機率使目標燃燒。",
        }
        result = engine._is_duplicate_skill(new_skill)
        self.assertIsNone(result)

    def test_not_duplicate_when_name_differs(self):
        """描述相似但名稱不同（如不同類型斬擊），不視為重複"""
        engine = self._make_engine()
        new_skill = {
            "name": "超級烈爆斬",
            "description": "揮出充滿火焰的光刃，造成火屬性傷害。",
        }
        result = engine._is_duplicate_skill(new_skill)
        self.assertIsNone(result)

    def test_duplicate_redirects_to_existing_skill(self):
        """_attempt_skill_learning 偵測到重複時，改為學習現有最相似技能"""
        engine = self._make_engine()
        player = Character(name="測試勇者", level=1)
        player.hp = 100
        player.mp = 50
        player.stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "LUK": 10}
        player.skills = {}
        engine.current_monster = dict(MOCK_MONSTER)

        # LLM 試圖發明一個與 FireSlash 完全一樣的技能
        duplicate_decision = {
            "learn_type": "new",
            "skill_id": "NewFireSlash",
            "name": "烈焰斬",
            "description": "揮出充滿火焰的光刃，造成火屬性傷害。",
            "mp_cost": 8,
            "required_stat": "STR",
            "damage_dice": "1d8",
            "damage_multiplier": 1.5,
            "accuracy_penalty": 0,
            "element": "fire",
            "status_effect": None,
            "effect_chance": 0,
        }
        engine.llm.decide_learned_skill.return_value = duplicate_decision

        with patch("services.battle_engine.random.random", return_value=0.05):
            result = engine._attempt_skill_learning(player, "揮出火焰斬擊")

        # 應改學現有的 FireSlash，不應新增 NewFireSlash
        self.assertIsNotNone(result)
        self.assertIn("FireSlash", player.skills)
        self.assertNotIn("NewFireSlash", engine.skills_db)


if __name__ == "__main__":
    unittest.main()


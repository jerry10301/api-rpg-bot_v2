import unittest
import os
import json
from unittest.mock import MagicMock, patch

from services.engine import GameEngine
from core.character import Character
from services.ollama_client import OllamaClient
from db.player_repository import PlayerRepository

class TestCombatCommands(unittest.TestCase):
    @patch('services.engine.init_db')
    @patch('services.engine.PlayerRepository')
    @patch('services.engine.OllamaClient')
    def setUp(self, mock_ollama_class, mock_repo_class, mock_init_db):
        # Mock Repository
        self.mock_repo = mock_repo_class.return_value
        self.mock_player = Character(name="Test Player", stats={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "LUK": 10})
        self.mock_player.hp = 100
        self.mock_player.max_hp = 100
        
        self.mock_repo.load_player.return_value = self.mock_player
        self.mock_repo.load_active_quests.return_value = {}
        self.mock_repo.load_battle_state.return_value = None
        
        # Mock Ollama Client
        self.mock_llm = mock_ollama_class.return_value
        self.mock_llm.generate_combat_narrative.return_value = "Mock combat narrative."
        
        # Initialize Engine (will use mocked dependencies)
        self.engine = GameEngine("test_user_id")

    def test_attack_fails_outside_combat(self):
        """測試 /attack 在非戰鬥狀態下應該失敗 (會回傳提示訊息)"""
        action_text = "攻擊"
        
        result = self.engine.handle_action(action_text)
        
        self.assertIn("你目前不在戰鬥中", result)
        self.assertFalse(self.engine.battle.is_in_battle())

    def test_escape_fails_outside_combat(self):
        """測試 /escape 在非戰鬥狀態下應該失敗 (會回傳提示訊息)"""
        result = self.engine.handle_escape()
        
        self.assertIn("不在戰鬥中", result)
        self.assertFalse(self.engine.battle.is_in_battle())

    @patch('core.dice.Dice.roll_d100')
    def test_escape_in_combat_success(self, mock_roll):
        """測試在戰鬥中 /escape 成功的情境"""
        mock_roll.return_value = 10  # Guaranteed success (less than target chance)
        
        # Start a battle manually
        self.engine.battle.current_monster = {
            "id": "slime", "name": "史萊姆", "max_hp": 10, "current_hp": 10, 
            "max_mp": 0, "current_mp": 0,
            "attack": 2, "defense": 0
        }
        
        self.mock_llm.generate_combat_narrative.return_value = "玩家逃跑成功！"
        result = self.engine.handle_escape()
        
        # Verify narrative contains success
        self.assertIn("玩家逃跑成功！", result)
        # Verify combat ended
        self.assertFalse(self.engine.battle.is_in_battle())
        
    @patch('core.dice.Dice.roll_d100')
    def test_escape_in_combat_failure(self, mock_roll):
        """測試在戰鬥中 /escape 失敗的情境 (會受到反擊)"""
        mock_roll.return_value = 99  # Guaranteed failure
        
        # Start a battle manually
        self.engine.battle.current_monster = {
            "id": "slime", "name": "史萊姆", "max_hp": 10, "current_hp": 10, 
            "max_mp": 0, "current_mp": 0,
            "attack": 2, "defense": 0
        }
        
        self.mock_llm.generate_combat_narrative.return_value = "玩家逃跑失敗！怪物趁機反擊。"
        result = self.engine.handle_escape()
        
        # Verify narrative contains failure
        self.assertIn("玩家逃跑失敗", result)
        # Verify still in combat because they didn't escape
        self.assertTrue(self.engine.battle.is_in_battle())

    @patch('core.dice.Dice.roll_d100')
    def test_attack_in_combat(self, mock_roll):
        """測試在戰鬥中 /attack 的情境"""
        mock_roll.return_value = 10  # Guaranteed success for player action
        
        # Start a battle manually
        self.engine.battle.current_monster = {
            "id": "slime", "name": "史萊姆", "max_hp": 10, "current_hp": 10, 
            "max_mp": 0, "current_mp": 0,
            "attack": 2, "defense": 0
        }
        
        self.mock_llm.parse_intent.return_value = {
            "action_type": "physical",
            "is_valid": True,
            "required_stat": "STR"
        }
        
        self.mock_llm.generate_combat_narrative.return_value = "玩家攻擊成功！"
        result = self.engine.handle_action("揮出猛烈的一拳")
        
        # Ensure process_turn was actually used
        self.assertIn("玩家攻擊成功", result)

if __name__ == '__main__':
    unittest.main()

import pytest
import os
import json
from core.character import Character
from services.battle_engine import BattleEngine
from services.ollama_client import OllamaClient
from unittest.mock import MagicMock

class MockLLM:
    def generate_combat_narrative(self, action, data):
        return "戰鬥敘事文字"

@pytest.fixture
def battle_engine():
    llm = MockLLM()
    engine = BattleEngine(llm)
    # 確保資料正確載入 (使用測試資料)
    engine.skills_db = {
        "Fireball": {
            "name": "火球術",
            "damage_dice": "1d6",
            "damage_multiplier": 2.0,
            "element": "fire",
            "status_effect": "燃燒",
            "effect_chance": 100
        },
        "FrostBolt": {
            "name": "冰箭術",
            "damage_dice": "1d6",
            "element": "ice",
            "status_effect": "凍結",
            "effect_chance": 100
        }
    }
    return engine

def test_element_counter(battle_engine):
    player = Character(name="TestPlayer")
    player.learn_skill("Fireball")  # level=1, exp=0
    # 設定怪物為 ice 屬性 (被 fire 克制)
    battle_engine.current_monster = {
        "name": "TestMonster",
        "max_hp": 100,
        "current_hp": 100,
        "defense": 0,
        "element": "ice", # 被 fire 克制
        "status_effects": {},
        "current_mp": 0,
        "attack": 0
    }
    
    # 傷害計算過程 (依 battle_engine.py 程式碼順序):
    # 1. roll=6, stat_bonus=10//5=2 → raw=8
    # 2. damage_multiplier=2.0 → raw=int(8*2.0)=16
    # 3. skill_bonus=level(1)*2=2 → raw=16+2=18
    # 4. level_multiplier=1.0 (Lv.1) → raw=int(18*1.0)=18
    # 5. element_mult=1.5 (fire→ice) → raw=int(18*1.5)=27
    # 6. defense=0 → final=max(1,27-0)=27
    from core.dice import Dice
    Dice.roll = MagicMock(return_value=6)
    
    intent = {"action_type": "magic", "skill_used": "Fireball", "required_stat": "STR"}
    narrative, over = battle_engine.process_turn(player, "使用火球術", intent, 10, True)
    
    assert "元素克制" in narrative
    # 100 - 27 = 73
    assert battle_engine.current_monster["current_hp"] == 73
    # 驗證施放後獲得熟練度
    assert player.skills["Fireball"]["exp"] == 10

def test_status_effect_burning(battle_engine):
    # __post_init__ 會補滿 HP，所以直接用 max_hp
    player = Character(name="TestPlayer", stats={"STR":10,"DEX":10,"CON":10,"INT":10,"WIS":10,"LUK":10})
    # 強制設定 HP
    player.max_hp = 100
    player.hp = 100
    player.apply_status("燃燒", 3)
    
    # 燃燒扣 5% HP = 100 * 0.05 = 5
    messages = player.process_status_effects()
    assert player.hp == 95
    assert "燃燒灼痛" in messages[0]
    assert player.status_effects["燃燒"] == 2

def test_frozen_skips_turn(battle_engine):
    player = Character(name="TestPlayer")
    # duration 需要設為 2，因為 process_status_effects() 會先扣 1 回合
    # 扣完後剩 1 回合，凍結仍在 status_effects 中，才能阻止行動
    player.apply_status("凍結", 2)
    
    battle_engine.current_monster = {
        "name": "TestMonster",
        "hp": 100,
        "current_hp": 100,
        "defense": 0,
        "element": "none",
        "current_mp": 0,
        "status_effects": {},
        "attack": 10
    }
    
    # 確保怪物反擊一定命中 (玩家閃避失敗)
    from core.dice import Dice
    Dice.check_d100 = MagicMock(return_value=False)
    
    intent = {"action_type": "physical"}
    full_narrative, over = battle_engine.process_turn(player, "攻擊", intent, 10, True)
    
    assert "目前的狀態無法發起攻擊" in full_narrative
    # 玩家不能動，但怪物反擊一定命中
    assert player.hp < player.max_hp

def test_monster_status_effect(battle_engine):
    player = Character(name="TestPlayer")
    battle_engine.current_monster = {
        "name": "TestMonster",
        "hp": 100,
        "current_hp": 100,
        "defense": 0,
        "element": "none",
        "status_effects": {"燃燒": 1},
        "current_mp": 0,
        "attack": 0
    }
    
    # 回合開始會處理狀態
    # player_success=False 確保玩家不會額外造成傷害，只測試燃燒 DOT
    intent = {"action_type": "physical"}
    full_narrative, over = battle_engine.process_turn(player, "等待", intent, 10, False)
    
    # 100 - 5 (燃燒 5% max_hp) = 95
    assert battle_engine.current_monster["current_hp"] == 95
    assert "TestMonster 受到燃燒傷害" in full_narrative

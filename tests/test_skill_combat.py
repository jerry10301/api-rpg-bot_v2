import pytest
import random
from unittest.mock import MagicMock
from core.character import Character
from services.battle_engine import BattleEngine

@pytest.fixture
def mock_ollama():
    return MagicMock()

@pytest.fixture
def battle_engine(mock_ollama):
    engine = BattleEngine(mock_ollama)
    # 模擬技能數據以確保測試穩定
    engine.skills_db = {
        "Fireball": {
            "name": "火球術",
            "mp_cost": 10,
            "damage_dice": "2d6",
            "damage_multiplier": 1.5,
            "required_stat": "INT"
        },
        "Heal": {
            "name": "治癒術",
            "mp_cost": 5,
            "heal_dice": "2d4",
            "is_healing": True,
            "required_stat": "WIS"
        },
        "AcidSpit": {
            "name": "酸液噴射",
            "mp_cost": 3,
            "damage_dice": "1d4",
            "damage_multiplier": 1.0,
            "required_stat": "INT"
        }
    }
    return engine

@pytest.fixture
def player():
    return Character(name="Test Hero")


# ======= 玩家技能測試 =======

def test_skill_damage_calculation(battle_engine, player):
    """玩家施放火球術應對怪物造成傷害"""
    battle_engine.current_monster = {
        "name": "Dummy",
        "current_hp": 100,
        "max_hp": 100,
        "max_mp": 0,
        "current_mp": 0,
        "skills": [],
        "attack": 10,
        "defense": 0
    }

    intent = {
        "action_type": "magic",
        "skill_used": "Fireball",
        "required_stat": "INT"
    }

    # 火球術 2d6 -> 範圍 2-12
    # 倍率 1.5 -> 範圍 3-18
    # 屬性加成 (INT 10 // 5) = 2 -> (基礎+加成)*倍率 = (2~12 + 2) * 1.5 = 6 ~ 21
    narrative, is_dead = battle_engine.process_turn(player, "施放火球", intent, player_roll=10, player_success=True)

    # 檢查怪物 HP 是否減少
    assert battle_engine.current_monster["current_hp"] < 100
    damage_dealt = 100 - battle_engine.current_monster["current_hp"]
    assert 6 <= damage_dealt <= 21


def test_skill_healing(battle_engine, player):
    """玩家使用治癒術應恢復生命值"""
    battle_engine.current_monster = {
        "name": "Dummy",
        "current_hp": 100,
        "max_hp": 100,
        "max_mp": 0,
        "current_mp": 0,
        "skills": [],
        "attack": 0,
        "defense": 0
    }
    player.hp = 50
    player.max_hp = 100

    intent = {
        "action_type": "magic",
        "skill_used": "Heal",
        "required_stat": "WIS"
    }

    # 治癒術 2d4 -> 2-8
    battle_engine.process_turn(player, "使用治癒", intent, player_roll=10, player_success=True)

    assert player.hp > 50
    assert player.hp <= 58


# ======= 怪物 MP 測試 =======

def test_monster_no_mp_physical_only(battle_engine, player):
    """怪物 MP=0 時，無論有無技能，反擊只走物理路徑，current_mp 不變"""
    battle_engine.current_monster = {
        "name": "哥布林",
        "current_hp": 30,
        "max_hp": 30,
        "max_mp": 0,
        "current_mp": 0,
        "skills": ["Fireball"],   # 有技能但無 MP
        "attack": 5,
        "defense": 2
    }

    player_hp_before = player.hp
    # 玩家故意失敗（確保怪物一定會反擊）
    intent = {"action_type": "physical", "skill_used": None, "required_stat": "STR"}

    # 執行多回合確保不消耗 MP
    for _ in range(10):
        if not battle_engine.is_in_battle():
            break
        battle_engine.process_turn(player, "普通攻擊", intent, player_roll=1, player_success=False)

    # current_mp 應始終為 0
    if battle_engine.current_monster:
        assert battle_engine.current_monster["current_mp"] == 0, "MP=0 時不應有任何 MP 消耗"


def test_monster_mp_decreases_when_skill_used(battle_engine, player):
    """怪物有 MP 且有技能時，多回合後 MP 應有機會減少"""
    initial_mp = 40
    battle_engine.current_monster = {
        "name": "森林巫婆",
        "current_hp": 25,
        "max_hp": 25,
        "max_mp": initial_mp,
        "current_mp": initial_mp,
        "skills": ["Fireball"],  # mp_cost=10
        "attack": 3,
        "defense": 1
    }

    intent = {"action_type": "physical", "skill_used": None, "required_stat": "STR"}

    # 固定隨機種子，確保 40% 施法機率至少觸發一次（種子 42 在 20 次中必定觸發）
    random.seed(42)
    mp_consumed = False
    for _ in range(20):
        if not battle_engine.is_in_battle():
            break
        battle_engine.process_turn(player, "普通攻擊", intent, player_roll=1, player_success=False)
        if battle_engine.current_monster and battle_engine.current_monster["current_mp"] < initial_mp:
            mp_consumed = True
            break

    assert mp_consumed, "怪物在 20 回合內應至少施放一次技能並消耗 MP"


def test_monster_mp_cannot_go_negative(battle_engine, player):
    """怪物 MP 消耗後不得低於 0"""
    battle_engine.current_monster = {
        "name": "森林巫婆",
        "current_hp": 25,
        "max_hp": 25,
        "max_mp": 3,
        "current_mp": 3,   # 只夠施放一次 AcidSpit (cost=3)
        "skills": ["AcidSpit"],
        "attack": 3,
        "defense": 1
    }

    intent = {"action_type": "physical", "skill_used": None, "required_stat": "STR"}

    random.seed(0)  # 確保固定結果
    for _ in range(15):
        if not battle_engine.is_in_battle():
            break
        battle_engine.process_turn(player, "普通攻擊", intent, player_roll=1, player_success=False)
        if battle_engine.current_monster:
            assert battle_engine.current_monster["current_mp"] >= 0, "怪物 MP 不應低於 0"

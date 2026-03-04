"""
tests/test_pvp.py
PvP 功能單元測試：PvPManager 邀請狀態管理 + PvPEngine 戰鬥模擬
"""
import pytest
from unittest.mock import MagicMock, patch
from core.character import Character
from core.pvp_manager import PvPManager
from services.pvp_engine import PvPEngine


# ─── 共用 Fixtures ────────────────────────────────────────────────

@pytest.fixture
def pvp_manager():
    return PvPManager()


@pytest.fixture
def skills_db():
    """簡易技能資料庫供測試使用"""
    return {
        "Fireball": {
            "name": "火球術",
            "mp_cost": 10,
            "required_stat": "INT",
            "damage_dice": "2d6",
            "damage_multiplier": 1.5,
            "accuracy_penalty": 0,
            "element": "fire",
            "description": "發射一顆燃燒的火球。",
        },
        "SwordSlash": {
            "name": "劍斬",
            "mp_cost": 5,
            "required_stat": "STR",
            "damage_dice": "1d8",
            "damage_multiplier": 1.2,
            "accuracy_penalty": 0,
            "element": "none",
            "description": "強力一斬。",
        },
    }


@pytest.fixture
def pvp_engine(skills_db):
    return PvPEngine(skills_db)


def _make_char(name: str, hp: int = 200, mp: int = 100, skills: dict = None) -> Character:
    char = Character(name=name)
    char.max_hp = hp
    char.hp = hp
    char.max_mp = mp
    char.mp = mp
    char.stats = {"STR": 15, "DEX": 12, "CON": 12, "INT": 15, "WIS": 10, "LUK": 10}
    char.skills = skills or {}
    return char


# ─── PvPManager Tests ───────────────────────────────────────────


class TestPvPManager:
    def test_send_invite_success(self, pvp_manager):
        """正常發送邀請"""
        result = pvp_manager.send_invite("player1", "player2")
        assert result is True
        assert pvp_manager.get_invite("player2") == "player1"

    def test_send_invite_to_self_returns_false(self, pvp_manager):
        """不能向自己發送邀請"""
        result = pvp_manager.send_invite("player1", "player1")
        assert result is False

    def test_invite_overwrite(self, pvp_manager):
        """後來的邀請會覆蓋舊邀請"""
        pvp_manager.send_invite("player1", "player3")
        pvp_manager.send_invite("player2", "player3")
        assert pvp_manager.get_invite("player3") == "player2"

    def test_remove_invite(self, pvp_manager):
        """移除邀請後應無記錄"""
        pvp_manager.send_invite("player1", "player2")
        pvp_manager.remove_invite("player2")
        assert pvp_manager.get_invite("player2") is None

    def test_has_pending_invite(self, pvp_manager):
        """has_pending_invite 應反映正確邀請狀態"""
        assert pvp_manager.has_pending_invite("player2") is False
        pvp_manager.send_invite("player1", "player2")
        assert pvp_manager.has_pending_invite("player2") is True
        pvp_manager.remove_invite("player2")
        assert pvp_manager.has_pending_invite("player2") is False

    def test_get_invite_no_invite(self, pvp_manager):
        """無邀請時應回傳 None"""
        assert pvp_manager.get_invite("nonexistent") is None


# ─── PvPEngine Tests ───────────────────────────────────────────


class TestPvPEngine:
    def test_simulation_has_winner_or_draw(self, pvp_engine):
        """模擬必定回傳勝負或平局"""
        p1 = _make_char("勇者 A")
        p2 = _make_char("法師 B")

        result = pvp_engine.simulate(p1, p2)

        assert "winner" in result
        assert "loser" in result
        assert "turns" in result
        assert "draw" in result
        assert "battle_log" in result
        assert isinstance(result["turns"], int)
        assert result["turns"] >= 1

    def test_winner_and_loser_are_different_players(self, pvp_engine):
        """勝者與敗者不應為同一玩家"""
        p1 = _make_char("坦克", hp=500)
        p2 = _make_char("弱雞", hp=30)

        result = pvp_engine.simulate(p1, p2)
        if not result["draw"]:
            assert result["winner"] is not None
            assert result["loser"] is not None
            assert result["winner"].name != result["loser"].name

    def test_simulation_does_not_modify_originals(self, pvp_engine):
        """模擬不應修改原始角色的 HP"""
        p1 = _make_char("勇者")
        p2 = _make_char("惡魔")
        original_hp1 = p1.hp
        original_hp2 = p2.hp

        pvp_engine.simulate(p1, p2)

        assert p1.hp == original_hp1
        assert p2.hp == original_hp2

    def test_battle_log_is_non_empty(self, pvp_engine):
        """戰鬥紀錄不應為空"""
        p1 = _make_char("A")
        p2 = _make_char("B")
        result = pvp_engine.simulate(p1, p2)
        assert len(result["battle_log"]) > 0

    def test_simulation_with_skills(self, pvp_engine, skills_db):
        """技能戰士應能正常模擬"""
        p1 = _make_char("魔法師", mp=200, skills={"Fireball": {"level": 3, "exp": 0}})
        p2 = _make_char("戰士", skills={"SwordSlash": {"level": 2, "exp": 0}})
        p1.max_mp = 200
        p1.mp = 200

        result = pvp_engine.simulate(p1, p2)
        assert "draw" in result

    def test_max_turns_results_in_draw(self, pvp_engine):
        """超過最大回合數時應判平局"""
        # 給雙方極高 HP 讓戰鬥超過 MAX_TURNS
        p1 = _make_char("不死人甲", hp=999999)
        p2 = _make_char("不死人乙", hp=999999)
        # 統一攻擊力很低
        p1.stats = {"STR": 1, "DEX": 1, "CON": 1, "INT": 1, "WIS": 1, "LUK": 1}
        p2.stats = {"STR": 1, "DEX": 1, "CON": 1, "INT": 1, "WIS": 1, "LUK": 1}

        result = pvp_engine.simulate(p1, p2)
        assert result["draw"] is True

    def test_first_attacker_is_higher_dex(self, pvp_engine):
        """先手應為 DEX 較高的玩家"""
        p1 = _make_char("快手", hp=100)
        p2 = _make_char("慢郎", hp=100)
        p1.stats["DEX"] = 30
        p2.stats["DEX"] = 5

        result = pvp_engine.simulate(p1, p2)
        # 戰鬥紀錄第二行應包含先手名稱
        assert "快手" in result["battle_log"][1]

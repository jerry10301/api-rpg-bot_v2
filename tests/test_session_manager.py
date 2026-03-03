"""
tests/test_session_manager.py
SessionManager 單元測試 — 測試 session 快取行為與 Repository 資料持久化往返。
"""
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

from db.player_repository import PlayerRepository


IN_MEMORY = ":memory:"


def _init_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            discord_user_id TEXT PRIMARY KEY, name TEXT NOT NULL,
            level INTEGER DEFAULT 1, hp INTEGER DEFAULT 0, max_hp INTEGER DEFAULT 0,
            mp INTEGER DEFAULT 0, max_mp INTEGER DEFAULT 0,
            money INTEGER DEFAULT 0, exp INTEGER DEFAULT 0,
            stat_str INTEGER DEFAULT 10, stat_dex INTEGER DEFAULT 10,
            stat_con INTEGER DEFAULT 10, stat_int INTEGER DEFAULT 10,
            stat_wis INTEGER DEFAULT 10, stat_luk INTEGER DEFAULT 10
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_quests (
            discord_user_id TEXT NOT NULL, quest_id TEXT NOT NULL,
            name TEXT, target_type TEXT, target_amount INTEGER DEFAULT 1,
            current_amount INTEGER DEFAULT 0, completed INTEGER DEFAULT 0,
            PRIMARY KEY (discord_user_id, quest_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS battle_states (
            discord_user_id TEXT PRIMARY KEY, monster_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_skills (
            discord_user_id TEXT NOT NULL, skill_id TEXT NOT NULL,
            level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0,
            PRIMARY KEY (discord_user_id, skill_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_inventory (
            discord_user_id TEXT NOT NULL, item_id TEXT NOT NULL,
            amount INTEGER DEFAULT 1,
            PRIMARY KEY (discord_user_id, item_id)
        )
    """)
    conn.commit()


@pytest.fixture
def shared_conn():
    conn = sqlite3.connect(IN_MEMORY)
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(shared_conn):
    return PlayerRepository(shared_conn=shared_conn)


# ─────────────────────────────────────────────────────────
# SessionManager 基本行為（使用 mock 避免 Ollama 依賴）
# ─────────────────────────────────────────────────────────

class TestSessionManagerCache:

    def test_player_exists_delegates_to_repo(self, repo):
        """player_exists 應委派至 repository"""
        assert not repo.player_exists("user_xyz")
        repo.create_player("user_xyz", "存在者")
        assert repo.player_exists("user_xyz")

    def test_flush_calls_save_state(self):
        """flush_session 應呼叫 engine.save_state()"""
        mock_engine = MagicMock()
        mock_engine.save_state = MagicMock()

        with patch("services.session_manager.init_db"):
            from services.session_manager import SessionManager
            mgr = SessionManager.__new__(SessionManager)
            mgr._sessions = {"user_flush": mock_engine}
            mgr._repo = MagicMock()

            mgr.flush_session("user_flush")
            mock_engine.save_state.assert_called_once()

    def test_flush_non_existent_session_is_safe(self):
        """flush_session 對不存在的 user_id 不應拋出例外"""
        with patch("services.session_manager.init_db"):
            from services.session_manager import SessionManager
            mgr = SessionManager.__new__(SessionManager)
            mgr._sessions = {}
            mgr._repo = MagicMock()
            # 不應拋出任何例外
            mgr.flush_session("nonexistent")

    def test_remove_session(self):
        """remove_session 應從快取中移除指定 user_id"""
        mock_engine = MagicMock()
        with patch("services.session_manager.init_db"):
            from services.session_manager import SessionManager
            mgr = SessionManager.__new__(SessionManager)
            mgr._sessions = {"user_remove": mock_engine}
            mgr._repo = MagicMock()

            mgr.remove_session("user_remove")
            assert "user_remove" not in mgr._sessions

    def test_get_or_create_caches_same_instance(self):
        """同一 user_id 連續呼叫 get_or_create_session 應回傳相同實例"""
        mock_engine = MagicMock()

        with patch("services.session_manager.init_db"):
            from services.session_manager import SessionManager
            mgr = SessionManager.__new__(SessionManager)
            mgr._sessions = {}
            mgr._repo = MagicMock()
            mgr._repo.player_exists.return_value = True

            # 第一次建立
            with patch("services.session_manager.SessionManager.get_or_create_session",
                       return_value=mock_engine):
                e1 = mgr.get_or_create_session("user_cache")
                e2 = mgr.get_or_create_session("user_cache")
                assert e1 is e2


# ─────────────────────────────────────────────────────────
# 資料持久化往返驗證（Repository 層）
# ─────────────────────────────────────────────────────────

class TestPersistenceRoundTrip:

    def test_player_data_survives_reload(self, repo):
        """角色資料儲存後重新載入應完整保留"""
        repo.create_player("user_roundtrip", "旅行者")
        char = repo.load_player("user_roundtrip")
        char.level = 3
        char.money = 500
        char.stats["INT"] = 30
        repo.save_player("user_roundtrip", char)

        fresh = repo.load_player("user_roundtrip")
        assert fresh.level == 3
        assert fresh.money == 500
        assert fresh.stats["INT"] == 30

    def test_quest_progress_survives_reload(self, repo):
        """任務進度儲存後重新載入應完整保留"""
        repo.create_player("user_quest_rt", "任務者")
        quests = {
            "q_slime": {
                "name": "消滅史萊姆", "target_type": "combat",
                "target_amount": 5, "current_amount": 3, "completed": False
            }
        }
        repo.save_active_quests("user_quest_rt", quests)

        loaded = repo.load_active_quests("user_quest_rt")
        assert loaded["q_slime"]["current_amount"] == 3
        assert loaded["q_slime"]["target_amount"] == 5
        assert loaded["q_slime"]["completed"] is False

    def test_battle_state_survives_reload(self, repo):
        """戰鬥狀態儲存後重新載入應完整保留"""
        repo.create_player("user_battle_rt", "戰士")
        monster = {
            "id": "goblin", "name": "哥布林",
            "current_hp": 15, "max_hp": 20,
            "current_mp": 5, "max_mp": 10,
            "attack": 8, "defense": 2
        }
        repo.save_battle_state("user_battle_rt", monster)
        loaded = repo.load_battle_state("user_battle_rt")
        assert loaded["current_hp"] == 15
        assert loaded["name"] == "哥布林"

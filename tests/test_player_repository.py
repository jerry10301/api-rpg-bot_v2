"""
tests/test_player_repository.py
PlayerRepository 單元測試 — 使用 in-memory SQLite 共用連線隔離測試
"""
import json
import sqlite3
import pytest
from core.character import Character
from db.database import init_db
from db.player_repository import PlayerRepository

IN_MEMORY = ":memory:"


@pytest.fixture
def shared_conn():
    """建立共用 in-memory 連線並初始化資料表，測試完畢後關閉"""
    conn = sqlite3.connect(IN_MEMORY)
    conn.row_factory = sqlite3.Row
    init_db.__wrapped__(conn) if hasattr(init_db, "__wrapped__") else _init_tables(conn)
    yield conn
    conn.close()


def _init_tables(conn):
    """直接使用既有連線初始化資料表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            discord_user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL, level INTEGER DEFAULT 1,
            hp INTEGER DEFAULT 0, max_hp INTEGER DEFAULT 0,
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
def repo(shared_conn):
    """每個測試函式使用相同的 shared_conn，確保 init_db 和查詢在同一 in-memory DB"""
    return PlayerRepository(shared_conn=shared_conn)


# ─────────────────────────────────────────────────────────
# 玩家角色 CRUD
# ─────────────────────────────────────────────────────────

class TestPlayerCRUD:

    def test_player_not_exists_initially(self, repo):
        """新 DB 中玩家不存在"""
        assert not repo.player_exists("user_001")

    def test_create_player_returns_character(self, repo):
        """create_player 應回傳正確初始化的 Character"""
        char = repo.create_player("user_001", "勇者阿明")
        assert char.name == "勇者阿明"
        assert char.level == 1
        assert char.hp == char.max_hp
        assert "Heal" in char.skills
        assert "Fireball" in char.skills

    def test_player_exists_after_create(self, repo):
        """建立後 player_exists 應回傳 True"""
        repo.create_player("user_001", "勇者阿明")
        assert repo.player_exists("user_001")

    def test_load_player_returns_correct_data(self, repo):
        """load_player 應還原與 create_player 相同的資料"""
        repo.create_player("user_001", "勇者阿明")
        char = repo.load_player("user_001")
        assert char is not None
        assert char.name == "勇者阿明"
        assert char.level == 1
        assert char.money == 0

    def test_load_player_nonexistent_returns_none(self, repo):
        """不存在的用戶應回傳 None"""
        assert repo.load_player("ghost_user") is None

    def test_save_and_reload_player(self, repo):
        """save_player 後 load_player 應得到相同狀態"""
        repo.create_player("user_001", "勇者阿明")
        char = repo.load_player("user_001")

        # 修改角色狀態
        char.level = 5
        char.money = 200
        char.exp = 50
        char.stats["STR"] = 25
        char.learn_skill("IceBolt", 2)
        char.hp = 100
        char.mp = 80
        repo.save_player("user_001", char)

        # 重新載入並驗證
        reloaded = repo.load_player("user_001")
        assert reloaded.level == 5
        assert reloaded.money == 200
        assert reloaded.exp == 50
        assert reloaded.stats["STR"] == 25
        assert reloaded.skills.get("IceBolt") == {"level": 2, "exp": 0}
        assert reloaded.hp == 100
        assert reloaded.mp == 80


# ─────────────────────────────────────────────────────────
# 任務進度
# ─────────────────────────────────────────────────────────

class TestActiveQuests:

    def test_load_empty_quests(self, repo):
        """沒有任務記錄時應回傳空 dict"""
        repo.create_player("user_001", "勇者")
        result = repo.load_active_quests("user_001")
        assert result == {}

    def test_save_and_load_quests(self, repo):
        """儲存任務後，load 應還原完整資料"""
        repo.create_player("user_001", "勇者")
        quests = {
            "quest_001": {
                "name": "討伐史萊姆",
                "target_type": "combat",
                "target_amount": 3,
                "current_amount": 1,
                "completed": False
            }
        }
        repo.save_active_quests("user_001", quests)
        result = repo.load_active_quests("user_001")
        assert "quest_001" in result
        assert result["quest_001"]["name"] == "討伐史萊姆"
        assert result["quest_001"]["current_amount"] == 1
        assert result["quest_001"]["completed"] is False

    def test_save_quests_overwrites_previous(self, repo):
        """再次 save 應完全覆蓋舊資料"""
        repo.create_player("user_001", "勇者")
        old_quests = {"q1": {"name": "舊任務", "target_type": "work",
                              "target_amount": 1, "current_amount": 0, "completed": False}}
        repo.save_active_quests("user_001", old_quests)

        new_quests = {"q2": {"name": "新任務", "target_type": "combat",
                              "target_amount": 2, "current_amount": 2, "completed": True}}
        repo.save_active_quests("user_001", new_quests)

        result = repo.load_active_quests("user_001")
        assert "q1" not in result
        assert "q2" in result
        assert result["q2"]["completed"] is True


# ─────────────────────────────────────────────────────────
# 戰鬥狀態
# ─────────────────────────────────────────────────────────

class TestBattleState:

    def test_load_battle_state_none_initially(self, repo):
        """初始時戰鬥狀態應為 None"""
        repo.create_player("user_001", "勇者")
        assert repo.load_battle_state("user_001") is None

    def test_save_and_load_battle_state(self, repo):
        """儲存怪物快照後應能正確還原"""
        repo.create_player("user_001", "勇者")
        monster = {
            "id": "slime", "name": "史萊姆",
            "current_hp": 20, "max_hp": 30,
            "current_mp": 0, "max_mp": 0,
            "attack": 5, "defense": 0
        }
        repo.save_battle_state("user_001", monster)
        result = repo.load_battle_state("user_001")
        assert result is not None
        assert result["name"] == "史萊姆"
        assert result["current_hp"] == 20

    def test_clear_battle_state(self, repo):
        """clear_battle_state 後應回傳 None"""
        repo.create_player("user_001", "勇者")
        repo.save_battle_state("user_001", {"name": "哥布林", "current_hp": 10,
                                             "max_hp": 10, "current_mp": 0, "max_mp": 0,
                                             "attack": 3, "defense": 0})
        repo.clear_battle_state("user_001")
        assert repo.load_battle_state("user_001") is None

    def test_save_none_clears_battle_state(self, repo):
        """save_battle_state(None) 等同於 clear"""
        repo.create_player("user_001", "勇者")
        repo.save_battle_state("user_001", {"name": "哥布林", "current_hp": 5,
                                             "max_hp": 10, "current_mp": 0, "max_mp": 0,
                                             "attack": 3, "defense": 0})
        repo.save_battle_state("user_001", None)
        assert repo.load_battle_state("user_001") is None

    def test_upsert_battle_state(self, repo):
        """重複 save 同一 user_id 應覆蓋而非重複插入"""
        repo.create_player("user_001", "勇者")
        repo.save_battle_state("user_001", {"name": "史萊姆", "current_hp": 30,
                                             "max_hp": 30, "current_mp": 0, "max_mp": 0,
                                             "attack": 5, "defense": 0})
        repo.save_battle_state("user_001", {"name": "哥布林王", "current_hp": 50,
                                             "max_hp": 50, "current_mp": 10, "max_mp": 10,
                                             "attack": 12, "defense": 3})
        result = repo.load_battle_state("user_001")
        assert result["name"] == "哥布林王"
        assert result["current_hp"] == 50

# ─────────────────────────────────────────────────────────
# 排行榜查詢
# ─────────────────────────────────────────────────────────

class TestPlayerRanking:
    def test_get_top_players_by_level(self, repo):
        repo.create_player("user_1", "Player A")  # level 1, exp 0
        
        char2 = repo.create_player("user_2", "Player B")
        char2.level = 5
        char2.exp = 100
        repo.save_player("user_2", char2)
        
        char3 = repo.create_player("user_3", "Player C")
        char3.level = 5
        char3.exp = 200
        repo.save_player("user_3", char3)
        
        top = repo.get_top_players_by_level(limit=2)
        assert len(top) == 2
        assert top[0]["name"] == "Player C"
        assert top[0]["level"] == 5
        assert top[0]["exp"] == 200
        assert top[1]["name"] == "Player B"

    def test_get_top_players_by_coin(self, repo):
        repo.create_player("user_1", "Player A") # money 0
        
        char2 = repo.create_player("user_2", "Player B")
        char2.money = 500
        repo.save_player("user_2", char2)
        
        char3 = repo.create_player("user_3", "Player C")
        char3.money = 100
        repo.save_player("user_3", char3)
        
        top = repo.get_top_players_by_coin(limit=2)
        assert len(top) == 2
        assert top[0]["name"] == "Player B"
        assert top[0]["money"] == 500
        assert top[1]["name"] == "Player C"
        assert top[1]["money"] == 100

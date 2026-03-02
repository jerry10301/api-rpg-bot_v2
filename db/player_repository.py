"""
db/player_repository.py
Repository 模式：封裝所有玩家相關的 SQLite 讀寫邏輯
"""
import json
from typing import Optional
from core.character import Character
from db.database import get_connection, DB_PATH


class _NoCloseConn:
    """
    Proxy wrapper：讓 with/try-finally 中的 conn.close() 不關閉共用連線。
    僅供 in-memory SQLite 測試使用。
    """
    def __init__(self, conn):
        self._conn = conn

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def commit(self):
        self._conn.commit()

    def close(self):
        pass  # 不關閉，保留共用連線

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class PlayerRepository:
    def __init__(self, db_path: str = DB_PATH, shared_conn=None):
        self.db_path = db_path
        # shared_conn 供測試用（in-memory SQLite 需共用同一連線）
        self._shared_conn = shared_conn

    def _conn(self):
        if self._shared_conn is not None:
            return _NoCloseConn(self._shared_conn)
        return get_connection(self.db_path)

    # =========================================================
    # 玩家角色 CRUD
    # =========================================================

    def player_exists(self, user_id: str) -> bool:
        """檢查玩家是否已存在"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM players WHERE discord_user_id = ?", (user_id,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def create_player(self, user_id: str, name: str) -> Character:
        """建立新玩家，存入 DB 並回傳初始 Character 物件"""
        char = Character(name=name)
        char.learn_skill("Heal", 1)
        char.learn_skill("Fireball", 1)

        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO players
                    (discord_user_id, name, level, hp, max_hp, mp, max_mp,
                     money, exp, stats_json, skills_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, char.name, char.level,
                char.hp, char.max_hp, char.mp, char.max_mp,
                char.money, char.exp,
                json.dumps(char.stats),
                json.dumps(char.skills)
            ))
            conn.commit()
        finally:
            conn.close()
        return char

    def load_player(self, user_id: str) -> Optional[Character]:
        """從 DB 還原 Character 物件；若找不到回傳 None"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM players WHERE discord_user_id = ?", (user_id,)
            ).fetchone()
            if not row:
                return None

            char = Character(
                name=row["name"],
                level=row["level"],
                hp=row["hp"],
                max_hp=row["max_hp"],
                mp=row["mp"],
                max_mp=row["max_mp"],
                money=row["money"],
                exp=row["exp"],
                stats=json.loads(row["stats_json"]),
                skills=json.loads(row["skills_json"])
            )
            # Character.__post_init__ 會重算 max_hp/max_mp，需用 override 保持 DB 值
            char.max_hp = row["max_hp"]
            char.max_mp = row["max_mp"]
            return char
        finally:
            conn.close()

    def save_player(self, user_id: str, char: Character):
        """將 Character 物件序列化並更新至 DB"""
        conn = self._conn()
        try:
            conn.execute("""
                UPDATE players SET
                    name=?, level=?, hp=?, max_hp=?, mp=?, max_mp=?,
                    money=?, exp=?, stats_json=?, skills_json=?
                WHERE discord_user_id=?
            """, (
                char.name, char.level,
                char.hp, char.max_hp, char.mp, char.max_mp,
                char.money, char.exp,
                json.dumps(char.stats),
                json.dumps(char.skills),
                user_id
            ))
            conn.commit()
        finally:
            conn.close()

    # =========================================================
    # 任務進度
    # =========================================================

    def load_active_quests(self, user_id: str) -> dict:
        """從 DB 還原 active_quests dict（與 QuestManager.active_quests 格式相同）"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM active_quests WHERE discord_user_id = ?", (user_id,)
            ).fetchall()
            result = {}
            for row in rows:
                result[row["quest_id"]] = {
                    "name": row["name"],
                    "target_type": row["target_type"],
                    "target_amount": row["target_amount"],
                    "current_amount": row["current_amount"],
                    "completed": bool(row["completed"])
                }
            return result
        finally:
            conn.close()

    def save_active_quests(self, user_id: str, quests: dict):
        """將 active_quests dict 完整同步至 DB（先刪再插）"""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM active_quests WHERE discord_user_id = ?", (user_id,)
            )
            for quest_id, data in quests.items():
                conn.execute("""
                    INSERT INTO active_quests
                        (discord_user_id, quest_id, name, target_type,
                         target_amount, current_amount, completed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, quest_id, data["name"], data["target_type"],
                    data["target_amount"], data["current_amount"],
                    1 if data["completed"] else 0
                ))
            conn.commit()
        finally:
            conn.close()

    # =========================================================
    # 戰鬥狀態
    # =========================================================

    def load_battle_state(self, user_id: str) -> Optional[dict]:
        """從 DB 還原怪物快照；若無戰鬥狀態回傳 None"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT monster_json FROM battle_states WHERE discord_user_id = ?",
                (user_id,)
            ).fetchone()
            if not row or not row["monster_json"]:
                return None
            return json.loads(row["monster_json"])
        finally:
            conn.close()

    def save_battle_state(self, user_id: str, monster: Optional[dict]):
        """儲存怪物快照（UPSERT）；monster 為 None 時等同清除"""
        conn = self._conn()
        try:
            if monster is None:
                conn.execute(
                    "DELETE FROM battle_states WHERE discord_user_id = ?", (user_id,)
                )
            else:
                conn.execute("""
                    INSERT INTO battle_states (discord_user_id, monster_json)
                    VALUES (?, ?)
                    ON CONFLICT(discord_user_id) DO UPDATE SET monster_json=excluded.monster_json
                """, (user_id, json.dumps(monster)))
            conn.commit()
        finally:
            conn.close()

    def clear_battle_state(self, user_id: str):
        """戰鬥結束後清除怪物快照"""
        self.save_battle_state(user_id, None)

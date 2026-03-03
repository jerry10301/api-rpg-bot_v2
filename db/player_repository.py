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

    def executemany(self, *args, **kwargs):
        return self._conn.executemany(*args, **kwargs)

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
        # 初始物品
        char.add_item("MinorHealthPotion", 3)
        char.add_item("MinorManaPotion", 2)

        conn = self._conn()
        try:
            # 使用交易確保多表寫入原子性
            conn.execute("BEGIN TRANSACTION")
            
            # 1. 插入玩家基本資料與屬性
            conn.execute("""
                INSERT INTO players
                    (discord_user_id, name, level, hp, max_hp, mp, max_mp,
                     money, exp, stat_str, stat_dex, stat_con, stat_int, stat_wis, stat_luk)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, char.name, char.level,
                char.hp, char.max_hp, char.mp, char.max_mp,
                char.money, char.exp,
                char.stats["STR"], char.stats["DEX"], char.stats["CON"],
                char.stats["INT"], char.stats["WIS"], char.stats["LUK"]
            ))

            # 2. 插入初始技能
            skill_data = [(user_id, s, d["level"], d["exp"]) for s, d in char.skills.items()]
            conn.executemany(
                "INSERT INTO player_skills (discord_user_id, skill_id, level, exp) VALUES (?, ?, ?, ?)",
                skill_data
            )

            # 3. 插入初始物品
            inv_data = [(user_id, i, a) for i, a in char.inventory.items()]
            conn.executemany(
                "INSERT INTO player_inventory (discord_user_id, item_id, amount) VALUES (?, ?, ?)",
                inv_data
            )

            conn.commit()
        except Exception as e:
            conn.execute("ROLLBACK")
            raise e
        finally:
            conn.close()
        return char

    def load_player(self, user_id: str) -> Optional[Character]:
        """從 DB 還原 Character 物件；若找不到回傳 None"""
        conn = self._conn()
        try:
            # 1. 讀取玩家核心資料
            row = conn.execute(
                "SELECT * FROM players WHERE discord_user_id = ?", (user_id,)
            ).fetchone()
            if not row:
                return None

            # 2. 讀取技能
            skill_rows = conn.execute(
                "SELECT skill_id, level, exp FROM player_skills WHERE discord_user_id = ?", (user_id,)
            ).fetchall()
            skills = {r["skill_id"]: {"level": r["level"], "exp": r["exp"]} for r in skill_rows}

            # 3. 讀取物品
            inv_rows = conn.execute(
                "SELECT item_id, amount FROM player_inventory WHERE discord_user_id = ?", (user_id,)
            ).fetchall()
            inventory = {r["item_id"]: r["amount"] for r in inv_rows}

            stats = {
                "STR": row["stat_str"],
                "DEX": row["stat_dex"],
                "CON": row["stat_con"],
                "INT": row["stat_int"],
                "WIS": row["stat_wis"],
                "LUK": row["stat_luk"]
            }

            char = Character(
                name=row["name"],
                level=row["level"],
                hp=row["hp"],
                max_hp=row["max_hp"],
                mp=row["mp"],
                max_mp=row["max_mp"],
                money=row["money"],
                exp=row["exp"],
                stats=stats,
                skills=skills,
                inventory=inventory
            )
            # 保持 DB 的上限值 (避免 Character.__post_init__ 重新根據等級計算後產生誤差)
            char.max_hp = row["max_hp"]
            char.max_mp = row["max_mp"]
            return char
        finally:
            conn.close()

    def save_player(self, user_id: str, char: Character):
        """將 Character 物件更新至 DB（包含屬性、技能、物品）"""
        conn = self._conn()
        try:
            conn.execute("BEGIN TRANSACTION")

            # 1. 更新基本資料與屬性
            conn.execute("""
                UPDATE players SET
                    name=?, level=?, hp=?, max_hp=?, mp=?, max_mp=?,
                    money=?, exp=?, 
                    stat_str=?, stat_dex=?, stat_con=?, stat_int=?, stat_wis=?, stat_luk=?
                WHERE discord_user_id=?
            """, (
                char.name, char.level,
                char.hp, char.max_hp, char.mp, char.max_mp,
                char.money, char.exp,
                char.stats["STR"], char.stats["DEX"], char.stats["CON"],
                char.stats["INT"], char.stats["WIS"], char.stats["LUK"],
                user_id
            ))

            # 2. 同步技能 (刪除後重新插入最保險且簡單)
            conn.execute("DELETE FROM player_skills WHERE discord_user_id = ?", (user_id,))
            skill_data = [(user_id, s, d["level"], d["exp"]) for s, d in char.skills.items()]
            conn.executemany(
                "INSERT INTO player_skills (discord_user_id, skill_id, level, exp) VALUES (?, ?, ?, ?)",
                skill_data
            )

            # 3. 同步物品
            conn.execute("DELETE FROM player_inventory WHERE discord_user_id = ?", (user_id,))
            inv_data = [(user_id, i, a) for i, a in char.inventory.items()]
            conn.executemany(
                "INSERT INTO player_inventory (discord_user_id, item_id, amount) VALUES (?, ?, ?)",
                inv_data
            )

            conn.commit()
        except Exception as e:
            conn.execute("ROLLBACK")
            raise e
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
    # 排行榜查詢
    # =========================================================

    def get_top_players_by_level(self, limit: int = 10) -> list[dict]:
        """取得等級排行榜（依據 level descending, exp descending 排序）"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT name, level, exp FROM players ORDER BY level DESC, exp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [{"name": r["name"], "level": r["level"], "exp": r["exp"]} for r in rows]
        finally:
            conn.close()

    def get_top_players_by_coin(self, limit: int = 10) -> list[dict]:
        """取得財富排行榜（依據 money descending 排序）"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT name, money FROM players ORDER BY money DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [{"name": r["name"], "money": r["money"]} for r in rows]
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

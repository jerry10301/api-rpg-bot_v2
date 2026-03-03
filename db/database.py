"""
db/database.py
SQLite 連線管理與資料庫初始化
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game_data.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """取得 SQLite 連線（row_factory 設為 dict-like）"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH):
    """初始化所有資料表（高度正規化版本）"""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        
        # 檢查是否存在舊架構 (例如: 存在 players 但沒 stat_str)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(players)")
            columns = [info[1] for info in cursor.fetchall()]
            if "stats_json" in columns or "stat_str" not in columns:
                print("*(系統)* 檢測到舊版資料架構，正在進行全面優化重設...")
                cursor.execute("DROP TABLE IF EXISTS players")
                cursor.execute("DROP TABLE IF EXISTS player_inventory")
                cursor.execute("DROP TABLE IF EXISTS player_skills")
                cursor.execute("DROP TABLE IF EXISTS active_quests")
                cursor.execute("DROP TABLE IF EXISTS battle_states")
        
        # 1. 玩家角色表 (屬性拆解為獨立欄位)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                discord_user_id TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                level           INTEGER DEFAULT 1,
                hp              INTEGER DEFAULT 0,
                max_hp          INTEGER DEFAULT 0,
                mp              INTEGER DEFAULT 0,
                max_mp          INTEGER DEFAULT 0,
                money           INTEGER DEFAULT 0,
                exp             INTEGER DEFAULT 0,
                -- 核心屬性 (1-100)
                stat_str        INTEGER DEFAULT 10,
                stat_dex        INTEGER DEFAULT 10,
                stat_con        INTEGER DEFAULT 10,
                stat_int        INTEGER DEFAULT 10,
                stat_wis        INTEGER DEFAULT 10,
                stat_luk        INTEGER DEFAULT 10
            )
        """)

        # 2. 玩家物品表 (多對多關聯)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_inventory (
                discord_user_id TEXT NOT NULL,
                item_id         TEXT NOT NULL,
                amount          INTEGER DEFAULT 1,
                PRIMARY KEY (discord_user_id, item_id),
                FOREIGN KEY (discord_user_id) REFERENCES players(discord_user_id) ON DELETE CASCADE
            )
        """)

        # 3. 玩家技能表 (多對多關聯)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_skills (
                discord_user_id TEXT NOT NULL,
                skill_id        TEXT NOT NULL,
                level           INTEGER DEFAULT 1,
                PRIMARY KEY (discord_user_id, skill_id),
                FOREIGN KEY (discord_user_id) REFERENCES players(discord_user_id) ON DELETE CASCADE
            )
        """)

        # 4. 進行中任務表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_quests (
                discord_user_id TEXT NOT NULL,
                quest_id        TEXT NOT NULL,
                name            TEXT,
                target_type     TEXT,
                target_amount   INTEGER DEFAULT 1,
                current_amount  INTEGER DEFAULT 0,
                completed       INTEGER DEFAULT 0,
                PRIMARY KEY (discord_user_id, quest_id),
                FOREIGN KEY (discord_user_id) REFERENCES players(discord_user_id) ON DELETE CASCADE
            )
        """)

        # 5. 戰鬥狀態表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battle_states (
                discord_user_id TEXT PRIMARY KEY,
                monster_json    TEXT,
                FOREIGN KEY (discord_user_id) REFERENCES players(discord_user_id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    finally:
        conn.close()

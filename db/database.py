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
    """初始化所有資料表（若不存在則建立）"""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        # 玩家角色表
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
                stats_json      TEXT DEFAULT '{}',
                skills_json     TEXT DEFAULT '{}'
            )
        """)
        # 進行中任務表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_quests (
                discord_user_id TEXT NOT NULL,
                quest_id        TEXT NOT NULL,
                name            TEXT,
                target_type     TEXT,
                target_amount   INTEGER DEFAULT 1,
                current_amount  INTEGER DEFAULT 0,
                completed       INTEGER DEFAULT 0,
                PRIMARY KEY (discord_user_id, quest_id)
            )
        """)
        # 戰鬥狀態表（怪物快照）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battle_states (
                discord_user_id TEXT PRIMARY KEY,
                monster_json    TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

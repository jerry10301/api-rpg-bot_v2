"""
services/session_manager.py
以 Discord user_id 為 key，管理每位玩家的 GameEngine 實例。
提供 get_or_create_session 與 flush_session 功能。
"""
from typing import Dict
from db.database import init_db
from db.player_repository import PlayerRepository


class SessionManager:
    """
    全域 Session 快取，確保同一用戶同一時間只有一個 GameEngine 實例。
    GameEngine 的 import 延後到方法內部，避免循環 import。
    """
    def __init__(self):
        init_db()  # 確保啟動時資料表已建立
        self._sessions: Dict[str, "GameEngine"] = {}  # type: ignore
        self._repo = PlayerRepository()

    def get_or_create_session(self, user_id: str) -> "GameEngine":  # type: ignore
        """
        取得或建立玩家的 GameEngine session。
        - 若 cache 已有 → 直接回傳（不讀 DB）
        - 若無 → 從 DB 載入狀態並建立 GameEngine
        """
        from services.engine import GameEngine  # 延後 import 避免循環
        if user_id not in self._sessions:
            engine = GameEngine(discord_user_id=user_id)
            self._sessions[user_id] = engine
        return self._sessions[user_id]

    def flush_session(self, user_id: str):
        """
        將指定用戶的 GameEngine 狀態同步至 DB。
        每次指令執行完畢後應呼叫此方法。
        """
        if user_id in self._sessions:
            self._sessions[user_id].save_state()

    def remove_session(self, user_id: str):
        """從快取中移除 session（登出/清理時使用）"""
        self._sessions.pop(user_id, None)

    def player_exists(self, user_id: str) -> bool:
        """檢查玩家是否已在 DB 中建立過角色"""
        return self._repo.player_exists(user_id)


# 全域單例，供 bot/commands.py 使用
session_manager = SessionManager()

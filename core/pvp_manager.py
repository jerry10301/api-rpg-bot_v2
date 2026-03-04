"""
core/pvp_manager.py
管理玩家 PvP 決鬥邀請的全域狀態。
"""
from typing import Optional


class PvPManager:
    """
    儲存待確認的 PvP 邀請。
    結構：_invites[target_user_id] = inviter_user_id
    一個玩家同時只能收到一個挑戰邀請（後來的會覆蓋舊的）。
    """

    def __init__(self):
        # key: target_id, value: inviter_id
        self._invites: dict[str, str] = {}

    def send_invite(self, inviter_id: str, target_id: str) -> bool:
        """
        發送決鬥邀請。
        若挑戰者嘗試挑戰自己，或已有相同邀請，回傳 False。
        """
        if inviter_id == target_id:
            return False
        self._invites[target_id] = inviter_id
        return True

    def get_invite(self, target_id: str) -> Optional[str]:
        """
        取得針對 target_id 的邀請者 ID，若無則回傳 None。
        """
        return self._invites.get(target_id)

    def remove_invite(self, target_id: str):
        """移除邀請（接受或拒絕後呼叫）"""
        self._invites.pop(target_id, None)

    def has_pending_invite(self, target_id: str) -> bool:
        """確認 target_id 是否有待接受的邀請"""
        return target_id in self._invites

    def get_all_invites(self) -> dict[str, str]:
        """回傳所有待確認邀請（僅供測試使用）"""
        return dict(self._invites)

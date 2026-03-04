"""
tests/test_quest_validation.py
確保討伐任務只有擊殺正確怪物才能推進進度。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.quest_manager import QuestManager
from core.character import Character


@pytest.fixture
def qm():
    """每個測試建立全新的 QuestManager"""
    return QuestManager()


@pytest.fixture
def player():
    return Character(name="測試學徒")


# ─────────────────────────────────────────────────────────────
# 測試 accept_quest 是否正確記錄 target_monsters
# ─────────────────────────────────────────────────────────────

class TestAcceptQuest:
    def test_mountain_quest_records_target_monsters(self, qm):
        """接取後山討伐任務後，應記錄 target_monsters=['slime', 'goblin'] 且目標數量為 3"""
        qm.accept_quest("quest_hunt_mountain_monster")
        assert "quest_hunt_mountain_monster" in qm.active_quests
        data = qm.active_quests["quest_hunt_mountain_monster"]
        assert "slime" in data["target_monsters"]
        assert "goblin" in data["target_monsters"]
        assert data["target_amount"] == 3

    def test_work_quest_has_no_target_monsters(self, qm):
        """工作任務不應有 target_monsters（或為 None）"""
        qm.accept_quest("quest_mopping")
        data = qm.active_quests.get("quest_mopping", {})
        assert data.get("target_monsters") is None


# ─────────────────────────────────────────────────────────────
# 測試 update_quest_progress：正確怪物才能推進任務
# ─────────────────────────────────────────────────────────────

class TestUpdateQuestProgress:
    def test_slime_advances_mountain_quest(self, qm):
        """打死史萊姆，後山討伐任務應推進進度"""
        qm.accept_quest("quest_hunt_mountain_monster")
        qm.update_quest_progress("combat", 1, monster_id="slime")
        data = qm.active_quests["quest_hunt_mountain_monster"]
        assert data["current_amount"] == 1
        assert data["completed"] is False  # 需要擊殺 3 隻

    def test_goblin_advances_mountain_quest(self, qm):
        """打死哥布林，後山討伐任務也應推進進度"""
        qm.accept_quest("quest_hunt_mountain_monster")
        qm.update_quest_progress("combat", 1, monster_id="goblin")
        data = qm.active_quests["quest_hunt_mountain_monster"]
        assert data["current_amount"] == 1

    def test_three_kills_completes_mountain_quest(self, qm):
        """擊殺 3 隻（混合史萊姆與哥布林）應完成任務"""
        qm.accept_quest("quest_hunt_mountain_monster")
        qm.update_quest_progress("combat", 1, monster_id="slime")
        qm.update_quest_progress("combat", 1, monster_id="goblin")
        qm.update_quest_progress("combat", 1, monster_id="slime")
        data = qm.active_quests["quest_hunt_mountain_monster"]
        assert data["current_amount"] == 3
        assert data["completed"] is True

    def test_wrong_monster_does_not_advance_mountain_quest(self, qm):
        """打死不在清單的怪物（如 forest_witch），後山討伐任務不應推進"""
        qm.accept_quest("quest_hunt_mountain_monster")
        qm.update_quest_progress("combat", 1, monster_id="forest_witch")
        data = qm.active_quests["quest_hunt_mountain_monster"]
        assert data["current_amount"] == 0

    def test_unknown_monster_does_not_advance_quest(self, qm):
        """傳入未知怪物 ID，任務不推進"""
        qm.accept_quest("quest_hunt_mountain_monster")
        qm.update_quest_progress("combat", 1, monster_id="ancient_dragon")
        data = qm.active_quests["quest_hunt_mountain_monster"]
        assert data["current_amount"] == 0

    def test_no_monster_id_does_not_advance_specific_quests(self, qm):
        """不傳入 monster_id（或傳 None）時，有怪物限制的任務不應推進"""
        qm.accept_quest("quest_hunt_mountain_monster")
        qm.update_quest_progress("combat", 1, monster_id=None)
        data = qm.active_quests["quest_hunt_mountain_monster"]
        assert data["current_amount"] == 0, "不傳怪物 ID 時，有目標限制的任務不應推進"


# ─────────────────────────────────────────────────────────────
# 測試 resolve_quest：未完成時不得提交
# ─────────────────────────────────────────────────────────────

class TestResolveQuest:
    def test_cannot_submit_incomplete_quest(self, qm, player):
        """任務進度未完成時，提交應失敗"""
        qm.accept_quest("quest_hunt_mountain_monster")
        result = qm.resolve_quest(player, "quest_hunt_mountain_monster")
        assert result["success"] is False
        assert "尚未完成" in result.get("error", "")

    def test_can_submit_completed_quest(self, qm, player):
        """任務完成後，提交應成功並發放獎勵"""
        qm.accept_quest("quest_hunt_mountain_monster")
        qm.update_quest_progress("combat", 1, monster_id="slime")
        qm.update_quest_progress("combat", 1, monster_id="goblin")
        qm.update_quest_progress("combat", 1, monster_id="slime")
        result = qm.resolve_quest(player, "quest_hunt_mountain_monster")
        assert result["success"] is True
        assert result["rewards"].get("money") == 160
        assert result["rewards"].get("exp") == 180
        # 任務應從活躍清單移除
        assert "quest_hunt_mountain_monster" not in qm.active_quests

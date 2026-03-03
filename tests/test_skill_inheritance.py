import pytest
import os
from unittest.mock import patch
from services.engine import GameEngine
from db.database import init_db

@pytest.fixture
def temp_db():
    db_path = "test_inheritance.db"
    if os.path.exists(db_path):
        try: os.remove(db_path)
        except: pass
    init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        try: os.remove(db_path)
        except: pass

@pytest.fixture
def engine(temp_db):
    with patch('services.engine.DB_PATH', "test_inheritance.db"):
        eng = GameEngine("test_user_inheritance")
        # 直接寫入測試資料
        eng.items_db = {
            "SkillNotebook": {
                "name": "技能筆記本",
                "description": "可以將一個指定技能寫入其中。寫入後會變成心得筆記。",
                "price": 500
            }
        }
        eng.skills_db = {
            "Fireball": {
                "name": "火球術",
                "description": "發射一枚火球攻擊敵人。"
            },
            "Heal": {
                "name": "治癒術",
                "description": "恢復少量生命值。"
            }
        }
        eng.player.inventory = {}
        eng.player.skills = {}
        yield eng

def test_use_skill_notebook_without_arg(engine):
    engine.player.add_item("SkillNotebook", 1)
    result = engine.handle_use_item("SkillNotebook")
    assert "請指定要寫入的技能" in result
    assert "SkillNotebook" in engine.player.inventory

def test_use_skill_notebook_unlearned_skill(engine):
    engine.player.add_item("SkillNotebook", 1)
    result = engine.handle_use_item("SkillNotebook", "Fireball")
    assert "你沒有學會技能" in result
    assert "SkillNotebook" in engine.player.inventory

def test_use_skill_notebook_success(engine):
    engine.player.add_item("SkillNotebook", 1)
    engine.player.learn_skill("Fireball", 1)
    
    # 用 ID 寫入
    result = engine.handle_use_item("SkillNotebook", "Fireball")
    assert "獲得了一本「心得筆記」" in result
    assert "SkillNotebook" not in engine.player.inventory
    assert "Note:Fireball" in engine.player.inventory
    
    # 檢查顯示名稱
    items_display = engine.handle_items()
    assert "心得筆記" in items_display
    assert "記載著【火球術】的學習心得" in items_display

def test_use_note_already_learned(engine):
    engine.player.add_item("Note:Fireball", 1)
    engine.player.learn_skill("Fireball", 1)
    
    result = engine.handle_use_item("Note:Fireball")
    assert "你已經學會" in result
    assert "Note:Fireball" in engine.player.inventory

def test_use_note_success(engine):
    engine.player.add_item("Note:Heal", 1)
    
    result = engine.handle_use_item("Note:Heal")
    assert "恭喜！你學會了新技能" in result
    assert "Note:Heal" not in engine.player.inventory
    assert "Heal" in engine.player.skills
    assert engine.player.skills["Heal"]["level"] == 1

def test_use_note_by_name(engine):
    engine.player.add_item("Note:Heal", 1)
    
    # 使用模糊名稱比對
    result = engine.handle_use_item("心得筆記")
    assert "恭喜！你學會了新技能：**【治癒術】**" in result
    assert "Note:Heal" not in engine.player.inventory
    assert "Heal" in engine.player.skills

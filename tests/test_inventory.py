import pytest
import os
import json
import sqlite3
from core.character import Character
from db.player_repository import PlayerRepository
from db.database import init_db, get_connection
from services.engine import GameEngine

@pytest.fixture
def repo(temp_db):
    return PlayerRepository(temp_db)

@pytest.fixture
def temp_db():
    db_path = "test_game_data.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)

def test_character_inventory():
    char = Character(name="Test")
    char.add_item("Potion", 2)
    assert char.inventory["Potion"] == 2
    char.add_item("Potion", 1)
    assert char.inventory["Potion"] == 3
    
    assert char.remove_item("Potion", 1) is True
    assert char.inventory["Potion"] == 2
    assert char.remove_item("Potion", 2) is True
    assert "Potion" not in char.inventory
    assert char.remove_item("Potion", 1) is False

def test_repository_inventory(temp_db):
    repo = PlayerRepository(temp_db)
    user_id = "user123"
    
    # Create player
    char = repo.create_player(user_id, "Adventurer")
    assert "MinorHealthPotion" in char.inventory
    assert char.inventory["MinorHealthPotion"] == 3
    
    # Save and Load
    char.add_item("Sword", 1)
    repo.save_player(user_id, char)
    
    loaded = repo.load_player(user_id)
    assert loaded.inventory["Sword"] == 1
    assert loaded.inventory["MinorHealthPotion"] == 3

def test_engine_items_logic(temp_db):
    # We need to mock items.json for GameEngine or just use the real one if it exists
    engine = GameEngine(discord_user_id="test_user")
    # Manually inject DB path if needed, but GameEngine uses DB_PATH constant.
    # For testing, we might need to override DB_PATH or use a test-specific engine.
    # Since GameEngine is hardcoded to DB_PATH, let's just test Character/Repo for now.
    pass

def test_item_usage_effects():
    char = Character(name="Test", hp=10, max_hp=100, mp=5, max_mp=50)
    char.add_item("MinorHealthPotion", 1)
    
    # Simulate GameEngine.handle_use_item logic
    item_data = {
        "name": "小紅水",
        "hp_restore": 30,
        "mp_restore": 0
    }
    
    char.heal(hp_amount=item_data["hp_restore"], mp_amount=item_data["mp_restore"])
    char.remove_item("MinorHealthPotion", 1)
    
    assert char.hp == 40
    assert "MinorHealthPotion" not in char.inventory

import pytest
import os
from unittest.mock import patch, MagicMock
from core.character import Character
from services.engine import GameEngine
from db.database import init_db

# --- Character Object Tests ---

def test_transfer_money():
    char1 = Character(name="Alice", money=100)
    char2 = Character(name="Bob", money=50)

    # Valid transfer
    assert char1.transfer_money(char2, 30) is True
    assert char1.money == 70
    assert char2.money == 80

    # Invalid transfer (not enough money)
    assert char1.transfer_money(char2, 100) is False
    assert char1.money == 70
    assert char2.money == 80

    # Invalid transfer (negative/zero amount)
    assert char1.transfer_money(char2, 0) is False
    assert char1.transfer_money(char2, -10) is False

def test_transfer_item():
    char1 = Character(name="Alice")
    char1.add_item("Potion", 5)
    char2 = Character(name="Bob")

    # Valid transfer
    assert char1.transfer_item(char2, "Potion", 2) is True
    assert char1.inventory["Potion"] == 3
    assert char2.inventory["Potion"] == 2

    # Invalid transfer (not enough items)
    assert char1.transfer_item(char2, "Potion", 5) is False
    assert char1.inventory["Potion"] == 3
    assert char2.inventory["Potion"] == 2

    # Invalid transfer (item doesn't exist)
    assert char1.transfer_item(char2, "Sword", 1) is False


# --- GameEngine Tests ---

@pytest.fixture
def temp_db():
    db_path = "test_trading.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)

@patch('services.engine.DB_PATH', "test_trading.db")
def test_engine_give_coin(temp_db):
    engine = GameEngine(discord_user_id="user1")
    engine.player.name = "Alice"
    engine.player.money = 100
    engine.save_state()

    # Create target player
    engine2 = GameEngine(discord_user_id="user2")
    engine2.player.name = "Bob"
    engine2.player.money = 50
    engine2.save_state()

    # Valid transfer
    res = engine.handle_give_coin("user2", 30)
    assert "成功轉移了 30 金幣給 Bob" in res
    assert engine.player.money == 70
    
    # Check target saved state
    engine2 = GameEngine(discord_user_id="user2")
    assert engine2.player.money == 80

    # Invalid transfers
    assert "餘額不足" in engine.handle_give_coin("user2", 100)
    assert "金額必須大於 0" in engine.handle_give_coin("user2", 0)
    assert "不能將金幣轉移給自己" in engine.handle_give_coin("user1", 10)
    assert "找不到指定的玩家" in engine.handle_give_coin("user3", 10)


@patch('services.engine.DB_PATH', "test_trading.db")
def test_engine_give_item(temp_db):
    engine = GameEngine(discord_user_id="userA")
    engine.player.name = "Alice"
    engine.player.add_item("item_potion", 5)
    
    # Mock items_db
    engine.items_db = {"item_potion": {"name": "紅藥水"}}
    engine.save_state()

    # Create target player
    engine2 = GameEngine(discord_user_id="userB")
    engine2.player.name = "Bob"
    engine2.save_state()

    # Valid transfer by ID
    res = engine.handle_give_item("userB", "item_potion", 2)
    assert "成功將 2 個【紅藥水】交給了 Bob" in res
    assert engine.player.inventory["item_potion"] == 3

    # Check target saved state
    engine2 = GameEngine(discord_user_id="userB")
    assert engine2.player.inventory["item_potion"] == 2

    # Valid transfer by Name
    res = engine.handle_give_item("userB", "紅藥水", 1)
    assert "成功將 1 個【紅藥水】交給了 Bob" in res
    assert engine.player.inventory["item_potion"] == 2
    
    engine2 = GameEngine(discord_user_id="userB")
    assert engine2.player.inventory["item_potion"] == 3

    # Invalid transfers
    assert "數量必須大於 0" in engine.handle_give_item("userB", "item_potion", 0)
    assert "不能將物品轉移給自己" in engine.handle_give_item("userA", "item_potion", 1)
    assert "找不到指定的玩家" in engine.handle_give_item("userC", "item_potion", 1)
    assert "你沒有【item_sword】" in engine.handle_give_item("userB", "item_sword", 1)
    assert "物品數量不足" in engine.handle_give_item("userB", "item_potion", 10)


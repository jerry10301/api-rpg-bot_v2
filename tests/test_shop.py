import pytest
import os
from unittest.mock import patch
from services.engine import GameEngine
from db.database import init_db

@pytest.fixture
def temp_db():
    db_path = "test_shop.db"
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
    with patch('services.engine.DB_PATH', "test_shop.db"):
        eng = GameEngine("test_shop_user_999")
        eng.player.money = 100
        eng.player.inventory = {}
        
        # 確保有測試用物品在 items_db 中
        eng.items_db = {
            "TestPotion": {
                "name": "測試藥水",
                "price": 50,
                "description": "測試用"
            },
            "TestSword": {
                "name": "測試劍",
                "price": 200,
                "description": "測試用"
            },
            "NoPriceItem": {
                "name": "無價之寶",
                "description": "測試用"
            }
        }
        yield eng

def test_shop_list(engine):
    output = engine.handle_shop_list()
    assert "商店商品清單" in output
    assert "測試藥水" in output
    assert "測試劍" in output
    assert "無價之寶" not in output # 沒有 price 就不該出現在商店

def test_shop_buy_success(engine):
    output = engine.handle_shop_buy("TestPotion", 1)
    assert "交易成功" in output
    assert engine.player.money == 50
    assert engine.player.inventory.get("TestPotion", 0) == 1

def test_shop_buy_insufficient_funds(engine):
    output = engine.handle_shop_buy("TestSword", 1)
    assert "金幣不足" in output
    assert engine.player.money == 100
    assert engine.player.inventory.get("TestSword", 0) == 0

def test_shop_buy_not_found(engine):
    output = engine.handle_shop_buy("UnknownItem", 1)
    assert "沒有販售" in output
    assert engine.player.money == 100

def test_shop_sell_success(engine):
    engine.player.add_item("TestPotion", 2)
    output = engine.handle_shop_sell("TestPotion", 1)
    assert "收購成功" in output
    # 原價 50, 賣價 1 / 10 = 5
    assert engine.player.money == 105
    assert engine.player.inventory.get("TestPotion", 0) == 1

def test_shop_sell_insufficient_item(engine):
    engine.player.add_item("TestPotion", 1)
    output = engine.handle_shop_sell("TestPotion", 2)
    assert "數量不足" in output
    assert engine.player.money == 100
    assert engine.player.inventory.get("TestPotion", 0) == 1

def test_shop_sell_no_price(engine):
    engine.player.add_item("NoPriceItem", 1)
    output = engine.handle_shop_sell("NoPriceItem", 1)
    assert "無法販售" in output
    assert engine.player.money == 100
    assert engine.player.inventory.get("NoPriceItem", 0) == 1

import sys
import os
import pytest

# 將專案根目錄加入路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.character import Character

def test_growth_stats():
    """測試屬性成長是否符合預期"""
    char = Character(name="TestHero")
    initial_stats = char.stats.copy()
    
    # 獲取足夠升級的經驗值 (Lv 1 -> 2 需要 100 * 1^1.5 = 100)
    char.gain_exp(100)
    
    assert char.level == 2
    # 檢查所有屬性是否至少 +1
    for stat, val in char.stats.items():
        assert val >= initial_stats[stat] + 1
    
    # 檢查總成長點數是否為 6 (全屬性+1) + 2 (隨機額外) = 8
    total_increase = sum(char.stats.values()) - sum(initial_stats.values())
    assert total_increase == 8

def test_hp_mp_growth():
    """測試 HP/MP 上限是否正確隨等級與屬性成長"""
    char = Character(name="TestHero")
    char.stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "LUK": 10}
    char.level = 1
    char.recalculate_max_stats()
    
    # Lv 1, CON=10, STR=10: 100 + (1*20) + (10*15) + (10*5) = 100 + 20 + 150 + 50 = 320
    assert char.max_hp == 320
    # Lv 1, WIS=10, INT=10: 50 + (1*15) + (10*12) + (10*8) = 50 + 15 + 120 + 80 = 265
    assert char.max_mp == 265
    
    # 升到 2 級
    char.gain_exp(100)
    # 等級變為 2, CON/STR/WIS/INT 至少各 +1
    # 假設這四項成長正好是 +1 (不考慮隨機額外), 則:
    # HP: 100 + (2*20) + (11*15) + (11*5) = 100 + 40 + 165 + 55 = 360
    # 隨機額外可能會讓這數值更高，所以檢查最小值
    assert char.max_hp >= 360
    assert char.max_mp >= 300 # 50 + (2*15) + (11*12) + (11*8) = 50 + 30 + 132 + 88 = 300

def test_exp_curve():
    """測試經驗值需求曲線"""
    char = Character(name="TestHero")
    # Lv 1 -> 2: 100 * 1^1.5 = 100
    assert char._get_exp_required(1) == 100
    # Lv 2 -> 3: 100 * 2^1.5 = 100 * 2.828... = 282
    assert char._get_exp_required(2) == 282
    # Lv 10 -> 11: 100 * 10^1.5 = 100 * 31.62... = 3162
    assert char._get_exp_required(10) == 3162

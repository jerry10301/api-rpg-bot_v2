import unittest
from core.character import Character

class TestCharacter(unittest.TestCase):
    def setUp(self):
        self.char = Character(name="TestHero")

    def test_initial_stats(self):
        self.assertEqual(self.char.name, "TestHero")
        self.assertEqual(self.char.level, 1)
        self.assertEqual(self.char.hp, 78)
    
    def test_gain_exp_level_up(self):
        self.char.gain_exp(100)
        self.assertEqual(self.char.level, 2)
        # Level 2 HP: 20 + (2*8) + (CON*4) + (STR*1)
        # Stats +1 (CON=11, STR=11) -> 20 + 16 + 44 + 11 = 91
        # Plus 2 random attributes +1. If CON or STR are selected, it will be higher.
        # So it should be at least 91.
        self.assertGreaterEqual(self.char.max_hp, 91)
        self.assertEqual(self.char.exp, 0)

    def test_max_level_cap(self):
        self.char.level = Character.MAX_LEVEL - 1
        self.char.exp = 0
        req_exp = self.char._get_exp_required(self.char.level)
        
        # 獲得足以升多級的超額經驗值
        self.char.gain_exp(req_exp + 50000)
        
        # 等級應該卡在上限
        self.assertEqual(self.char.level, Character.MAX_LEVEL)
        # 多的經驗值應該保留
        self.assertEqual(self.char.exp, 50000)

    def test_update_stat(self):
        self.assertTrue(self.char.update_stat("STR", 5))
        self.assertEqual(self.char.stats["STR"], 15)
        
        # 測試上限確保不超過 100
        self.char.update_stat("STR", 100)
        self.assertEqual(self.char.stats["STR"], 100)
        
        # 測試下限確保不低於 1
        self.char.update_stat("STR", -200)
        self.assertEqual(self.char.stats["STR"], 1)

    def test_learn_skill(self):
        self.char.learn_skill("Fireball")
        self.assertEqual(self.char.skills["Fireball"]["level"], 1)
        self.assertEqual(self.char.skills["Fireball"]["exp"], 0)
        self.char.learn_skill("Fireball")
        self.assertEqual(self.char.skills["Fireball"]["level"], 2)

    def test_get_status_report(self):
        report = self.char.get_status_report()
        self.assertIn("STR (力量): 10", report)
        self.assertIn("DEX (敏捷): 10", report)
        self.assertIn("CON (體質): 10", report)
        self.assertIn("INT (智力): 10", report)
        self.assertIn("WIS (精神): 10", report)
        self.assertIn("LUK (幸運): 10", report)

if __name__ == '__main__':
    unittest.main()

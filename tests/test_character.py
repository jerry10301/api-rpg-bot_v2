import unittest
from core.character import Character

class TestCharacter(unittest.TestCase):
    def setUp(self):
        self.char = Character(name="TestHero")

    def test_initial_stats(self):
        self.assertEqual(self.char.name, "TestHero")
        self.assertEqual(self.char.level, 1)
        self.assertEqual(self.char.hp, 320)
    
    def test_gain_exp_level_up(self):
        self.char.gain_exp(100)
        self.assertEqual(self.char.level, 2)
        # Level 2 HP: 100 + (2*20) + (CON*15) + (STR*5)
        # Stats +1 (CON=11, STR=11) -> 100 + 40 + 165 + 55 = 360
        # Plus 2 random attributes +1. If CON or STR are selected, it will be higher.
        # So it should be at least 360.
        self.assertGreaterEqual(self.char.max_hp, 360)
        self.assertEqual(self.char.exp, 0)

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
        self.assertEqual(self.char.skills["Fireball"], 1)
        self.char.learn_skill("Fireball")
        self.assertEqual(self.char.skills["Fireball"], 2)

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

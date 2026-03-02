import unittest
from core.character import Character

class TestCharacter(unittest.TestCase):
    def setUp(self):
        self.char = Character(name="TestHero")

    def test_initial_stats(self):
        self.assertEqual(self.char.name, "TestHero")
        self.assertEqual(self.char.level, 1)
        self.assertEqual(self.char.hp, 260)
    
    def test_gain_exp_level_up(self):
        self.char.gain_exp(100)
        self.assertEqual(self.char.level, 2)
        self.assertEqual(self.char.max_hp, 270)
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

if __name__ == '__main__':
    unittest.main()

import unittest
from core.dice import Dice

class TestDice(unittest.TestCase):
    def test_roll_d100(self):
        result = Dice.roll_d100()
        self.assertTrue(1 <= result <= 100)

    def test_roll_d20(self):
        result = Dice.roll_d20()
        self.assertTrue(1 <= result <= 20)

    def test_roll_expr(self):
        result1 = Dice.roll("1d20+5")
        self.assertTrue(6 <= result1 <= 25)
        
        result2 = Dice.roll("2d6")
        self.assertTrue(2 <= result2 <= 12)
        
        result3 = Dice.roll("1d100-10")
        self.assertTrue(-9 <= result3 <= 90)

    def test_check_d100(self):
        self.assertTrue(Dice.check_d100(100, roll_value=50))
        self.assertFalse(Dice.check_d100(10, roll_value=50))
        self.assertTrue(Dice.check_d100(40, roll_value=40)) # 邊界: 小於等於算成功

    def test_check_d20(self):
        self.assertTrue(Dice.check_d20(dc=15, roll_value=12, modifier=5)) # 12+5=17 >= 15
        self.assertFalse(Dice.check_d20(dc=15, roll_value=5, modifier=5)) # 5+5=10 < 15

if __name__ == '__main__':
    unittest.main()

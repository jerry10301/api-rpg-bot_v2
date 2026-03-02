import random
import re

class Dice:
    @staticmethod
    def roll_d100() -> int:
        """擲 d100 骰子 (回傳 1-100)"""
        return random.randint(1, 100)
    
    @staticmethod
    def roll_d20() -> int:
        """擲 d20 骰子 (回傳 1-20)"""
        return random.randint(1, 20)
        
    @staticmethod
    def roll(expr: str) -> int:
        """解析並擲骰，支援如 '1d20+5' 或 '1d100' 格式"""
        match = re.match(r'^(\d+)[dD](\d+)(?:([+-])(\d+))?$', expr.strip())
        if not match:
            raise ValueError(f"無效的骰子表達式: {expr}")
            
        count = int(match.group(1))
        sides = int(match.group(2))
        
        total = sum(random.randint(1, sides) for _ in range(count))
        
        if match.group(3):
            modifier = int(match.group(4))
            if match.group(3) == '+':
                total += modifier
            else:
                total -= modifier
                
        return total

    @staticmethod
    def check_d100(chance: int, roll_value: int = None) -> bool:
        """
        CoC 風格 d100 判定：擲出點數 <= 成功率 則成功
        """
        if roll_value is None:
            roll_value = Dice.roll_d100()
        return roll_value <= chance

    @staticmethod
    def check_d20(dc: int, roll_value: int = None, modifier: int = 0) -> bool:
        """
        D&D 風格 d20 判定：擲出點數 + 加成 >= DC 則成功
        """
        if roll_value is None:
            roll_value = Dice.roll_d20()
        return (roll_value + modifier) >= dc

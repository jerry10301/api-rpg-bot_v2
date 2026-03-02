from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class Character:
    name: str
    level: int = 1
    hp: int = 0
    max_hp: int = 0
    mp: int = 0
    max_mp: int = 0
    money: int = 0
    exp: int = 0
    
    # 核心屬性 (1-100)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "STR": 10, # 力量
        "DEX": 10, # 敏捷
        "CON": 10, # 體質
        "INT": 10, # 智力
        "WIS": 10, # 精神
        "LUK": 10  # 幸運
    })
    
    # 技能與熟練度 { "技能名稱": 熟練度等級 }
    skills: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """初始化後計算最大生命與法力"""
        self.recalculate_max_stats()
        if self.hp == 0:
            self.hp = self.max_hp
        if self.mp == 0:
            self.mp = self.max_mp

    def recalculate_max_stats(self):
        """根據等級與屬性重新計算最大生命與法力上限"""
        con = self.stats.get("CON", 10)
        str_val = self.stats.get("STR", 10)
        int_val = self.stats.get("INT", 10)
        
        self.max_hp = 50 + (self.level * 10) + (con * 15) + (str_val * 5)
        self.max_mp = 25 + (self.level * 10) + (con * 10) + (int_val * 5)
    
    def update_stat(self, stat_name: str, amount: int) -> bool:
        """增加或減少特定屬性"""
        stat_name = stat_name.upper()
        if stat_name in self.stats:
            self.stats[stat_name] += amount
            # 確保屬性在合理範圍內 (例如 1-100)
            self.stats[stat_name] = max(1, min(100, self.stats[stat_name]))
            # 屬性變動後重新計算上限
            self.recalculate_max_stats()
            return True
        return False

    def gain_money(self, amount: int):
        self.money += amount
        if self.money < 0:
            self.money = 0

    def gain_exp(self, amount: int):
        self.exp += amount
        self._check_level_up()

    def _check_level_up(self):
        # 簡單的升級邏輯：每 100 exp 升一級
        while self.exp >= self.level * 100:
            self.exp -= self.level * 100
            self.level += 1
            # 升級後重新計算上限並補滿
            self.recalculate_max_stats()
            self.hp = self.max_hp
            self.mp = self.max_mp
            # 升級時可以給予屬性點，此處先保持簡單

    def learn_skill(self, skill_name: str, initial_level: int = 1):
        """學習新技能或提升現有技能等級"""
        if skill_name in self.skills:
            self.skills[skill_name] += 1
        else:
            self.skills[skill_name] = initial_level

    def heal(self, hp_amount: int = 0, mp_amount: int = 0):
        """恢復生命與法力"""
        self.hp = min(self.max_hp, self.hp + hp_amount)
        self.mp = min(self.max_mp, self.mp + mp_amount)

    def full_rest(self):
        """完全恢復"""
        self.hp = self.max_hp
        self.mp = self.max_mp

    def get_status_report(self) -> str:
        """生成角色狀態文字報告"""
        report = f"=== {self.name} 的狀態卡 ===\n"
        report += f"等級: {self.level} | 經驗值: {self.exp}/{self.level * 100}\n"
        report += f"HP: {self.hp}/{self.max_hp} | MP: {self.mp}/{self.max_mp}\n"
        report += f"資金: {self.money} 金幣\n"
        report += "--- 屬性 ---\n"
        for stat, val in self.stats.items():
            report += f"{stat}: {val}\t"
        report += "\n--- 技能 ---\n"
        if not self.skills:
            report += "無\n"
        for skill, lvl in self.skills.items():
            report += f"{skill} (Lv.{lvl})\n"
        return report

from dataclasses import dataclass, field
from typing import Dict, Optional

# 屬性中文標籤對應表
STAT_LABELS = {
    "STR": "力量",
    "DEX": "敏捷",
    "CON": "體質",
    "INT": "智力",
    "WIS": "精神",
    "LUK": "幸運"
}

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
    
    # 技能與熟練度 { "技能名稱": {"level": int, "exp": int} }
    skills: Dict[str, dict] = field(default_factory=dict)
    
    # 異常狀態 { "狀態名稱": 剩餘回合 }
    status_effects: Dict[str, int] = field(default_factory=dict)
    
    # 物品欄 { "物品名稱": 數量 }
    inventory: Dict[str, int] = field(default_factory=dict)

    # 元素屬性 (預設無)
    element: Optional[str] = None

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
        wis = self.stats.get("WIS", 10)
        
        # 優化後的計算公式
        self.max_hp = 100 + (self.level * 20) + (con * 15) + (str_val * 5)
        self.max_mp = 50 + (self.level * 15) + (wis * 12) + (int_val * 8)
    
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

    def transfer_money(self, other: 'Character', amount: int) -> bool:
        """轉移金幣給另一個角色"""
        if amount <= 0 or self.money < amount:
            return False
        self.money -= amount
        other.gain_money(amount)
        return True

    def gain_exp(self, amount: int):
        self.exp += amount
        self._check_level_up()

    def _get_exp_required(self, level: int) -> int:
        """計算升至下一級所需的經驗值 (非線性公式: 100 * level^1.5)"""
        return int(100 * (level ** 1.5))

    def _check_level_up(self):
        """檢查是否升級並執行成長邏輯"""
        import random
        
        while self.exp >= self._get_exp_required(self.level):
            self.exp -= self._get_exp_required(self.level)
            self.level += 1
            
            # 1. 基礎屬性成長：全屬性 +1
            for stat in self.stats:
                self.stats[stat] += 1
            
            # 2. 額外隨機成長：隨機選 2 項屬性額外 +1
            bonus_stats = random.sample(list(self.stats.keys()), 2)
            for stat in bonus_stats:
                self.stats[stat] += 1
                
            # 屬性變動後重新計算上限並補滿
            self.recalculate_max_stats()
            self.hp = self.max_hp
            self.mp = self.max_mp
            print(f"*(系統)* 等級提升！目前等級: {self.level}，屬性獲得全面提升。")

    def learn_skill(self, skill_name: str, initial_level: int = 1):
        """學習新技能或提升現有技能等級"""
        if skill_name in self.skills:
            self.skills[skill_name]["level"] += 1
        else:
            self.skills[skill_name] = {"level": initial_level, "exp": 0}

    def gain_skill_exp(self, skill_name: str, amount: int = 10) -> Optional[str]:
        """增加技能熟練度，並處理升級邏輯，回傳升級訊息（若有）"""
        if skill_name not in self.skills:
            return None
            
        skill_data = self.skills[skill_name]
        skill_data["exp"] += amount
        
        # 升級邏輯：所需經驗 = level * 100
        level_up_msg = None
        current_level = skill_data["level"]
        req_exp = current_level * 100
        
        while skill_data["exp"] >= req_exp:
            skill_data["exp"] -= req_exp
            skill_data["level"] += 1
            current_level = skill_data["level"]
            req_exp = current_level * 100
            level_up_msg = f"✨ 熟練度突破！你的【{skill_name}】升級到了 Lv.{current_level}！威力提升了！"
            
        return level_up_msg

    def add_item(self, item_name: str, amount: int = 1):
        """獲得物品"""
        if item_name in self.inventory:
            self.inventory[item_name] += amount
        else:
            self.inventory[item_name] = amount

    def remove_item(self, item_name: str, amount: int = 1) -> bool:
        """消耗物品，返回是否成功"""
        if item_name in self.inventory and self.inventory[item_name] >= amount:
            self.inventory[item_name] -= amount
            if self.inventory[item_name] <= 0:
                del self.inventory[item_name]
            return True
        return False

    def transfer_item(self, other: 'Character', item_name: str, amount: int = 1) -> bool:
        """轉移物品給另一個角色"""
        if amount <= 0 or not self.remove_item(item_name, amount):
            return False
        other.add_item(item_name, amount)
        return True

    def heal(self, hp_amount: int = 0, mp_amount: int = 0):
        """恢復生命與法力"""
        self.hp = min(self.max_hp, self.hp + hp_amount)
        self.mp = min(self.max_mp, self.mp + mp_amount)

    def full_rest(self):
        """完全恢復"""
        self.hp = self.max_hp
        self.mp = self.max_mp
        self.status_effects.clear()

    def apply_status(self, effect_name: str, duration: int):
        """施加異常狀態"""
        # 如果已有同名狀態，取較長的持續時間
        self.status_effects[effect_name] = max(self.status_effects.get(effect_name, 0), duration)

    def process_status_effects(self) -> list:
        """處理每回合更新的異常狀態效果，回傳訊息清單"""
        messages = []
        to_remove = []
        
        for effect, duration in self.status_effects.items():
            # 處理每回合扣血效果 (DOT)
            if effect == "燃燒":
                dmg = max(1, int(self.max_hp * 0.05))
                self.hp = max(0, self.hp - dmg)
                messages.append(f"燃燒灼痛！失去 {dmg} 點 HP。")
            elif effect == "中毒":
                dmg = 10 # 固定的毒傷，可依等級調整
                self.hp = max(0, self.hp - dmg)
                messages.append(f"毒發攻心！失去 {dmg} 點 HP。")
                
            # 減少持續時間
            self.status_effects[effect] -= 1
            if self.status_effects[effect] <= 0:
                to_remove.append(effect)
                messages.append(f"狀態【{effect}】已解除。")
                
        for effect in to_remove:
            del self.status_effects[effect]
            
        return messages

    def get_status_report(self) -> str:
        """生成角色狀態文字報告"""
        report = f"=== {self.name} 的狀態卡 ===\n"
        next_exp = self._get_exp_required(self.level)
        report += f"等級: {self.level} | 經驗值: {self.exp}/{next_exp}\n"
        report += f"HP: {self.hp}/{self.max_hp} | MP: {self.mp}/{self.max_mp}\n"
        report += f"資金: {self.money} 金幣\n"
        report += "--- 屬性 ---\n"
        for stat, val in self.stats.items():
            label = STAT_LABELS.get(stat, "")
            report += f"{stat} ({label}): {val}\n"
        report += "\n--- 技能 ---\n"
        if not self.skills:
            report += "無\n"
        else:
            for skill, data in self.skills.items():
                lvl = data.get("level", 1)
                exp = data.get("exp", 0)
                req_exp = lvl * 100
                report += f"{skill} (Lv.{lvl} | Exp: {exp}/{req_exp})\n"
        return report

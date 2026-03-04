import json
import os

filepath = 'data/skills.json'

with open(filepath, 'r', encoding='utf-8') as f:
    skills = json.load(f)

# Handled effects defined in battle_engine.py
HANDLED_EFFECTS = ["燃燒", "中毒", "凍結", "石化", "麻痺"]

for skill_id, skill_data in skills.items():
    # 1. Standardize creator
    if "creator" not in skill_data:
        skill_data["creator"] = "系統"

    # 2. Standardize required_stat
    if skill_data.get("required_stat") == "AGI":
        skill_data["required_stat"] = "DEX"

    # 3. Standardize elements (non-standard to physical)
    element = skill_data.get("element")
    if element in ["金屬", "鋼", "poison"]:
        skill_data["element"] = "physical"

    # 4. Standardize status_effect
    status_effect = skill_data.get("status_effect")
    if status_effect and status_effect not in HANDLED_EFFECTS:
        skill_data["status_effect"] = None
        skill_data["effect_chance"] = 0

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(skills, f, ensure_ascii=False, indent=4)

print("skills.json cleaned successfully.")

import sys
from services.engine import GameEngine

def print_help():
    print("""
=============== 可用指令 ===============
/help           - 顯示此幫助選單
/status         - 查看目前角色狀態與能力值
/questlog       - 查看目前接取的任務與進度
/explore        - 隨機接取一個符合當前等級的任務
/quest [id]     - 找 NPC 接取指定的任務
/items          - 🎒 查看目前擁有的物品
/skill-list     - 📜 查看目前習得的技能 (詳細資訊)
/use [id]       - 🧪 使用物品
/give coin [id] [數量] - 💰 將金幣轉移給其他玩家
/give item [id] [物品] [數量] - 📦 將物品轉移給其他玩家
/shop list      - 📋 查看商店商品清單
/shop buy [名] [數] - 🛍️ 購買商店物品
/shop sell [名] [數]- 💰 販售物品換取金幣 (1/10 價)
/rank level     - 🌟 查看全服等級排行榜
/rank coin      - 💰 查看全服 10 大富豪榜
/rest           - 😴 休息並補滿 HP 與 MP
/work           - 🌟 執行接取的一般任務 (非討伐)
/findmonst      - ⚔️ 尋找怪物並進入戰鬥模式
/turnin [id]    - 🏆 回報已完成的任務
/skill [名] [動]- 🗡️ 在戰鬥中施放特定技能
/forget-skill [名]- 🛞 遺忘一個技能
/attack [動]    - 嘗試進行任何動作或攻擊
/escape         - 🏃‍♂️ 嘗試從戰鬥中逃跑
/pk [id]        - ⚔️ 向玩家發出決鬥邀請
/pk allow       - ✅ 接受決鬥邀請
/pk deny        - ❌ 拒絕決鬥邀請
/exit           - 離開遊戲
========================================
    """)

def main():
    print("歡迎來到【AI RPG - 魔法學院】")
    print("系統初始化中...")
    try:
        engine = GameEngine()
    except Exception as e:
        print(f"初始化系統時發生錯誤: {e}")
        return

    print("初始化完成！輸入 /help 查看可用指令。")

    while True:
        try:
            cmd_line = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n遊戲結束。")
            break

        if not cmd_line:
            continue

        if cmd_line == "/exit":
            print("遊戲結束。")
            break
        elif cmd_line == "/help":
            print_help()
        elif cmd_line == "/status":
            print(engine.handle_status())
        elif cmd_line == "/questlog":
            print(engine.handle_questlog())
        elif cmd_line == "/explore":
            print(engine.handle_random_quest())
        elif cmd_line == "/items":
            print(engine.handle_items())
        elif cmd_line.startswith("/give coin"):
            parts = cmd_line.split(" ", 3)
            if len(parts) >= 4:
                _, _, target_id, amount_str = parts
                try:
                    amount = int(amount_str)
                    print(engine.handle_give_coin(target_id, amount))
                except ValueError:
                    print("錯誤: 金額必須是數字。")
            else:
                print("錯誤: 格式為 /give coin [玩家ID] [數量]")
        elif cmd_line.startswith("/give item"):
            parts = cmd_line.split(" ", 4)
            if len(parts) >= 4:
                target_id = parts[2]
                item_name = parts[3]
                amount = 1
                if len(parts) >= 5:
                    try:
                        amount = int(parts[4])
                    except ValueError:
                        print("錯誤: 數量必須是數字。")
                        amount = 0
                if amount > 0:
                    print(engine.handle_give_item(target_id, item_name, amount))
            else:
                print("錯誤: 格式為 /give item [玩家ID] [物品名稱] [數量]")
        elif cmd_line == "/shop list":
            print(engine.handle_shop_list())
        elif cmd_line.startswith("/shop buy"):
            parts = cmd_line.split(" ", 3)
            # /shop buy [物品ID] [數量]
            if len(parts) >= 3:
                item_name = parts[2]
                amount = 1
                if len(parts) >= 4:
                    try:
                        amount = int(parts[3])
                    except ValueError:
                        print("數量格式不正確，將使用預設值 1。")
                print(engine.handle_shop_buy(item_name, amount))
            else:
                print("錯誤: 格式為 /shop buy [物品ID/名稱] [數量]")
        elif cmd_line.startswith("/shop sell"):
            parts = cmd_line.split(" ", 3)
            if len(parts) >= 3:
                item_name = parts[2]
                amount = 1
                if len(parts) >= 4:
                    try:
                        amount = int(parts[3])
                    except ValueError:
                        print("數量格式不正確，將使用預設值 1。")
                print(engine.handle_shop_sell(item_name, amount))
            else:
                print("錯誤: 格式為 /shop sell [物品ID/名稱] [數量]")
        elif cmd_line == "/rank level":
            ranks = engine.handle_rank_level()
            if not ranks:
                print("目前尚無排行榜資料。")
            else:
                print("=== 🌟 全服等級排行榜 (Top 10) ===")
                for i, r in enumerate(ranks, 1):
                    print(f"{i:2d}. {r['name']:<12} | Lv.{r['level']:<3} (EXP: {r['exp']})")
        elif cmd_line == "/rank coin":
            ranks = engine.handle_rank_coin()
            if not ranks:
                print("目前尚無排行榜資料。")
            else:
                print("=== 💰 全服 10 大富豪榜 ===")
                for i, r in enumerate(ranks, 1):
                    print(f"{i:2d}. {r['name']:<12} | {r['money']} 枚金幣")
        elif cmd_line == "/rest":
            print(engine.handle_rest())
        elif cmd_line == "/escape":
            print(engine.handle_escape())
        elif cmd_line.startswith("/pk"):
            parts = cmd_line.split(" ")
            if len(parts) >= 2:
                action = parts[1]
                if action == "allow":
                    narrative, _ = engine.handle_pk_allow()
                    print(narrative)
                elif action == "deny":
                    print(engine.handle_pk_deny())
                else:
                    # 預設為邀請
                    target_id = action
                    print(engine.handle_pk_invite(target_id))
            else:
                print("錯誤: 格式為 /pk [邀請ID] 或 /pk allow/deny")
        elif cmd_line == "/skills" or cmd_line == "/skill-list":
            print(engine.handle_skills())
        elif cmd_line.startswith("/use"):
            parts = cmd_line.split(" ", 1)
            if len(parts) > 1:
                item_id = parts[1].strip()
                print(engine.handle_use_item(item_id))
            else:
                print("錯誤: 請提供物品名稱或 ID。例如 /use 小紅水")
        elif cmd_line == "/findmonst":
            print(engine.handle_findmonst())
        elif cmd_line.startswith("/quest"):
            parts = cmd_line.split(" ", 1)
            if len(parts) > 1:
                quest_id = parts[1].strip()
                print(engine.handle_quest(quest_id))
            else:
                print("錯誤: 請提供任務 ID。例如 /quest quest_mopping")
        elif cmd_line.startswith("/work"):
            parts = cmd_line.split(" ", 1)
            if len(parts) > 1:
                quest_id = parts[1].strip()
                print(engine.handle_work(quest_id))
            else:
                print(engine.handle_work())
        elif cmd_line.startswith("/turnin"):
            parts = cmd_line.split(" ", 1)
            if len(parts) > 1:
                quest_id = parts[1].strip()
                print(engine.handle_turnin(quest_id))
            else:
                print("錯誤: 請提供回報任務的 ID。例如 /turnin quest_hunt_slime")
        elif cmd_line.startswith("/skill "):
            # /skill [技能名稱] [可選動作描述]
            parts = cmd_line.split(" ", 2)
            if len(parts) > 1:
                skill_name = parts[1].strip()
                action = parts[2].strip() if len(parts) > 2 else ""
                print(engine.handle_skill_use(skill_name, action))
            else:
                print("錯誤: 請提供技能名稱。例如 /skill Fireball")
        elif cmd_line.startswith("/forget-skill"):
            parts = cmd_line.split(" ", 1)
            if len(parts) > 1:
                skill_name = parts[1].strip()
                print(engine.handle_forget_skill(skill_name))
            else:
                print("錯誤: 請提供要遺忘的技能名稱。")
        elif cmd_line.startswith("/attack"):
            parts = cmd_line.split(" ", 1)
            if len(parts) > 1:
                action = parts[1].strip()
                print(engine.handle_action(action))
            else:
                print("錯誤: 請提供動作描述。例如 /attack 揮拳打向史萊姆")
        elif cmd_line.startswith("/"):
            print("未知的指令。輸入 /help 查看可用清單。")
        else:
            # 沒加上 /attack，也可預設為動作
            print(engine.handle_action(cmd_line))

if __name__ == "__main__":
    main()

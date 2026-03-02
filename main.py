import sys
from services.engine import GameEngine

def print_help():
    print("""
=============== 可用指令 ===============
/help       - 顯示此幫助選單
/status     - 查看目前角色狀態與能力值
/questlog   - 查看目前接取的任務與進度
/explore    - 隨機接取一個符合當前等級的任務
/quest [id] - 找 NPC 接取指定的任務 (如 /quest quest_hunt_slime)
/work       - 🌟 執行接取的一般任務 (非討伐)
/findmonst  - 🌟 尋找怪物並進入戰鬥模式
/turnin [id]- 🌟 回報已完成的任務 (如 /turnin quest_hunt_slime)
/attack [動]- 嘗試進行任何動作或攻擊 (戰鬥中為回合攻擊)
/exit       - 離開遊戲
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

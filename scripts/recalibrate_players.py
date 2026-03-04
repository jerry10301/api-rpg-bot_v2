"""
scripts/recalibrate_players.py
根據新的 HP/MP 公式，重新校準資料庫內所有玩家的 max_hp / max_mp / hp / mp。

校準原則：
  - 保留所有屬性值（STR/DEX/CON/INT/WIS/LUK）—— 任務加成不受影響
  - 保留等級、金幣、EXP、技能、物品 —— 完全不動
  - max_hp / max_mp 依新公式重算
  - 當前 hp / mp 按比例還原（保留血量百分比），最少保留 1 點
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_connection, DB_PATH

# ── 新公式（與 character.py 一致）──────────────────────────────────────────
def new_max_hp(level: int, con: int, str_: int) -> int:
    return 20 + (level * 8) + (con * 4) + (str_ * 1)

def new_max_mp(level: int, wis: int, int_: int) -> int:
    return 15 + (level * 6) + (wis * 4) + (int_ * 2)
# ─────────────────────────────────────────────────────────────────────────────


def recalibrate():
    conn = get_connection(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT discord_user_id, name, level, hp, max_hp, mp, max_mp, "
            "stat_str, stat_dex, stat_con, stat_int, stat_wis, stat_luk "
            "FROM players"
        ).fetchall()

        if not rows:
            print("資料庫內沒有任何玩家資料。")
            return

        print(f"找到 {len(rows)} 位玩家，開始校準...\n")
        print(f"{'玩家名稱':<16} {'等級':>4} | {'舊max_hp':>8} {'新max_hp':>8} | {'舊max_mp':>8} {'新max_mp':>8} | {'舊hp':>6} {'新hp':>6} | {'舊mp':>6} {'新mp':>6}")
        print("-" * 100)

        updates = []
        for row in rows:
            uid        = row["discord_user_id"]
            name       = row["name"]
            level      = row["level"]
            old_hp     = row["hp"]
            old_max_hp = row["max_hp"]
            old_mp     = row["mp"]
            old_max_mp = row["max_mp"]

            stat_str = row["stat_str"]
            stat_con = row["stat_con"]
            stat_int = row["stat_int"]
            stat_wis = row["stat_wis"]

            # 用新公式計算上限
            n_max_hp = new_max_hp(level, stat_con, stat_str)
            n_max_mp = new_max_mp(level, stat_wis, stat_int)

            # 按比例保留當前血量（最少 1）
            hp_ratio = old_hp / old_max_hp if old_max_hp > 0 else 1.0
            mp_ratio = old_mp / old_max_mp if old_max_mp > 0 else 1.0
            n_hp = max(1, round(n_max_hp * hp_ratio))
            n_mp = max(0, round(n_max_mp * mp_ratio))

            # 不超上限
            n_hp = min(n_hp, n_max_hp)
            n_mp = min(n_mp, n_max_mp)

            print(
                f"{name:<16} {level:>4}級 | "
                f"{old_max_hp:>8} {n_max_hp:>8} | "
                f"{old_max_mp:>8} {n_max_mp:>8} | "
                f"{old_hp:>6} {n_hp:>6} | "
                f"{old_mp:>6} {n_mp:>6}"
            )
            updates.append((n_hp, n_max_hp, n_mp, n_max_mp, uid))

        print()
        confirm = input("確認要套用以上校準結果嗎？(y/N): ").strip().lower()
        if confirm != "y":
            print("已取消，資料庫未做任何變更。")
            return

        conn.execute("BEGIN TRANSACTION")
        conn.executemany(
            "UPDATE players SET hp=?, max_hp=?, mp=?, max_mp=? WHERE discord_user_id=?",
            updates
        )
        conn.commit()
        print(f"\n✅ 成功校準 {len(updates)} 位玩家的 HP/MP 數值。")

    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"❌ 校準過程發生錯誤：{e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    recalibrate()

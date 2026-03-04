"""
bot/formatter.py
將 GameEngine 回傳的純文字轉換為 Discord Embed 格式。
"""
import discord


# ─── 顏色定義 ───────────────────────────────────────────────
COLOR_INFO    = 0x5865F2   # Discord 藍
COLOR_SUCCESS = 0x57F287   # 綠
COLOR_WARNING = 0xFEE75C   # 黃
COLOR_DANGER  = 0xED4245   # 紅
COLOR_COMBAT  = 0xEB459E   # 粉紅（戰鬥）
COLOR_QUEST   = 0xF8AA2A   # 橘（任務）


def _make_bar(current: int, maximum: int, length: int = 10, fill: str = "█", empty: str = "░") -> str:
    """製作文字進度條"""
    if maximum <= 0:
        ratio = 0.0
    else:
        ratio = max(0.0, min(1.0, current / maximum))
    filled = round(ratio * length)
    return fill * filled + empty * (length - filled)


def status_embed(player, player_name: str = None) -> discord.Embed:
    """角色狀態卡 Embed（接受 Character 物件）"""
    from core.character import STAT_LABELS

    # 向下相容：若傳入的是純文字字串（舊版呼叫），直接包在 code block 回傳
    if isinstance(player, str):
        embed = discord.Embed(
            title=f"📊 {player_name or '角色'} 的狀態卡",
            description=f"```\n{player}\n```",
            color=COLOR_INFO
        )
        return embed

    name = player.name
    level = player.level
    exp = player.exp
    next_exp = int(100 * (level ** 1.5))
    hp, max_hp = player.hp, player.max_hp
    mp, max_mp = player.mp, player.max_mp
    money = player.money

    # ── 顏色：依 HP 百分比 ──────────────────────────────────────
    hp_ratio = hp / max_hp if max_hp > 0 else 0
    if hp_ratio > 0.6:
        embed_color = 0x2ECC71   # 綠（健康）
    elif hp_ratio > 0.3:
        embed_color = 0xF39C12   # 橘（受傷）
    else:
        embed_color = 0xE74C3C   # 紅（危険）

    embed = discord.Embed(
        title=f"📊 {name} 的冒險者卡",
        color=embed_color
    )

    # ── 基本資訊 ───────────────────────────────────────────────
    hp_bar  = _make_bar(hp, max_hp)
    mp_bar  = _make_bar(mp, max_mp)
    exp_bar = _make_bar(exp, next_exp)

    basic_info = (
        f"⚔️ **等級 {level}**　💰 {money} 金幣\n"
        f"❤️ `{hp_bar}` {hp}/{max_hp}\n"
        f"💙 `{mp_bar}` {mp}/{max_mp}\n"
        f"✨ `{exp_bar}` {exp}/{next_exp} EXP"
    )
    embed.add_field(name="─── 基本資訊 ───", value=basic_info, inline=False)

    # ── 六大屬性 ───────────────────────────────────────────────
    stat_icons = {
        "STR": "💪", "DEX": "🌀", "CON": "🛡️",
        "INT": "🧠", "WIS": "🔮", "LUK": "🍀"
    }
    stat_lines = []
    for stat, val in player.stats.items():
        label = STAT_LABELS.get(stat, stat)
        icon  = stat_icons.get(stat, "▫️")
        bar   = _make_bar(val, 100, length=8)
        stat_lines.append(f"{icon} **{stat}** ({label})　`{bar}` **{val}**")

    # 分兩欄顯示
    half = len(stat_lines) // 2
    embed.add_field(name="─── 屬性 ───", value="\n".join(stat_lines[:half]), inline=True)
    embed.add_field(name="\u200b",         value="\n".join(stat_lines[half:]), inline=True)

    # ── 技能摘要 ───────────────────────────────────────────────
    if player.skills:
        skill_parts = []
        for skill_id, data in player.skills.items():
            lvl     = data.get("level", 1)
            sk_exp  = data.get("exp", 0)
            req_exp = lvl * 100
            skill_parts.append(f"• `{skill_id}` Lv.**{lvl}** ({sk_exp}/{req_exp})")
        embed.add_field(
            name="─── 已習得技能 ───",
            value="\n".join(skill_parts),
            inline=False
        )
    else:
        embed.add_field(name="─── 已習得技能 ───", value="尚未習得任何技能", inline=False)

    # ── 異常狀態 ───────────────────────────────────────────────
    if player.status_effects:
        status_str = "  ".join(
            f"【{e}】({d}回合)" for e, d in player.status_effects.items()
        )
        embed.add_field(name="⚠️ 異常狀態", value=status_str, inline=False)

    embed.set_footer(text="💡 /skills 查看技能詳情 | /items 查看物品欄 | /questlog 查看任務")
    return embed


def items_embed(text: str) -> discord.Embed:
    """物品欄 Embed"""
    embed = discord.Embed(
        title="🎒 物品欄",
        description=f"```\n{text}\n```",
        color=COLOR_INFO
    )
    return embed


def skills_embed(text: str) -> discord.Embed:
    """技能清單 Embed (舊版，保留相容性)"""
    embed = discord.Embed(
        title="🔮 技能清單",
        description=f"```\n{text}\n```",
        color=COLOR_INFO
    )
    return embed


def skill_list_embed(text: str, player_name: str) -> discord.Embed:
    """技能書 Embed（詳細版）"""
    embed = discord.Embed(
        title=f"📜 {player_name} 的技能書",
        description=text,
        color=0x9B59B6  # 紫色，象徵魔法
    )
    embed.set_footer(text="💡 使用 /skill <技能ID> 來施放技能 | /forget-skill <技能ID> 遺忘技能")
    return embed


def questlog_embed(text: str) -> discord.Embed:
    """任務日誌 Embed"""
    embed = discord.Embed(
        title="📜 任務日誌",
        description=text,
        color=COLOR_QUEST
    )
    return embed


def action_embed(text: str, title: str = "⚔️ 行動結果") -> discord.Embed:
    """一般行動 / 戰鬥結果 Embed"""
    # 嘗試自動判斷顏色（若文字含戰鬥結果關鍵字）
    color = COLOR_COMBAT
    if "失敗" in title or "被擊倒" in text:
        color = COLOR_DANGER
    elif "成功" in text or "擊敗" in text:
        color = COLOR_SUCCESS

    embed = discord.Embed(
        title=title,
        description=text,
        color=color
    )
    return embed


def info_embed(text: str, title: str = "💬 系統訊息") -> discord.Embed:
    """一般資訊 Embed"""
    embed = discord.Embed(
        title=title,
        description=text,
        color=COLOR_INFO
    )
    return embed


def error_embed(text: str) -> discord.Embed:
    """錯誤訊息 Embed"""
    embed = discord.Embed(
        title="❌ 錯誤",
        description=text,
        color=COLOR_DANGER
    )
    return embed


def quest_embed(text: str, title: str = "🗺️ 任務") -> discord.Embed:
    """任務接取 / 回報 Embed"""
    embed = discord.Embed(
        title=title,
        description=text,
        color=COLOR_QUEST
    )
    return embed


def rest_embed(text: str) -> discord.Embed:
    """休息結果 Embed"""
    embed = discord.Embed(
        title="😴 休息",
        description=text,
        color=COLOR_SUCCESS
    )
    return embed


def shop_embed(text: str, title: str = "🛒 商店系統") -> discord.Embed:
    """商店系統 Embed"""
    embed = discord.Embed(
        title=title,
        description=text,
        color=0xF1C40F  # 金色/黃色
    )
    return embed


def rank_embed(text: str, title: str = "🏆 排行榜") -> discord.Embed:
    """排行榜 Embed"""
    embed = discord.Embed(
        title=title,
        description=f"```\n{text}\n```",
        color=0xFFD700  # 金色
    )
    return embed


def pvp_embed(text: str, title: str = "⚔️ PvP 決鬥") -> discord.Embed:
    """PvP 決鬥系統 Embed"""
    embed = discord.Embed(
        title=title,
        description=text,
        color=0xE74C3C  # 鮮紅色，代表對戰
    )
    embed.set_footer(text="💡 /pk invite @玩家 挑戰 | /pk allow 接受 | /pk deny 拒絕")
    return embed


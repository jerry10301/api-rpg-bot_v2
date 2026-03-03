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


def status_embed(text: str, player_name: str) -> discord.Embed:
    """角色狀態卡 Embed"""
    embed = discord.Embed(
        title=f"📊 {player_name} 的狀態卡",
        description=f"```\n{text}\n```",
        color=COLOR_INFO
    )
    return embed


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
    """技能清單 Embed"""
    embed = discord.Embed(
        title="🔮 技能清單",
        description=f"```\n{text}\n```",
        color=COLOR_INFO
    )
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

"""
bot/bot.py
Discord Bot 主程式 — 讀取 .env 設定、載入 Slash Commands Cog 並啟動 bot。
"""
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# GUILD_ID 可選填：指定伺服器時 Slash Commands 立即生效（測試用）
# 不填則需等 Discord 全域同步（最多 1 小時）
GUILD_ID_STR = os.getenv("DISCORD_GUILD_ID", "")


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = False  # Slash Commands 不需要 message_content intent

    bot = commands.Bot(
        command_prefix="!",     # 保留 prefix 但主要用 Slash Commands
        intents=intents,
        help_command=None       # 停用預設的 !help
    )
    return bot


bot = create_bot()


@bot.event
async def on_ready():
    print(f"✅ Bot 已上線：{bot.user} (ID: {bot.user.id})")

    # 載入 Slash Commands Cog
    await bot.load_extension("bot.commands")

    # 同步 Slash Commands
    if GUILD_ID_STR:
        guild = discord.Object(id=int(GUILD_ID_STR))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"⚡ 已同步 {len(synced)} 個指令至測試伺服器 (Guild ID: {GUILD_ID_STR})")
    else:
        synced = await bot.tree.sync()
        print(f"🌍 已全域同步 {len(synced)} 個指令（最多需 1 小時生效）")


@bot.event
async def on_command_error(ctx, error):
    pass  # 忽略前綴指令錯誤，只使用 Slash Commands


def main():
    if not DISCORD_TOKEN:
        print("❌ 錯誤：請在 .env 設定 DISCORD_TOKEN")
        return
    print("🚀 正在啟動 AI RPG Bot...")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

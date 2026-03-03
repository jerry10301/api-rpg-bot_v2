"""
bot/commands.py
Discord Slash Commands — 對應 GameEngine 的各個 handle_* 方法。
每條指令執行完畢後呼叫 session_manager.flush_session() 持久化狀態。
"""
import discord
from discord import app_commands
from discord.ext import commands

from services.session_manager import session_manager
from db.player_repository import PlayerRepository
from db.database import DB_PATH
import bot.formatter as fmt


class RPGCommands(commands.Cog):
    """所有 RPG Slash Commands 的集合"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._repo = PlayerRepository(DB_PATH)

    # ─── 輔助：需要先 /register 才能使用的指令 ─────────────────────
    def _require_registered(self, interaction: discord.Interaction) -> bool:
        return session_manager.player_exists(str(interaction.user.id))

    # =================================================================
    # /register — 建立角色（首次使用）
    # =================================================================
    @app_commands.command(name="register", description="📝 建立你的冒險者角色（首次使用）")
    @app_commands.describe(name="角色名稱（留空則使用你的 Discord 顯示名稱）")
    async def register(self, interaction: discord.Interaction, name: str = None):
        user_id = str(interaction.user.id)
        if session_manager.player_exists(user_id):
            await interaction.response.send_message(
                embed=fmt.info_embed("你已經有角色了！使用 `/status` 查看狀態。", "⚠️ 已存在角色"),
                ephemeral=True
            )
            return

        char_name = name or interaction.user.display_name
        self._repo.create_player(user_id, char_name)
        # 建立 session（會從 DB 載入剛建立的角色）
        engine = session_manager.get_or_create_session(user_id)

        embed = discord.Embed(
            title="🎉 角色建立成功！",
            description=(
                f"歡迎來到【AI RPG - 魔法學院】，**{char_name}**！\n\n"
                "你的冒險即將展開。使用以下指令開始：\n"
                "• `/status` — 查看角色狀態\n"
                "• `/explore` — 探索並接取任務\n"
                "• `/findmonst` — 尋找怪物戰鬥"
            ),
            color=fmt.COLOR_SUCCESS
        )
        embed.set_footer(text=f"Discord ID: {user_id}")
        await interaction.response.send_message(embed=embed)

    # =================================================================
    # /status — 角色狀態
    # =================================================================
    @app_commands.command(name="status", description="📊 查看角色目前狀態與能力值")
    async def status(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        await interaction.response.defer()
        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_status()
        await interaction.followup.send(embed=fmt.status_embed(result, engine.player.name))

    # =================================================================
    # /questlog — 任務日誌
    # =================================================================
    @app_commands.command(name="questlog", description="📜 查看目前接取的任務與進度")
    async def questlog(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_questlog()
        await interaction.response.send_message(embed=fmt.questlog_embed(result))

    # =================================================================
    # /explore — 隨機接取任務
    # =================================================================
    @app_commands.command(name="explore", description="🗺️ 隨機接取一個符合等級的任務")
    async def explore(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_random_quest()
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.quest_embed(result, "🗺️ 探索任務"))

    # =================================================================
    # /quest <id> — 接取指定任務
    # =================================================================
    @app_commands.command(name="quest", description="📋 向 NPC 接取指定任務")
    @app_commands.describe(quest_id="任務 ID，例如 quest_hunt_slime")
    async def quest(self, interaction: discord.Interaction, quest_id: str):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_quest(quest_id)
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.quest_embed(result))

    # =================================================================
    # /work — 執行工作任務
    # =================================================================
    @app_commands.command(name="work", description="🌟 執行進行中的工作任務")
    @app_commands.describe(quest_id="（選填）指定任務 ID")
    async def work(self, interaction: discord.Interaction, quest_id: str = None):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        await interaction.response.defer()
        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_work(quest_id)
        session_manager.flush_session(user_id)
        await interaction.followup.send(embed=fmt.action_embed(result, "🌟 工作結果"))

    # =================================================================
    # /findmonst — 尋找怪物
    # =================================================================
    @app_commands.command(name="findmonst", description="⚠️ 尋找怪物並進入戰鬥！")
    async def findmonst(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_findmonst()
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.action_embed(result, "⚔️ 遭遇戰！"))

    # =================================================================
    # /attack <動作> — 攻擊 / 行動
    # =================================================================
    @app_commands.command(name="attack", description="⚔️ 攻擊或行動（僅限戰鬥中使用）")
    @app_commands.describe(action="動作描述，例如「揮拳打向史萊姆」或「施放火球術」")
    async def attack(self, interaction: discord.Interaction, action: str):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        await interaction.response.defer()
        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_action(action)
        session_manager.flush_session(user_id)
        await interaction.followup.send(embed=fmt.action_embed(result))

    # =================================================================
    # /escape — 逃跑 (繞過 LLM)
    # =================================================================
    @app_commands.command(name="escape", description="🏃‍♂️ 嘗試從戰鬥中逃跑（依賴敏捷檢定）")
    async def escape(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        await interaction.response.defer()
        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_escape()
        session_manager.flush_session(user_id)
        await interaction.followup.send(embed=fmt.action_embed(result))

    # =================================================================
    # /turnin <id> — 回報任務
    # =================================================================
    @app_commands.command(name="turnin", description="🏆 回報已完成的任務並領取獎勵")
    @app_commands.describe(quest_id="任務 ID，例如 quest_hunt_slime")
    async def turnin(self, interaction: discord.Interaction, quest_id: str):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        await interaction.response.defer()
        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_turnin(quest_id)
        session_manager.flush_session(user_id)
        await interaction.followup.send(embed=fmt.quest_embed(result, "🏆 任務回報結算"))

    # =================================================================
    # /rest — 休息補血
    # =================================================================
    @app_commands.command(name="rest", description="😴 好好休息，完全恢復 HP 與 MP")
    async def rest(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_rest()
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.rest_embed(result))

    # =================================================================
    # /help — 指令說明
    # =================================================================
    @app_commands.command(name="help", description="❓ 查看所有可用指令說明")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 AI RPG - 魔法學院 指令手冊",
            color=fmt.COLOR_INFO
        )
        embed.add_field(name="🆕 首次使用", value="`/register [名稱]` — 建立角色", inline=False)
        embed.add_field(
            name="📊 角色管理",
            value=(
                "`/status` — 查看角色狀態\n"
                "`/questlog` — 任務日誌\n"
                "`/rest` — 完全恢復 HP/MP"
            ),
            inline=False
        )
        embed.add_field(
            name="🗺️ 任務系統",
            value=(
                "`/explore` — 隨機接取任務\n"
                "`/quest <id>` — 接取指定任務\n"
                "`/work [id]` — 執行工作任務\n"
                "`/turnin <id>` — 回報已完成任務"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ 戰鬥",
            value=(
                "`/findmonst` — 尋找怪物\n"
                "`/attack <動作>` — 攻擊或行動（戰鬥中）\n"
                "`/escape` — 嘗試逃離戰鬥"
            ),
            inline=False
        )
        embed.set_footer(text="AI RPG Bot v2 | 由 Ollama LLM 驅動")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """載入 Cog 的入口函式"""
    await bot.add_cog(RPGCommands(bot))

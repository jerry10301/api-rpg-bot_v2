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
    # 交易指令群組 (/give)
    # =================================================================
    give_group = app_commands.Group(name="give", description="🤝 交易系統：轉移金幣或物品給其他玩家")

    @give_group.command(name="coin", description="💰 將金幣轉移給其他玩家")
    @app_commands.describe(
        target="要接收金幣的玩家",
        amount="轉移的金幣數量"
    )
    async def give_coin(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_give_coin(str(target.id), amount)
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.info_embed(result, "💰 金幣轉移"))

    @give_group.command(name="item", description="📦 將物品轉移給其他玩家")
    @app_commands.describe(
        target="要接收物品的玩家",
        item_name="物品名稱或 ID",
        amount="轉移的數量（預設為 1）"
    )
    async def give_item(self, interaction: discord.Interaction, target: discord.Member, item_name: str, amount: int = 1):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_give_item(str(target.id), item_name, amount)
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.info_embed(result, "📦 物品轉移"))

    # =================================================================
    # 商店指令群組 (/shop)
    # =================================================================
    shop_group = app_commands.Group(name="shop", description="🛒 商店系統：購買與販售物品")

    @shop_group.command(name="list", description="📋 查看商店目前販售的商品")
    async def shop_list(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_shop_list()
        await interaction.response.send_message(embed=fmt.shop_embed(result))

    @shop_group.command(name="buy", description="🛍️ 從商店購買指定的物品")
    @app_commands.describe(
        item_name="要購買的物品名稱或 ID",
        amount="購買數量（預設 1）"
    )
    async def shop_buy(self, interaction: discord.Interaction, item_name: str, amount: int = 1):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_shop_buy(item_name, amount)
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.shop_embed(result, "🛍️ 購買物品"))

    @shop_group.command(name="sell", description="💰 將物品賣給商店換取金幣 (原價的1/10)")
    @app_commands.describe(
        item_name="要販售的物品名稱或 ID",
        amount="販售數量（預設 1）"
    )
    async def shop_sell(self, interaction: discord.Interaction, item_name: str, amount: int = 1):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_shop_sell(item_name, amount)
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.shop_embed(result, "💰 販售物品"))

    # =================================================================
    # 排行榜指令群組 (/rank)
    # =================================================================
    rank_group = app_commands.Group(name="rank", description="🏆 排行榜系統：查詢全服排名")

    @rank_group.command(name="level", description="🌟 查詢等級排名前 10 名玩家")
    async def rank_level(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = str(interaction.user.id)
        engine = session_manager.get_or_create_session(user_id)
        top_players = engine.handle_rank_level(limit=10)
        
        if not top_players:
            await interaction.followup.send(embed=fmt.error_embed("目前沒有任何玩家資料。"))
            return

        lines = []
        for i, p in enumerate(top_players, 1):
            lines.append(f"{i:2d}. {p['name']:<12} | Lv.{p['level']:<3} (EXP: {p['exp']})")
        
        text = "\n".join(lines)
        await interaction.followup.send(embed=fmt.rank_embed(text, "🏆 全服等級排行榜 (Top 10)"))

    @rank_group.command(name="coin", description="💰 查詢 10 大富豪榜")
    async def rank_coin(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = str(interaction.user.id)
        engine = session_manager.get_or_create_session(user_id)
        top_players = engine.handle_rank_coin(limit=10)
        
        if not top_players:
            await interaction.followup.send(embed=fmt.error_embed("目前沒有任何玩家資料。"))
            return

        lines = []
        for i, p in enumerate(top_players, 1):
            lines.append(f"{i:2d}. {p['name']:<12} | {p['money']} 枚金幣")
        
        text = "\n".join(lines)
        await interaction.followup.send(embed=fmt.rank_embed(text, "💰 全服 10 大富豪榜"))

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
        await interaction.followup.send(embed=fmt.status_embed(engine.player))

    # =================================================================
    # /items — 物品欄
    # =================================================================
    @app_commands.command(name="items", description="🎒 查看目前擁有的物品")
    async def items(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_items()
        await interaction.response.send_message(embed=fmt.info_embed(result, "🎒 物品欄"))

    # =================================================================
    # /use — 使用物品
    # =================================================================
    @app_commands.command(name="use", description="🧪 使用物品")
    @app_commands.describe(
        item_name="物品名稱或 ID",
        extra_arg="附加參數，例如使用技能筆記本時指定要寫入的技能（選填）"
    )
    async def use_item(self, interaction: discord.Interaction, item_name: str, extra_arg: str = None):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_use_item(item_name, extra_arg)
        session_manager.flush_session(user_id)
        await interaction.response.send_message(embed=fmt.action_embed(result, "🧪 使用物品"))

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
    # /skill-list — 查看技能清單
    # =================================================================
    @app_commands.command(name="skill-list", description="📜 查看已學會的技能清單")
    async def skill_list(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_skills()
        await interaction.response.send_message(embed=fmt.skill_list_embed(result, engine.player.name))

    # =================================================================
    # /skill — 在戰鬥中施放技能
    # =================================================================
    @app_commands.command(name="skill", description="⚔️ 在戰鬥中施放技能")
    @app_commands.describe(
        name="技能ID 或中文名稱，例如 Fireball 或 火球術",
        action="附加動作描述（選填），例如「向史萊姆施放火球」"
    )
    async def skill(self, interaction: discord.Interaction, name: str, action: str = None):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        await interaction.response.defer()
        engine = session_manager.get_or_create_session(user_id)

        # action 未填時，自動帶入技能描述作為動作文字
        if not action:
            skill_data = engine.skills_db.get(name) or next(
                (v for v in engine.skills_db.values() if v.get("name") == name), {}
            )
            action = skill_data.get("description") or f"施放{name}"

        result = engine.handle_skill_use(name, action)
        session_manager.flush_session(user_id)
        await interaction.followup.send(embed=fmt.action_embed(result))

    # =================================================================
    # /forget-skill — 遺忘技能（含確認按鈕）
    # =================================================================
    @app_commands.command(name="forget-skill", description="🛞 遺忘一個已學會的技能")
    @app_commands.describe(name="要遺忘的技能ID 或中文名稱")
    async def forget_skill(self, interaction: discord.Interaction, name: str):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)

        # 驗證技能是否存在
        target_id = None
        skill_display_name = name
        if name in engine.player.skills:
            target_id = name
            skill_display_name = engine.skills_db.get(name, {}).get("name", name)
        else:
            for sid, data in engine.skills_db.items():
                if data.get("name") == name and sid in engine.player.skills:
                    target_id = sid
                    skill_display_name = data.get("name", sid)
                    break

        if not target_id:
            await interaction.response.send_message(
                embed=fmt.error_embed(f"你沒有學會技能【{name}】。"), ephemeral=True
            )
            return

        # 建立確認按鈕界面
        class ForgetConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False

            @discord.ui.button(label="確定遺忘", style=discord.ButtonStyle.danger, emoji="🛞")
            async def confirm(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                if btn_interaction.user.id != interaction.user.id:
                    await btn_interaction.response.send_message("這不是你的操作。", ephemeral=True)
                    return
                self.confirmed = True
                result = engine.handle_forget_skill(target_id)
                session_manager.flush_session(user_id)
                await btn_interaction.response.edit_message(
                    embed=fmt.action_embed(result, "🛞 技能遺忘"),
                    view=None
                )

            @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="❌")
            async def cancel(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                if btn_interaction.user.id != interaction.user.id:
                    return
                await btn_interaction.response.edit_message(
                    embed=fmt.info_embed("已取消遺忘技能。", "❌ 操作取消"),
                    view=None
                )

        view = ForgetConfirmView()
        await interaction.response.send_message(
            embed=fmt.info_embed(
                f"你確定要遺忘技能**【{skill_display_name}】**嗎？\n遺忘後不會影響其他玩家。",
                "🛞 技能遺忘確認"
            ),
            view=view,
            ephemeral=True
        )

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
                "`/rest` — 完全恢復 HP/MP\n"
                "`/rank level` — 查詢等級排行\n"
                "`/rank coin` — 查詢財富排行"
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
                "`/skill <名稱> [動作]` — 施放技能（戰鬥中）\n"
                "`/escape` — 嘗試逃離戰鬥"
            ),
            inline=False
        )
        embed.add_field(
            name="📜 技能管理",
            value=(
                "`/skill-list` — 查看已學會的技能清單\n"
                "`/forget-skill <名稱>` — 遺忘一個技能"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ PvP 決鬥",
            value=(
                "`/pk invite @玩家` — 向玩家發出決鬥邀請\n"
                "`/pk allow` — 接受待處理的決鬥邀請\n"
                "`/pk deny` — 拒絕待處理的決鬥邀請"
            ),
            inline=False
        )
        embed.set_footer(text="AI RPG Bot v2 | 由 Ollama LLM 驅動")
        await interaction.response.send_message(embed=embed)

    # =================================================================
    # /pk — PvP 決鬥系統
    # =================================================================
    pk_group = app_commands.Group(name="pk", description="⚔️ PvP 決鬥系統：向其他玩家發起決鬥")

    @pk_group.command(name="invite", description="⚔️ 向另一位玩家發起決鬥邀請")
    @app_commands.describe(target="要挑戰的玩家")
    async def pk_invite(self, interaction: discord.Interaction, target: discord.Member):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        if str(target.id) == user_id:
            await interaction.response.send_message(
                embed=fmt.error_embed("❌ 你不能挑戰自己！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_pk_invite(str(target.id))
        await interaction.response.send_message(embed=fmt.pvp_embed(result, "⚔️ 決鬥邀請"))

    @pk_group.command(name="allow", description="✅ 接受待處理的決鬥邀請")
    async def pk_allow(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        await interaction.response.defer()
        engine = session_manager.get_or_create_session(user_id)
        narrative, sys_result = engine.handle_pk_allow()
        await interaction.followup.send(embed=fmt.pvp_embed(narrative, "⚔️ 決鬥結果"))

    @pk_group.command(name="deny", description="❌ 拒絕待處理的決鬥邀請")
    async def pk_deny(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not self._require_registered(interaction):
            await interaction.response.send_message(
                embed=fmt.error_embed("請先使用 `/register` 建立角色！"), ephemeral=True
            )
            return

        engine = session_manager.get_or_create_session(user_id)
        result = engine.handle_pk_deny()
        await interaction.response.send_message(embed=fmt.pvp_embed(result, "🛡️ 拒絕決鬥"))


async def setup(bot: commands.Bot):
    """載入 Cog 的入口函式"""
    await bot.add_cog(RPGCommands(bot))


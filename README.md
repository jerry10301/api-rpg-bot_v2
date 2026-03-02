# AI RPG Bot (魔法學院)

基於 Python 的指令式文字 RPG，整合本地端 **Ollama LLM** 生成戰鬥與任務敘事。  
支援 **Discord 多人同時遊玩**，角色狀態儲存於本地 SQLite 資料庫。

---

## 系統需求

- Python 3.10+
- [Ollama](https://ollama.com/) 且已下載語言模型（預設 `qwen3:8b`，可於 `.env` 修改）
- Discord Bot Token（僅 Discord 模式需要）

---

## 安裝

```bash
pip install -r requirements.txt
```

---

## 設定 `.env`

複製以下內容至 `.env` 並填入對應值：

```env
# Ollama 設定
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Discord Bot 設定（CLI 模式可不填）
DISCORD_TOKEN=your_discord_bot_token_here
# 測試伺服器 ID（填入後 Slash Commands 立即生效，不填則需等 1 小時全域同步）
DISCORD_GUILD_ID=
```

---

## 執行方式

### 🖥️ CLI 本地模式（開發 / 測試用）

```bash
python main.py
```

### 🤖 Discord Bot 模式（正式多人）

```bash
python -m bot.bot
```

#### Discord Bot 建立步驟
1. 至 [Discord Developer Portal](https://discord.com/developers/applications) 建立 Application
2. 左側選 **Bot** → **Reset Token** 取得 Token
3. 左側選 **OAuth2 → URL Generator** → 勾選 `bot` + `applications.commands` scope
4. 填入你的 `DISCORD_TOKEN` 與 `DISCORD_GUILD_ID`
5. 啟動 bot 後在 Discord 輸入 `/register` 建立角色

---

## Discord Slash Commands

| 指令 | 說明 |
|---|---|
| `/register [名稱]` | 📝 建立冒險者角色（首次使用）|
| `/status` | 📊 查看角色狀態 |
| `/questlog` | 📜 查看任務日誌 |
| `/explore` | 🗺️ 隨機接取任務 |
| `/quest <id>` | 📋 接取指定任務 |
| `/work [id]` | 🌟 執行工作任務 |
| `/findmonst` | ⚠️ 尋找怪物進入戰鬥 |
| `/attack <動作>` | ⚔️ 攻擊或行動 |
| `/turnin <id>` | 🏆 回報任務領取獎勵 |
| `/rest` | 😴 完全恢復 HP/MP |
| `/help` | ❓ 查看指令說明 |

---

## 目錄結構

```
ai-rpg-bot_v2/
├── bot/                    # Discord Bot 層
│   ├── bot.py              # 主入口（啟動與 Slash Command 同步）
│   ├── commands.py         # 全部指令定義（Cog）
│   └── formatter.py        # Discord Embed 格式化
├── core/                   # 核心遊戲邏輯
│   ├── character.py        # 角色屬性與成長
│   ├── dice.py             # 骰子判定工具
│   └── quest_manager.py    # 任務管理與結算
├── db/                     # 資料持久化層（SQLite）
│   ├── database.py         # DB 連線與資料表初始化
│   └── player_repository.py# 玩家/任務/戰鬥狀態 CRUD
├── services/
│   ├── engine.py           # 遊戲引擎（整合各模組）
│   ├── session_manager.py  # 多用戶 Session 快取
│   ├── battle_engine.py    # 戰鬥回合計算
│   └── ollama_client.py    # LLM 連線與 Prompt 生成
├── data/                   # 遊戲資料 JSON
│   ├── quests.json         # 任務庫
│   ├── monsters.json       # 怪物圖鑑
│   ├── skills.json         # 技能資料
│   └── npcs.json           # NPC 設定
├── tests/                  # 單元測試
├── main.py                 # CLI 模式入口
├── game_data.db            # SQLite 資料庫（自動建立）
└── .env                    # 環境設定
```

---

## 執行測試

```bash
python -m pytest tests/ -v
```

#!/bin/bash
# 啟動 AI RPG Bot 的腳本

# 確保在專案根目錄執行
cd "$(dirname "$0")"

# 啟動虛擬環境 (Windows Bash 環境下通常使用 .venv/Scripts/activate 或 .venv/bin/activate)
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "⚠️ 找不到虛擬環境 (.venv)，嘗試直接使用系統 python..."
fi

echo "🚀 正在啟動 Bot..."
python run_bot.py

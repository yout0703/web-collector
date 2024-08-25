import os
import re
import sqlite3
from datetime import datetime
from difflib import SequenceMatcher

import httpx
from dotenv import load_dotenv
from loguru import logger
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# 创建或连接到 SQLite 数据库
conn = sqlite3.connect('websites.db')
cursor = conn.cursor()

# 创建表 c_website（如果尚未存在），增加 created_at 字段
cursor.execute('''
    CREATE TABLE IF NOT EXISTS c_website (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theme TEXT,
        url TEXT UNIQUE,
        title TEXT,
        response TEXT,
        created_at TIMESTAMP
    )
''')
conn.commit()

# 创建历史表 c_website_history（如果尚未存在）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS c_website_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theme TEXT,
        url TEXT,
        title TEXT,
        response TEXT,
        created_at TIMESTAMP
    )
''')
conn.commit()


# 定义提取主机名并获取主页 URL 的函数
def extract_homepage(url: str) -> str:
    pattern = r"(http[s]?://[^/]+)"
    match = re.match(pattern, url)
    if match:
        return match.group(1)
    return None


# 定义获取页面标题的函数
def get_page_title(url: str) -> str:
    try:
        response = httpx.get(url, timeout=60, follow_redirects=True)
        logger.info(f"URL: {url}, {response.text[:200]}...")  # 只记录前200字符
        response.raise_for_status()

        # 使用正则表达式提取 HTML 中的标题
        match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), response.text
        return "No title found", response.text
    except httpx.RequestError as e:
        return f"Request failed: {e}", ""
    except httpx.HTTPStatusError as e:
        return f"HTTP error: {e}", ""


# 定义计算相似度的函数
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# 定义处理用户消息的函数
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    # 检查消息是否是 URL 类型
    if re.match(r"http[s]?://", text):
        homepage = extract_homepage(text)
        if homepage:
            cursor.execute('SELECT id, theme, response FROM c_website WHERE url = ?', (homepage,))
            result = cursor.fetchone()

            if result:
                await update.message.reply_text(f"URL 已存在，主题为: {result[1]}")
            else:
                title, response_text = get_page_title(homepage)

                # 查找相似的记录
                cursor.execute('SELECT id, theme, response FROM c_website')
                all_records = cursor.fetchall()
                matched_theme = None

                for record in all_records:
                    existing_id, existing_theme, existing_response = record
                    if similarity(existing_response, response_text) > 0.8:
                        matched_theme = existing_theme
                        break

                if not matched_theme:
                    cursor.execute('SELECT COUNT(*) FROM c_website')
                    record_count = cursor.fetchone()[0]
                    matched_theme = f"模版_{record_count + 1}"

                # 将新的记录插入到数据库
                cursor.execute(
                    'INSERT INTO c_website (theme, url, title, response, created_at) VALUES (?, ?, ?, ?, ?)',
                    (matched_theme, homepage, title, response_text, datetime.now())
                )
                conn.commit()

                await update.message.reply_text(
                    f"添加成功！\n主页链接: {homepage}\n标题: {title}\n主题: {matched_theme}"
                )

    elif text == "列表":
        # 获取并按 theme 分组展示数据
        cursor.execute('SELECT theme, url, title FROM c_website ORDER BY theme')
        websites = cursor.fetchall()

        response = ""
        current_theme = None
        for website in websites:
            if website[0] != current_theme:
                current_theme = website[0]
                response += f"\n{current_theme}:\n"

            response += f"  - {website[1]}: {website[2]}\n"

        if response:
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("当前没有记录。")

    elif text == "清理":
        # 将所有数据移动到历史表并清空原表
        cursor.execute('INSERT INTO c_website_history SELECT * FROM c_website')
        cursor.execute('DELETE FROM c_website')
        conn.commit()
        await update.message.reply_text("数据已清理并转移到历史记录中。")

    else:
        await update.message.reply_text("这不是一个有效的链接或命令。")


# 主函数，用于启动机器人
def main() -> None:
    # 使用你的 Telegram bot token
    application = (
        Application.builder()
        .token(os.getenv("TELEGRAM_TOKEN"))
        .build()
    )

    # 注册消息处理器
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # 启动机器人并开始轮询
    application.run_polling()


if __name__ == "__main__":
    # 自动加载 .env 到 环境变量中
    load_dotenv()
    main()

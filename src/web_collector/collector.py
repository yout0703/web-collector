import re
import sqlite3
from datetime import datetime

import httpx
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
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
def get_page_title(url: str) -> (str, str):
    try:
        response = httpx.get(url, timeout=60, follow_redirects=True)
        logger.info(f"URL: {url}, {response.text[:200]}...")  # 只记录前200字符
        response.raise_for_status()

        # 使用正则表达式提取 HTML 中的标题
        match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), response.text
        return "No title found", response.text
    except Exception as e:
        return f"Request failed: {e}", ""


# 使用 TF-IDF 和余弦相似度计算文本相似度
def calculate_similarity(text1: str, text2: str) -> float:
    vectorizer = TfidfVectorizer().fit_transform([text1, text2])
    vectors = vectorizer.toarray()
    cosine_sim = cosine_similarity(vectors)
    s = cosine_sim[0, 1]  # 返回两个文本之间的相似度
    logger.info(f"Similarity: {s}")
    return s


# 定义处理用户消息的函数

import os
import tempfile


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    logger.info(f"Received message: {text}")

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
                cursor.execute('SELECT theme, response FROM c_website GROUP BY theme')
                theme_records = cursor.fetchall()
                matched_theme = None
                max_similarity = 0.0

                for theme, response in theme_records:
                    similarity = calculate_similarity(response_text, response)
                    if similarity > 0.9 and similarity > max_similarity:
                        matched_theme = theme
                        max_similarity = similarity

                if not matched_theme:
                    cursor.execute('SELECT COUNT(DISTINCT theme) FROM c_website')
                    theme_count = cursor.fetchone()[0]
                    matched_theme = f"模版_{theme_count + 1}"

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

        if websites:
            # 创建一个临时文件来存储数据
            with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as temp_file:
                current_theme = None
                for website in websites:
                    if website[0] != current_theme:
                        current_theme = website[0]
                        temp_file.write(f"\n{current_theme}:\n")

                    temp_file.write(f"  - {website[1]}: {website[2]}\n")

                temp_file_path = temp_file.name

            # 发送文件给用户
            await context.bot.send_document(chat_id=update.message.chat_id, document=open(temp_file_path, 'rb'))

            # 删除临时文件
            os.remove(temp_file_path)
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
def start_bot() -> None:
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
    logger.info("Bot started.")

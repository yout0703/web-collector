from dotenv import load_dotenv
from loguru import logger

from src.web_collector.collector import start_bot

if __name__ == "__main__":
    # 自动加载 .env 到 环境变量中
    logger.info("启动机器人...")
    load_dotenv()
    start_bot()

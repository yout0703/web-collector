import asyncio
import logging
import signal
from src.web_collector.config import Config
from src.web_collector.collector import WebCollector
from src.web_collector.database import Database
from src.web_collector.similarity import SimilarityAnalyzer
from src.web_collector.bot import WebTemplateBot

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """主函数"""
    try:
        # 加载配置
        config = Config()
        
        # 初始化组件
        collector = WebCollector(
            timeout=config.get('collector.timeout', 30)
        )
        
        database = Database(
            db_path=config.get('database.path', 'website_templates.db')
        )
        
        analyzer = SimilarityAnalyzer(
            threshold=config.get('similarity.threshold', 0.4)
        )
        
        # 获取 Telegram Bot Token
        token = config.get('telegram.token')
        if not token:
            raise ValueError("未设置 Telegram Bot Token")
        
        # 创建 Bot
        bot = WebTemplateBot(token, database, collector, analyzer)
        
        # 启动 Bot
        await bot.start()
        
        # 等待中断信号
        stop = asyncio.Future()
        
        def signal_handler():
            stop.set_result(None)
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(sig, signal_handler)
        
        logger.info("Bot is ready. Press Ctrl+C to stop")
        await stop
        
        # 停止 Bot
        await bot.stop()
        
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}")

from telegram import Update, Document
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
from typing import Optional
from urllib.parse import urlparse
from .collector import WebCollector
from .database import Database
from .similarity import SimilarityAnalyzer
from datetime import datetime
from .collector import WebsiteFeatures
import tempfile
import os

class WebTemplateBot:
    """Telegram Bot 实现"""
    
    def __init__(self, token: str, db: Database, collector: WebCollector, analyzer: SimilarityAnalyzer):
        self.token = token
        self.db = db
        self.collector = collector
        self.analyzer = analyzer
        self.logger = logging.getLogger(__name__)
        
        # 创建应用
        self.app = Application.builder().token(token).build()
        
        # 注册处理器
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("template", self.template_command))
        self.app.add_handler(CommandHandler("list", self.list_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start(self):
        """启动机器人"""
        await self.db.initialize()
        self.logger.info("Starting bot...")
        await self.app.initialize()
        await self.app.start()
        self.logger.info("Bot is running...")
        await self.app.updater.start_polling()

    async def stop(self):
        """停止机器人"""
        self.logger.info("Stopping bot...")
        await self.app.updater.stop()
        await self.app.stop()
        self.logger.info("Bot stopped")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        await update.message.reply_text(
            "👋 欢迎使用网站模板分析机器人！\n\n"
            "你可以发送网站URL给我，我会分析网站并识别其使用的模板。\n"
            "使用 /help 查看所有可用命令。"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        help_text = (
            "🤖 可用命令列表：\n\n"
            "/analyze <url> - 分析网站\n"
            "/stats - 查看统计信息\n"
            "/template <id> - 查看模板详情\n"
            "/list - 下载完整的网站分组列表\n"
            "/help - 显示此帮助信息\n\n"
            "你也可以直接发送URL给我进行分析。"
        )
        await update.message.reply_text(help_text)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /stats 命令"""
        stats = await self.db.get_statistics()
        
        stats_text = (
            "📊 统计信息：\n\n"
            f"总网站数：{stats['total_websites']}\n"
            f"模板数量：{stats['total_templates']}\n\n"
            "最近分析的网站：\n"
        )
        
        for site in stats['recent_websites']:
            stats_text += f"• {site['url']} ({site['last_updated_at']})\n"
            
        await update.message.reply_text(stats_text)

    async def template_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /template 命令"""
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("请提供有效的模板ID，例如：/template 1")
            return
            
        template_id = int(context.args[0])
        websites = await self.db.get_template_websites(template_id)
        
        if not websites:
            await update.message.reply_text(f"未找到ID为 {template_id} 的模板")
            return
            
        response = f"📑 模板 #{template_id} 的网站列表：\n\n"
        for site in websites:
            response += f"• {site['url']}\n"
            
        await update.message.reply_text(response)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户消息"""
        if not update.message or not update.message.text:
            return
            
        message = update.message.text
        
        # 验证URL
        if not self._is_valid_url(message):
            await update.message.reply_text("请发送有效的网站URL")
            return
            
        # 发送等待消息
        wait_message = await update.message.reply_text("🔍 正在分析网站，请稍候...")
        
        try:
            # 分析网站
            features = await self.collector.analyze_url(message)
            if not features:
                await wait_message.edit_text("❌ 无法分析该网站，请确保网站可访问")
                return
                
            # 存储网站信息
            website_id = await self.db.add_website(message, features)
            
            # 获取所有现有模板
            templates = await self.db.get_all_templates()
            
            # 寻找最相似的模板
            max_similarity = 0
            similar_template_id = None
            
            for template_id, template_features in templates:
                # 将模板特征转换为 WebsiteFeatures 对象
                template_features['created_at'] = datetime.fromisoformat(template_features['created_at'])
                template_features['updated_at'] = datetime.fromisoformat(template_features['updated_at'])
                template_obj = WebsiteFeatures(**template_features)
                
                # 计算相似度
                similarity = self.analyzer.calculate_similarity(features, template_obj)
                if similarity > max_similarity:
                    max_similarity = similarity
                    similar_template_id = template_id

            # 构建响应消息
            response_text = [
                "✅ 分析完成！\n",
                f"URL: {message}\n",
                f"特征数: {len(features.css_classes)} CSS类, {len(features.js_libraries)} JS库"
            ]

            # 根据相似度决定是创建新模板还是使用现有模板
            if max_similarity >= self.analyzer.threshold and similar_template_id:
                # 使用现有模板
                await self.db.update_website_template(website_id, similar_template_id)
                await self.db.update_template_count(similar_template_id)
                response_text.append(f"\n\n🔍 匹配到现有模板 #{similar_template_id}")
                response_text.append(f"相似度: {max_similarity:.2%}")
            else:
                # 创建新模板
                new_template_id = await self.db.create_template_from_website(website_id)
                response_text.append(f"\n\n🆕 创建新模板 #{new_template_id}")
                response_text.append("没有找到足够相似的现有模板")

            # 添加性能指标
            if features.performance_metrics and 'loadTime' in features.performance_metrics:
                response_text.append(f"\n⚡ 加载时间: {features.performance_metrics['loadTime']}ms")
            
            # 添加JavaScript库信息
            if features.js_libraries:
                response_text.append(f"\n📚 检测到的JS库: {', '.join(features.js_libraries)}")
            
            await wait_message.edit_text("\n".join(response_text))
            
        except Exception as e:
            self.logger.error(f"处理URL时出错: {str(e)}")
            await wait_message.edit_text(
                "❌ 分析过程中出现错误，请稍后重试\n"
                f"错误信息: {str(e)}"
            )

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /list 命令，生成并发送网站列表文件"""
        try:
            # 发送等待消息
            wait_message = await update.message.reply_text("正在生成网站列表，请稍候...")
            
            # 获取分组数据
            templates = await self.db.get_grouped_websites()
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write("网站模板分组列表\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                
                for template in templates:
                    f.write(f"模板 #{template['template_id']}\n")
                    f.write(f"创建时间: {template['created_at']}\n")
                    f.write(f"网站数量: {template['website_count']}\n")
                    f.write("\n网站列表:\n")
                    
                    for website in template['websites']:
                        f.write(f"- {website['url']}\n")
                    
                    f.write("\n" + "-" * 30 + "\n\n")
                
                filename = f.name

            # 发送文件
            with open(filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename="website_templates.txt",
                    caption="📋 这是所有网站的分组列表"
                )
            
            # 删除临时文件
            os.unlink(filename)
            
            # 删除等待消息
            await wait_message.delete()
            
        except Exception as e:
            self.logger.error(f"生成列表失败: {str(e)}")
            await update.message.reply_text("❌ 生成列表时出现错误，请稍后重试")

    def _is_valid_url(self, url: str) -> bool:
        """验证URL是否有效"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
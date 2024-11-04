from datetime import datetime
from typing import Optional, List, Dict, Tuple
import aiosqlite
import json
import logging
from pathlib import Path
from .collector import WebsiteFeatures
from urllib.parse import urlparse

class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = "website_templates.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            # 创建网站记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS websites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    template_id INTEGER,
                    first_analyzed_at TIMESTAMP,
                    last_updated_at TIMESTAMP,
                    status TEXT,
                    features JSON,
                    FOREIGN KEY (template_id) REFERENCES templates (id)
                )
            """)

            # 创建模板分类表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP,
                    website_count INTEGER DEFAULT 0,
                    feature_summary JSON,
                    last_updated_at TIMESTAMP
                )
            """)
            
            await db.commit()

    async def add_website(self, url: str, features: WebsiteFeatures) -> int:
        """添加新的网站记录"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.now()
                cursor = await db.execute(
                    """
                    INSERT INTO websites (url, first_analyzed_at, last_updated_at, status, features)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (url, now, now, "analyzed", json.dumps(features.to_dict()))
                )
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"添加网站记录失败: {str(e)}")
            raise

    async def update_website_template(self, website_id: int, template_id: int):
        """更新网站的模板ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    UPDATE websites 
                    SET template_id = ?, last_updated_at = ?
                    WHERE id = ?
                    """,
                    (template_id, datetime.now(), website_id)
                )
                await db.commit()
        except Exception as e:
            self.logger.error(f"更新网站模板失败: {str(e)}")
            raise

    async def create_template(self, feature_summary: dict) -> int:
        """创建新的模板记录"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.now()
                cursor = await db.execute(
                    """
                    INSERT INTO templates (created_at, website_count, feature_summary, last_updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (now, 1, json.dumps(feature_summary), now)
                )
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"创建模板失败: {str(e)}")
            raise

    async def get_website_features(self, url: str) -> Optional[dict]:
        """获取网站特征"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT features FROM websites WHERE url = ?",
                    (url,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return json.loads(row['features']) if row else None
        except Exception as e:
            self.logger.error(f"获取网站特征失败: {str(e)}")
            return None

    async def get_template_websites(self, template_id: int) -> List[Dict]:
        """获取使用特定模板的所有网站"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT url, first_analyzed_at, last_updated_at
                    FROM websites
                    WHERE template_id = ?
                    """,
                    (template_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"获取模板网站失败: {str(e)}")
            return []

    async def get_statistics(self) -> Dict:
        """获取统计信息"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 获取网站总数
                async with db.execute("SELECT COUNT(*) FROM websites") as cursor:
                    total_websites = (await cursor.fetchone())[0]

                # 获取模板总数
                async with db.execute("SELECT COUNT(*) FROM templates") as cursor:
                    total_templates = (await cursor.fetchone())[0]

                # 获取最近分析的网站
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT url, last_updated_at 
                    FROM websites 
                    ORDER BY last_updated_at DESC 
                    LIMIT 5
                    """
                ) as cursor:
                    recent_websites = [dict(row) for row in await cursor.fetchall()]

                return {
                    "total_websites": total_websites,
                    "total_templates": total_templates,
                    "recent_websites": recent_websites
                }
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}")
            return {
                "total_websites": 0,
                "total_templates": 0,
                "recent_websites": []
            }

    async def cleanup_old_records(self, days: int = 30):
        """清理超过指定天数的旧记录"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    DELETE FROM websites 
                    WHERE last_updated_at < datetime('now', ?)
                    """,
                    (f'-{days} days',)
                )
                await db.commit()
        except Exception as e:
            self.logger.error(f"清理旧记录失败: {str(e)}")

    async def get_all_templates(self) -> List[Tuple[int, Dict]]:
        """获取所有模板及其特征"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT t.id, w.features
                    FROM templates t
                    JOIN websites w ON w.template_id = t.id
                    WHERE w.id IN (
                        SELECT MIN(id)
                        FROM websites
                        WHERE template_id IS NOT NULL
                        GROUP BY template_id
                    )
                    """
                ) as cursor:
                    templates = await cursor.fetchall()
                    return [(t['id'], json.loads(t['features'])) for t in templates]
        except Exception as e:
            self.logger.error(f"获取模板失败: {str(e)}")
            return []

    async def update_template_count(self, template_id: int):
        """更新模板的网站数量"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 获取该模板的网站数量
                async with db.execute(
                    "SELECT COUNT(*) FROM websites WHERE template_id = ?",
                    (template_id,)
                ) as cursor:
                    count = (await cursor.fetchone())[0]

                # 更新模板记录
                await db.execute(
                    """
                    UPDATE templates 
                    SET website_count = ?, last_updated_at = ?
                    WHERE id = ?
                    """,
                    (count, datetime.now(), template_id)
                )
                await db.commit()
        except Exception as e:
            self.logger.error(f"更新模板数量失败: {str(e)}")
            raise

    async def create_template_from_website(self, website_id: int) -> int:
        """从网站创建新模板"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 获取网站特征
                async with db.execute(
                    "SELECT features FROM websites WHERE id = ?",
                    (website_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        raise ValueError(f"Website {website_id} not found")
                    features = json.loads(row[0])

                # 创建新模板
                now = datetime.now()
                cursor = await db.execute(
                    """
                    INSERT INTO templates (created_at, website_count, feature_summary, last_updated_at)
                    VALUES (?, 1, ?, ?)
                    """,
                    (now, json.dumps(features), now)
                )
                template_id = cursor.lastrowid

                # 更新网站的模板ID
                await db.execute(
                    "UPDATE websites SET template_id = ? WHERE id = ?",
                    (template_id, website_id)
                )
                await db.commit()
                return template_id
        except Exception as e:
            self.logger.error(f"创建模板失败: {str(e)}")
            raise

    async def get_grouped_websites(self) -> List[Dict]:
        """获取按模板分组的网站列表"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                # 获取所有模板及其关联的网站
                async with db.execute(
                    """
                    SELECT 
                        t.id as template_id,
                        t.website_count,
                        t.created_at as template_created_at,
                        w.url,
                        w.first_analyzed_at,
                        w.last_updated_at
                    FROM templates t
                    LEFT JOIN websites w ON w.template_id = t.id
                    ORDER BY t.id, w.first_analyzed_at
                    """
                ) as cursor:
                    rows = await cursor.fetchall()
                    
                    # 组织数据结构
                    templates = {}
                    for row in rows:
                        template_id = row['template_id']
                        if template_id not in templates:
                            templates[template_id] = {
                                'template_id': template_id,
                                'website_count': row['website_count'],
                                'created_at': row['template_created_at'],
                                'websites': []
                            }
                        if row['url']:  # 确保网站URL存在
                            templates[template_id]['websites'].append({
                                'url': row['url'],
                                'first_analyzed_at': row['first_analyzed_at'],
                                'last_updated_at': row['last_updated_at']
                            })
                    
                    return list(templates.values())
        except Exception as e:
            self.logger.error(f"获取分组网站列表失败: {str(e)}")
            return []

    async def get_website_by_host(self, url: str) -> Optional[Dict]:
        """根据域名获取网站信息"""
        try:
            # 解析URL获取host
            parsed_url = urlparse(url)
            host = parsed_url.netloc
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT w.*, t.id as template_id
                    FROM websites w
                    LEFT JOIN templates t ON w.template_id = t.id
                    WHERE w.url LIKE ?
                    ORDER BY w.last_updated_at DESC
                    LIMIT 1
                    """,
                    (f"%{host}%",)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            return None
        except Exception as e:
            self.logger.error(f"获取网站信息失败: {str(e)}")
            return None
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
from playwright.async_api import async_playwright, Page, TimeoutError
from bs4 import BeautifulSoup
import json
import logging

@dataclass
class WebsiteFeatures:
    """网站特征数据类"""
    url: str
    dom_structure: dict
    css_classes: List[str]
    js_libraries: List[str]
    responsive_features: dict
    color_scheme: List[str]
    fonts: List[str]
    performance_metrics: dict
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict())

class WebCollector:
    """网站数据收集器"""
    
    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    async def analyze_url(self, url: str) -> Optional[WebsiteFeatures]:
        """分析网站URL并提取特征"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                # 设置基本超时
                page.set_default_timeout(self.timeout * 1000)
                
                try:
                    # 等待页面加载，但设置较短的超时时间以获取部分内容
                    initial_timeout = min(30000, self.timeout * 1000)  # 30秒或总超时时间的较小值
                    await page.goto(url, wait_until='domcontentloaded', timeout=initial_timeout)
                except TimeoutError:
                    self.logger.warning(f"页面加载超时，将基于已加载内容进行分析: {url}")
                
                try:
                    # 收集特征，使用asyncio.wait_for来处理超时
                    features = await asyncio.wait_for(
                        self._collect_features(page, url),
                        timeout=max(5, self.timeout - 30)  # 留出一些时间给清理工作
                    )
                except asyncio.TimeoutError:
                    self.logger.warning("特征收集超时，使用已获取的数据")
                    # 使用已获取的部分数据创建特征对象
                    features = await self._collect_partial_features(page, url)
                
                await browser.close()
                return features
                
        except Exception as e:
            self.logger.error(f"分析URL时出错: {url}, 错误: {str(e)}")
            return None

    async def _collect_partial_features(self, page: Page, url: str) -> WebsiteFeatures:
        """收集部分页面特征（用于超时情况）"""
        try:
            # 获取当前可用的DOM结构
            dom_structure = await self._analyze_dom_structure(page)
        except Exception:
            dom_structure = {"tag": "body", "children": []}

        try:
            # 获取可见的CSS类
            css_classes = await self._extract_css_classes(page)
        except Exception:
            css_classes = []

        try:
            # 检测已加载的JS库
            js_libraries = await self._detect_js_libraries(page)
        except Exception:
            js_libraries = []

        try:
            # 获取响应式特征
            responsive_features = await self._analyze_responsive_features(page)
        except Exception:
            responsive_features = {"viewport": None, "mediaQueries": []}

        try:
            # 获取颜色方案
            color_scheme = await self._extract_color_scheme(page)
        except Exception:
            color_scheme = []

        try:
            # 获取字体信息
            fonts = await self._extract_fonts(page)
        except Exception:
            fonts = []

        try:
            # 获取性能指标
            performance_metrics = await self._collect_performance_metrics(page)
        except Exception:
            performance_metrics = {
                "loadTime": 0,
                "domContentLoaded": 0,
                "firstPaint": 0,
                "resourceCount": 0
            }

        return WebsiteFeatures(
            url=url,
            dom_structure=dom_structure,
            css_classes=css_classes,
            js_libraries=js_libraries,
            responsive_features=responsive_features,
            color_scheme=color_scheme,
            fonts=fonts,
            performance_metrics=performance_metrics,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _analyze_dom_structure(self, page: Page) -> dict:
        """分析DOM结构"""
        dom_structure = await page.evaluate('''() => {
            function getNodeStructure(node) {
                const result = {
                    tag: node.tagName?.toLowerCase(),
                    children: []
                };
                
                for (const child of node.children) {
                    result.children.push(getNodeStructure(child));
                }
                
                return result;
            }
            return getNodeStructure(document.body);
        }''')
        return dom_structure

    async def _extract_css_classes(self, page: Page) -> List[str]:
        """提取CSS类名"""
        classes = await page.evaluate('''() => {
            const classes = new Set();
            document.querySelectorAll('*').forEach(el => {
                el.classList.forEach(cls => classes.add(cls));
            });
            return Array.from(classes);
        }''')
        return classes

    async def _detect_js_libraries(self, page: Page) -> List[str]:
        """检测JavaScript库"""
        libraries = await page.evaluate('''() => {
            const libraries = [];
            if (window.jQuery) libraries.push('jQuery');
            if (window.React) libraries.push('React');
            if (window.Vue) libraries.push('Vue');
            if (window.Angular) libraries.push('Angular');
            return libraries;
        }''')
        return libraries

    async def _analyze_responsive_features(self, page: Page) -> dict:
        """分析响应式设计特征"""
        features = await page.evaluate('''() => {
            const meta = document.querySelector('meta[name="viewport"]');
            const mediaQueries = Array.from(document.styleSheets)
                .flatMap(sheet => {
                    try {
                        return Array.from(sheet.cssRules);
                    } catch {
                        return [];
                    }
                })
                .filter(rule => rule.type === CSSRule.MEDIA_RULE)
                .map(rule => rule.conditionText);
            
            return {
                viewport: meta?.content,
                mediaQueries: Array.from(new Set(mediaQueries))
            };
        }''')
        return features

    async def _extract_color_scheme(self, page: Page) -> List[str]:
        """提取颜色方案"""
        colors = await page.evaluate('''() => {
            const colors = new Set();
            const elements = document.querySelectorAll('*');
            elements.forEach(el => {
                const style = window.getComputedStyle(el);
                colors.add(style.color);
                colors.add(style.backgroundColor);
            });
            return Array.from(colors).filter(c => c !== 'rgba(0, 0, 0, 0)');
        }''')
        return colors

    async def _extract_fonts(self, page: Page) -> List[str]:
        """提取字体信息"""
        fonts = await page.evaluate('''() => {
            const fonts = new Set();
            document.querySelectorAll('*').forEach(el => {
                const fontFamily = window.getComputedStyle(el).fontFamily;
                fonts.add(fontFamily);
            });
            return Array.from(fonts);
        }''')
        return fonts

    async def _collect_performance_metrics(self, page: Page) -> dict:
        """收集性能指标"""
        metrics = await page.evaluate('''() => {
            const timing = window.performance.timing;
            const navigationStart = timing.navigationStart;
            
            return {
                loadTime: timing.loadEventEnd - navigationStart,
                domContentLoaded: timing.domContentLoadedEventEnd - navigationStart,
                firstPaint: timing.responseStart - navigationStart,
                resourceCount: performance.getEntriesByType('resource').length
            };
        }''')
        return metrics

    async def _collect_features(self, page: Page, url: str) -> WebsiteFeatures:
        """收集页面特征"""
        try:
            # 获取当前可用的DOM结构
            dom_structure = await self._analyze_dom_structure(page)
            
            # 获取可见的CSS类
            css_classes = await self._extract_css_classes(page)
            
            # 检测已加载的JS库
            js_libraries = await self._detect_js_libraries(page)
            
            # 获取响应式特征
            responsive_features = await self._analyze_responsive_features(page)
            
            # 获取颜色方案
            color_scheme = await self._extract_color_scheme(page)
            
            # 获取字体信息
            fonts = await self._extract_fonts(page)
            
            # 获取性能指标
            performance_metrics = await self._collect_performance_metrics(page)

            return WebsiteFeatures(
                url=url,
                dom_structure=dom_structure,
                css_classes=css_classes,
                js_libraries=js_libraries,
                responsive_features=responsive_features,
                color_scheme=color_scheme,
                fonts=fonts,
                performance_metrics=performance_metrics,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"收集特征时出错: {str(e)}")
            raise

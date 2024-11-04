from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
from playwright.async_api import async_playwright, Page
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
        # 转换datetime对象为字符串
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict())

class WebCollector:
    """网站数据收集器"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    async def analyze_url(self, url: str) -> Optional[WebsiteFeatures]:
        """分析网站URL并提取特征"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                # 设置超时
                page.set_default_timeout(self.timeout * 1000)
                
                # 访问页面
                await page.goto(url)
                
                # 收集特征
                features = await self._collect_features(page, url)
                
                await browser.close()
                return features
                
        except Exception as e:
            self.logger.error(f"分析URL时出错: {url}, 错误: {str(e)}")
            return None

    async def _collect_features(self, page: Page, url: str) -> WebsiteFeatures:
        """收集页面特征"""
        dom_structure = await self._analyze_dom_structure(page)
        css_classes = await self._extract_css_classes(page)
        js_libraries = await self._detect_js_libraries(page)
        responsive_features = await self._analyze_responsive_features(page)
        color_scheme = await self._extract_color_scheme(page)
        fonts = await self._extract_fonts(page)
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

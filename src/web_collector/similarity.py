from typing import Dict, List, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dataclasses import asdict
from .collector import WebsiteFeatures
import logging

class SimilarityAnalyzer:
    """网站相似度分析器"""
    
    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold
        self.logger = logging.getLogger(__name__)

    def calculate_similarity(self, site1: WebsiteFeatures, site2: WebsiteFeatures) -> float:
        """计算两个网站的总体相似度"""
        try:
            self.logger.info(f"\n开始比较网站相似度:")
            self.logger.info(f"网站1: {site1.url}")
            self.logger.info(f"网站2: {site2.url}")

            weights = {
                'dom_similarity': 0.5,
                'css_similarity': 0.3,
                'responsive_similarity': 0.1,
                'layout_similarity': 0.1
            }

            similarities = {
                'dom_similarity': self._calculate_dom_similarity(site1.dom_structure, site2.dom_structure),
                'css_similarity': self._calculate_css_similarity(site1.css_classes, site2.css_classes),
                'responsive_similarity': self._calculate_responsive_similarity(
                    site1.responsive_features, site2.responsive_features
                ),
                'layout_similarity': self._calculate_layout_similarity(
                    site1.dom_structure, site2.dom_structure
                )
            }

            # 打印各维度的相似度
            self.logger.info("\n各维度相似度:")
            for key, value in similarities.items():
                self.logger.info(f"{key}: {value:.2%} (权重: {weights[key]})")

            total_similarity = sum(
                similarities[key] * weights[key] for key in weights
            )

            self.logger.info(f"\n总体相似度: {total_similarity:.2%}")
            self.logger.info(f"相似度阈值: {self.threshold:.2%}")
            self.logger.info(f"判定结果: {'相似' if total_similarity >= self.threshold else '不相似'}\n")

            return total_similarity
            
        except Exception as e:
            self.logger.error(f"计算相似度时出错: {str(e)}")
            return 0.0

    def _calculate_dom_similarity(self, dom1: dict, dom2: dict) -> float:
        """计算DOM结构相似度，主要关注主要布局元素"""
        def get_layout_sequence(dom: dict) -> List[str]:
            important_tags = {'div', 'section', 'main', 'header', 'footer', 'nav', 'aside'}
            sequence = []
            
            def traverse(node, depth=0):
                if isinstance(node, dict) and 'tag' in node:
                    tag = node['tag']
                    if tag in important_tags:
                        sequence.append(f"{depth}:{tag}")
                    for child in node.get('children', []):
                        traverse(child, depth + 1)
            
            traverse(dom)
            return sequence

        seq1 = get_layout_sequence(dom1)
        seq2 = get_layout_sequence(dom2)

        self.logger.debug("\nDOM结构比较:")
        self.logger.debug(f"网站1 DOM序列: {seq1}")
        self.logger.debug(f"网站2 DOM序列: {seq2}")
        
        # 使用最长公共子序列算法
        matrix = np.zeros((len(seq1) + 1, len(seq2) + 1))
        for i in range(1, len(seq1) + 1):
            for j in range(1, len(seq2) + 1):
                if seq1[i-1] == seq2[j-1]:
                    matrix[i][j] = matrix[i-1][j-1] + 1
                else:
                    matrix[i][j] = max(matrix[i-1][j], matrix[i][j-1])

        lcs_length = matrix[-1][-1]
        similarity = 2 * lcs_length / (len(seq1) + len(seq2)) if (len(seq1) + len(seq2)) > 0 else 0
        
        self.logger.debug(f"最长公共子序列长度: {lcs_length}")
        self.logger.debug(f"DOM相似度: {similarity:.2%}")
        
        return similarity

    def _calculate_css_similarity(self, classes1: List[str], classes2: List[str]) -> float:
        """计算CSS类相似度，关注布局相关的类名"""
        def filter_layout_classes(classes: List[str]) -> set:
            layout_keywords = {'container', 'wrapper', 'header', 'footer', 'nav', 'sidebar', 
                             'main', 'content', 'grid', 'flex', 'row', 'col', 'section'}
            return {cls for cls in classes if any(keyword in cls.lower() for keyword in layout_keywords)}
        
        layout_classes1 = filter_layout_classes(classes1)
        layout_classes2 = filter_layout_classes(classes2)

        self.logger.debug("\nCSS类比较:")
        self.logger.debug(f"网站1布局相关类: {layout_classes1}")
        self.logger.debug(f"网站2布局相关类: {layout_classes2}")
        
        if not layout_classes1 or not layout_classes2:
            self.logger.debug("未找到布局相关的CSS类")
            return 0.0
        
        intersection = len(layout_classes1.intersection(layout_classes2))
        union = len(layout_classes1.union(layout_classes2))
        
        similarity = intersection / union if union > 0 else 0
        self.logger.debug(f"共同类数量: {intersection}")
        self.logger.debug(f"总类数量: {union}")
        self.logger.debug(f"CSS相似度: {similarity:.2%}")
        
        return similarity

    def _calculate_responsive_similarity(self, resp1: dict, resp2: dict) -> float:
        """计算响应式设计相似度，主要关注布局断点"""
        if not resp1 or not resp2:
            self.logger.debug("\n未找到响应式设计特征")
            return 0.0
            
        def extract_breakpoints(queries: List[str]) -> set:
            import re
            breakpoints = set()
            for query in queries:
                matches = re.findall(r'min-width:\s*(\d+)px', query)
                breakpoints.update(map(int, matches))
            return breakpoints
            
        breakpoints1 = extract_breakpoints(resp1.get('mediaQueries', []))
        breakpoints2 = extract_breakpoints(resp2.get('mediaQueries', []))

        self.logger.debug("\n响应式断点比较:")
        self.logger.debug(f"网站1断点: {breakpoints1}")
        self.logger.debug(f"网站2断点: {breakpoints2}")
        
        if not breakpoints1 or not breakpoints2:
            self.logger.debug("未找到媒体查询断点")
            return 0.0
            
        # 计算断点的相似度
        max_diff = 100  # 允许断点有100px的误差
        similar_breakpoints = 0
        for bp1 in breakpoints1:
            for bp2 in breakpoints2:
                if abs(bp1 - bp2) <= max_diff:
                    similar_breakpoints += 1
                    self.logger.debug(f"匹配断点: {bp1}px ≈ {bp2}px")
                    break
                    
        similarity = similar_breakpoints / max(len(breakpoints1), len(breakpoints2))
        self.logger.debug(f"响应式相似度: {similarity:.2%}")
        
        return similarity

    def _calculate_layout_similarity(self, dom1: dict, dom2: dict) -> float:
        """计算页面布局相似度"""
        def get_layout_structure(dom: dict) -> List[tuple]:
            structure = []
            
            def analyze_node(node, parent_type='root'):
                if isinstance(node, dict) and 'tag' in node:
                    tag = node['tag']
                    # 判断节点的布局类型
                    layout_type = self._determine_layout_type(node)
                    structure.append((parent_type, layout_type, len(node.get('children', []))))
                    for child in node.get('children', []):
                        analyze_node(child, layout_type)
            
            analyze_node(dom)
            return structure

        def compare_structures(struct1: List[tuple], struct2: List[tuple]) -> float:
            # 计算两个结构的相似度
            min_len = min(len(struct1), len(struct2))
            max_len = max(len(struct1), len(struct2))
            
            matches = 0
            for i in range(min_len):
                # 比较父类型、布局类型和子元素数量
                if (struct1[i][0] == struct2[i][0] and  # 相同的父类型
                    struct1[i][1] == struct2[i][1] and  # 相同的布局类型
                    abs(struct1[i][2] - struct2[i][2]) <= 2):  # 子元素数量相近
                    matches += 1
            
            return matches / max_len if max_len > 0 else 0

        layout1 = get_layout_structure(dom1)
        layout2 = get_layout_structure(dom2)
        return compare_structures(layout1, layout2)

    def _determine_layout_type(self, node: dict) -> str:
        """判断节点的布局类型"""
        tag = node.get('tag', '').lower()
        
        # 定义布局类型映射
        layout_tags = {
            'header': 'header',
            'footer': 'footer',
            'nav': 'navigation',
            'main': 'main-content',
            'aside': 'sidebar',
            'section': 'section',
            'article': 'article',
            'div': 'container'
        }
        
        return layout_tags.get(tag, 'other')

    def is_similar(self, site1: WebsiteFeatures, site2: WebsiteFeatures) -> bool:
        """判断两个网站是否相似"""
        similarity = self.calculate_similarity(site1, site2)
        return similarity >= self.threshold
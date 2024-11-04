from typing import Dict
import os
import yaml

class Config:
    """配置管理类"""
    
    def __init__(self, config_path: str = "config.yml"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'telegram': {
                'token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
                'admin_users': []
            },
            'database': {
                'path': 'website_templates.db'
            },
            'collector': {
                'timeout': 30,
                'max_retries': 3
            },
            'similarity': {
                'threshold': 0.85
            },
            'cleanup': {
                'days': 30
            }
        }

    def get(self, key: str, default=None):
        """获取配置值"""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default 
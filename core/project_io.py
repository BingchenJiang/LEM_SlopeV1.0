# -*- coding: utf-8 -*-
"""
工程文件序列化与数据存储模块
支持保存为 JSON / .lem 专有格式
"""
import json
from typing import Dict, Any, Optional


def save_project_file(filepath: str, project_data: Dict[str, Any]) -> bool:
    """保存工程配置文件"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_project_file(filepath: str) -> Optional[Dict[str, Any]]:
    """加载工程配置文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
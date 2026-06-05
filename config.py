"""
配置管理模块
管理API密钥、路径和其他配置项
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
TEXT_DIR = DATA_DIR / "texts"
DB_PATH = DATA_DIR / "papers.db"

# 创建必要的目录
DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
TEXT_DIR.mkdir(exist_ok=True)

# ============================================================
# LLM API 配置
# ============================================================

# 通用 LLM 配置（推荐 - 支持任何兼容 OpenAI API 格式的服务）
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

# OpenAI 配置（备选）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_OPENAI_MODEL = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4o-mini")

# Anthropic 配置（备选）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_ANTHROPIC_MODEL = os.getenv("DEFAULT_ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

# LLM 提供商选择：custom（推荐）, openai, anthropic
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "custom")

# ============================================================
# 业务配置
# ============================================================

# 相关性分析标签（可配置）
RELEVANCE_TAGS = [
    "3D avatar",
    "digital human",
    "human head reconstruction",
    "human face reconstruction",
    "facial avatar",
    "head avatar",
    "3D face",
    "3D head",
    "neural rendering",
    "Gaussian splatting",
    "NeRF",
    "monocular reconstruction",
    "personalized avatar",
    "feed-forward reconstruction",
    "optimization-based reconstruction",
    "Nersemble",
    "open-source code",
    "GPU requirements"
]

# 标题级快速预筛关键词，格式可以是 "keyword" 或 "keyword:weight"
# 当前 survey 只关注三组标题信号：
# 1. avatar
# 2. human head / human face / human body
# 3. 3D / 4D
TITLE_KEYWORDS = [
    "avatar:4",
    "facial avatar:4",
    "head avatar:4",
    "face avatar:4",
    "body avatar:4",
    "human avatar:4",
    "human head:4",
    "human face:4",
    "human body:4",
    "head:2",
    "face:2",
    "body:2",
    "3d:3",
    "4d:3",
    "three dimensional:3",
    "four dimensional:3"
]

# 会议和年份配置
CONFERENCES = {
    "ai": ["neurips", "iclr", "icml"],
    "robotics": ["corl", "rss", "icra", "iros"],
    "vision_graphics": ["cvpr", "iccv", "siggraph"],
    "digital_human_survey": ["cvpr", "iclr", "iccv", "siggraph"]
}

# Google Programmable Search JSON API 配置（用于 search-assisted 标题抓取）
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 请求配置
REQUEST_TIMEOUT = 30  # 秒
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 1  # 秒

# PDF处理配置
MAX_PDF_SIZE_MB = 50  # 最大PDF大小（MB）
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"

# ============================================================
# 辅助函数
# ============================================================

def get_api_key(provider: str = None) -> str:
    """
    获取指定提供商的API密钥
    
    Args:
        provider: 提供商名称，None表示使用默认提供商
        
    Returns:
        API密钥字符串
    """
    if provider is None:
        provider = DEFAULT_LLM_PROVIDER
    
    if provider == "custom":
        return LLM_API_KEY
    elif provider == "openai":
        return OPENAI_API_KEY
    elif provider == "anthropic":
        return ANTHROPIC_API_KEY
    else:
        # 未知提供商，尝试返回通用配置
        return LLM_API_KEY


def get_model_name(provider: str = None) -> str:
    """
    获取指定提供商的模型名称
    
    Args:
        provider: 提供商名称，None表示使用默认提供商
        
    Returns:
        模型名称字符串
    """
    if provider is None:
        provider = DEFAULT_LLM_PROVIDER
    
    if provider == "custom":
        return LLM_MODEL
    elif provider == "openai":
        return DEFAULT_OPENAI_MODEL
    elif provider == "anthropic":
        return DEFAULT_ANTHROPIC_MODEL
    else:
        # 未知提供商，尝试返回通用配置
        return LLM_MODEL


def get_base_url(provider: str = None) -> str:
    """
    获取指定提供商的API基础URL
    
    Args:
        provider: 提供商名称，None表示使用默认提供商
        
    Returns:
        API基础URL字符串
    """
    if provider is None:
        provider = DEFAULT_LLM_PROVIDER
    
    if provider == "custom":
        return LLM_BASE_URL
    elif provider == "openai":
        return OPENAI_BASE_URL
    elif provider == "anthropic":
        # Anthropic使用官方SDK，不需要base_url
        # 但为了兼容性，这里返回空字符串
        return ""
    else:
        # 未知提供商，尝试返回通用配置
        return LLM_BASE_URL

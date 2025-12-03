"""
ICML论文收集器
使用 DBLP API 获取 ICML 论文标题
"""

import logging
from typing import List, Dict

from .dblp import (
    build_dblp_conf_page_url,
    fetch_dblp_papers,
    fetch_dblp_papers_from_html,
)

logger = logging.getLogger(__name__)


def collect_icml_papers(year: int = 2024) -> List[Dict[str, str]]:
    """
    收集ICML论文标题

    Args:
        year: 会议年份

    Returns:
        论文列表，每个元素包含 {title, url, source}
    """
    source = f"ICML{year}"
    logger.info("Collecting ICML %s papers via DBLP API", year)
    papers = fetch_dblp_papers("conf/icml", year, source)

    if papers:
        return papers

    fallback_url = build_dblp_conf_page_url("icml", year)
    logger.info("Falling back to DBLP HTML page %s", fallback_url)
    return fetch_dblp_papers_from_html(fallback_url, source)


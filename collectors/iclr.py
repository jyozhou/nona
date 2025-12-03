"""
ICLR论文收集器
使用 DBLP API 获取 ICLR 论文标题
"""

import logging
from typing import List, Dict

from .dblp import (
    build_dblp_conf_page_url,
    fetch_dblp_papers,
    fetch_dblp_papers_from_html,
)

logger = logging.getLogger(__name__)


def collect_iclr_papers(year: int = 2025) -> List[Dict[str, str]]:
    """
    收集ICLR论文标题

    Args:
        year: 会议年份

    Returns:
        论文列表，每个元素包含 {title, url, source}
    """
    source = f"ICLR{year}"
    logger.info("Collecting ICLR %s papers via DBLP API", year)
    papers = fetch_dblp_papers("conf/iclr", year, source)

    if papers:
        return papers

    fallback_url = build_dblp_conf_page_url("iclr", year)
    logger.info("Falling back to DBLP HTML page %s", fallback_url)
    return fetch_dblp_papers_from_html(fallback_url, source)


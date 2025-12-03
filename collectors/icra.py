"""
ICRA论文收集器
使用 DBLP API 获取 ICRA 论文标题
"""

import logging
from typing import List, Dict

from .dblp import (
    build_dblp_conf_page_url,
    fetch_dblp_papers,
    fetch_dblp_papers_from_html,
)

logger = logging.getLogger(__name__)


def collect_icra_papers(year: int = 2024) -> List[Dict[str, str]]:
    """
    收集ICRA论文标题

    Args:
        year: 会议年份

    Returns:
        论文列表，每个元素包含 {title, url, source}
    """
    source = f"ICRA{year}"
    logger.info("Collecting ICRA %s papers via DBLP API", year)
    papers = fetch_dblp_papers("conf/icra", year, source)

    if papers:
        return papers

    fallback_url = build_dblp_conf_page_url("icra", year)
    logger.info("Falling back to DBLP HTML page %s", fallback_url)
    return fetch_dblp_papers_from_html(fallback_url, source)


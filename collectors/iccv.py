"""
ICCV paper collector.
"""

import logging
from typing import Dict, List

from .cvf import collect_cvf_openaccess_papers
from .dblp import (
    build_dblp_conf_page_url,
    fetch_dblp_papers,
    fetch_dblp_papers_from_html,
)

logger = logging.getLogger(__name__)


def collect_iccv_papers(year: int = 2025) -> List[Dict[str, str]]:
    """
    Collect ICCV paper titles from CVF Open Access, with DBLP fallback.
    """
    source = f"ICCV{year}"
    papers = collect_cvf_openaccess_papers("ICCV", year)
    if papers:
        return papers

    logger.info("Falling back to DBLP API for ICCV %s", year)
    papers = fetch_dblp_papers("conf/iccv", year, source)
    if papers:
        return papers

    fallback_url = build_dblp_conf_page_url("iccv", year)
    logger.info("Falling back to DBLP HTML page %s", fallback_url)
    return fetch_dblp_papers_from_html(fallback_url, source)

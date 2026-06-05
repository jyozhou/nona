"""
CVPR paper collector.
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


def collect_cvpr_papers(year: int = 2025) -> List[Dict[str, str]]:
    """
    Collect CVPR paper titles from CVF Open Access, with DBLP fallback.
    """
    source = f"CVPR{year}"
    papers = collect_cvf_openaccess_papers("CVPR", year)
    if papers:
        return papers

    logger.info("Falling back to DBLP API for CVPR %s", year)
    papers = fetch_dblp_papers("conf/cvpr", year, source)
    if papers:
        return papers

    fallback_url = build_dblp_conf_page_url("cvpr", year)
    logger.info("Falling back to DBLP HTML page %s", fallback_url)
    return fetch_dblp_papers_from_html(fallback_url, source)

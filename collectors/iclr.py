"""
ICLR论文收集器
使用 DBLP API / OpenReview API 获取 ICLR 论文标题
"""

import logging
from typing import List, Dict

import requests

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

    logger.info("Falling back to OpenReview API for ICLR %s", year)
    papers = _collect_iclr_openreview_papers(year, source)
    if papers:
        return papers

    fallback_url = build_dblp_conf_page_url("iclr", year)
    logger.info("Falling back to DBLP HTML page %s", fallback_url)
    return fetch_dblp_papers_from_html(fallback_url, source)


def _collect_iclr_openreview_papers(year: int, source: str) -> List[Dict[str, str]]:
    """
    从 OpenReview 获取 ICLR 已接收论文标题。

    OpenReview 的 accepted/published submissions 可通过 content.venueid 过滤。
    """
    venue_id = f"ICLR.cc/{year}/Conference"
    base_url = "https://api2.openreview.net/notes"
    papers: List[Dict[str, str]] = []
    page_size = 1000
    offset = 0

    while True:
        params = {
            "content.venueid": venue_id,
            "limit": page_size,
            "offset": offset,
        }

        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to fetch OpenReview data for %s: %s", venue_id, exc)
            break

        notes = response.json().get("notes", [])
        if not notes:
            break

        for note in notes:
            title = _extract_openreview_value(note.get("content", {}).get("title"))
            if not title:
                continue

            papers.append(
                {
                    "title": " ".join(title.split()),
                    "url": f"https://openreview.net/forum?id={note.get('id', '')}",
                    "source": source,
                }
            )

        if len(notes) < page_size:
            break
        offset += page_size

    papers = _deduplicate_papers(papers)
    logger.info("Collected %d ICLR %s papers from OpenReview", len(papers), year)
    return papers


def _extract_openreview_value(field) -> str:
    if isinstance(field, dict):
        return str(field.get("value", "")).strip()
    if isinstance(field, str):
        return field.strip()
    return ""


def _deduplicate_papers(papers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    unique: List[Dict[str, str]] = []

    for paper in papers:
        key = paper["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)

    return unique


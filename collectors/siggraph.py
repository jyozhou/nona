"""
SIGGRAPH paper collector.
"""

import logging
import re
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .dblp import (
    build_dblp_conf_page_url,
    fetch_dblp_papers,
    fetch_dblp_papers_from_html,
)

logger = logging.getLogger(__name__)


def collect_siggraph_papers(year: int = 2025) -> List[Dict[str, str]]:
    """
    Collect SIGGRAPH technical paper titles via DBLP.

    DBLP is the most stable public title source here because SIGGRAPH papers are
    split across ACM TOG journal and conference proceedings pages.
    """
    source = f"SIGGRAPH{year}"
    logger.info("Collecting SIGGRAPH %s papers via DBLP API", year)
    papers = fetch_dblp_papers("conf/siggraph", year, source)

    if papers:
        return papers

    papers = _collect_siggraph_schedule_papers(year, source)
    if papers:
        return papers

    fallback_url = build_dblp_conf_page_url("siggraph", year)
    logger.info("Falling back to DBLP HTML page %s", fallback_url)
    papers = fetch_dblp_papers_from_html(fallback_url, source)
    if papers:
        return papers

    return _collect_siggraph_program_highlights(year, source)


def _collect_siggraph_schedule_papers(year: int, source: str) -> List[Dict[str, str]]:
    url = f"https://s{year}.conference-schedule.org/contributors/"
    logger.info("Falling back to SIGGRAPH schedule page %s", url)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to fetch SIGGRAPH schedule page %s: %s", url, exc)
        return []

    html = response.text
    papers: List[Dict[str, str]] = []

    pattern = re.compile(
        r"(?:Art Paper|Technical Paper)\s*(?:.{0,400}?)<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        title_html = match.group(2)
        title = BeautifulSoup(title_html, "html.parser").get_text(" ", strip=True)
        title = _clean_title(title)
        if not _looks_like_paper_title(title):
            continue
        papers.append(
            {
                "title": title,
                "url": urljoin(url, match.group(1)),
                "source": source,
            }
        )

    papers = _deduplicate(papers)
    logger.info("Collected %d SIGGRAPH papers from schedule page", len(papers))
    return papers


def _collect_siggraph_program_highlights(year: int, source: str) -> List[Dict[str, str]]:
    url = f"https://s{year}.siggraph.org/program/technical-papers/"
    logger.info("Falling back to SIGGRAPH technical papers page %s", url)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to fetch SIGGRAPH technical papers page %s: %s", url, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    papers: List[Dict[str, str]] = []

    for item in soup.find_all("li"):
        title = _clean_title(item.get_text(" ", strip=True))
        if _looks_like_paper_title(title):
            papers.append({"title": title, "url": url, "source": source})

    return _deduplicate(papers)


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "")
    return title.strip()


def _looks_like_paper_title(title: str) -> bool:
    if len(title) < 12 or len(title) > 220:
        return False

    lowered = title.lower()
    blocked_terms = {
        "technical paper",
        "art paper",
        "session",
        "workshop",
        "presentation",
        "committee",
        "united states",
        "china",
        "canada",
        "japan",
        "germany",
        "university",
        "institute",
        "labs",
        "research",
        "corporation",
    }
    if lowered in blocked_terms or any(lowered.startswith(term + " ") for term in blocked_terms):
        return False

    return len(title.split()) >= 3 and bool(re.search(r"[A-Za-z]", title))


def _deduplicate(papers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    unique: List[Dict[str, str]] = []

    for paper in papers:
        key = paper["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)

    return unique

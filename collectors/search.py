"""
Search-assisted paper title collection.

This module uses Google Programmable Search JSON API when GOOGLE_SEARCH_API_KEY
and GOOGLE_SEARCH_ENGINE_ID are configured. It is meant to discover a paper-list
page for queries such as "cvpr 2025 paper list", then parse titles from the
result pages and apply local keyword scoring.
"""

import logging
import re
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .title_filter import filter_papers_by_keywords

logger = logging.getLogger(__name__)


def collect_google_paper_titles(
    query: str,
    year: int,
    keywords: Optional[Iterable[str]] = None,
    max_results: int = 50,
    min_keyword_score: float = 1.0,
) -> List[Dict[str, str]]:
    """
    Collect candidate paper titles through Google Programmable Search.

    Args:
        query: Search query, e.g. "cvpr 2025 paper list".
        year: Year used for source labels and known official page shortcuts.
        keywords: Optional title keywords for ranking/filtering.
        max_results: Max search results/pages to inspect.
        min_keyword_score: Minimum keyword score when keywords are provided.
    """
    if not query:
        query = f"cvpr {year} paper list"

    papers: List[Dict[str, str]] = []

    shortcut_papers = _collect_known_official_page(query, year)
    papers.extend(shortcut_papers)

    search_items = _google_search(query, max_results=max_results)
    for item in search_items:
        url = item.get("link", "")
        if not url:
            continue

        page_papers = _collect_from_search_result_page(url, year)
        if page_papers:
            papers.extend(page_papers)
            continue

        title = _clean_search_result_title(item.get("title", ""))
        if title:
            papers.append(
                {
                    "title": title,
                    "url": url,
                    "source": f"GoogleSearch{year}",
                }
            )

    papers = _deduplicate(papers)
    if keywords:
        return filter_papers_by_keywords(papers, keywords, min_score=min_keyword_score)
    return papers


def _collect_known_official_page(query: str, year: int) -> List[Dict[str, str]]:
    normalized_query = query.lower()

    if "cvpr" in normalized_query:
        from .cvpr import collect_cvpr_papers

        return collect_cvpr_papers(year)
    if "iccv" in normalized_query:
        from .iccv import collect_iccv_papers

        return collect_iccv_papers(year)
    if "siggraph" in normalized_query:
        from .siggraph import collect_siggraph_papers

        return collect_siggraph_papers(year)
    if "iclr" in normalized_query:
        from .iclr import collect_iclr_papers

        return collect_iclr_papers(year)
    return []


def _google_search(query: str, max_results: int) -> List[Dict[str, str]]:
    try:
        from config import GOOGLE_SEARCH_API_KEY, GOOGLE_SEARCH_ENGINE_ID
    except Exception:
        GOOGLE_SEARCH_API_KEY = ""
        GOOGLE_SEARCH_ENGINE_ID = ""

    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        logger.warning(
            "Google search is not configured. Set GOOGLE_SEARCH_API_KEY and "
            "GOOGLE_SEARCH_ENGINE_ID in .env to enable search-assisted collection."
        )
        return []

    max_results = max(1, min(max_results, 100))
    items: List[Dict[str, str]] = []
    start = 1
    page_size = 10

    while len(items) < max_results:
        params = {
            "key": GOOGLE_SEARCH_API_KEY,
            "cx": GOOGLE_SEARCH_ENGINE_ID,
            "q": query,
            "num": min(page_size, max_results - len(items)),
            "start": start,
        }
        try:
            response = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error("Google search request failed: %s", exc)
            break

        data = response.json()
        page_items = data.get("items", [])
        if not page_items:
            break

        items.extend(page_items)
        start += len(page_items)
        if len(page_items) < page_size:
            break

    logger.info("Google search returned %d result items for query %r", len(items), query)
    return items


def _collect_from_search_result_page(url: str, year: int) -> List[Dict[str, str]]:
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    if "openaccess.thecvf.com" in hostname:
        match = re.search(r"/(CVPR|ICCV)(\d{4})", parsed.path + "?" + parsed.query, re.I)
        if match:
            return collect_cvf_openaccess_papers(match.group(1).upper(), int(match.group(2)))

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    candidates: List[Dict[str, str]] = []

    selectors = [
        "dt.ptitle a",
        "h2 a",
        "h3 a",
        "article a",
        "li a",
    ]
    for selector in selectors:
        for link in soup.select(selector):
            title = _clean_candidate_title(link.get_text(" ", strip=True))
            if _looks_like_paper_title(title):
                candidates.append(
                    {
                        "title": title,
                        "url": urljoin(url, link.get("href", "")),
                        "source": f"SearchPage{year}",
                    }
                )

        if len(candidates) >= 20:
            break

    return _deduplicate(candidates)


def _clean_search_result_title(title: str) -> str:
    title = re.sub(r"\s*[-|]\s*(Google Scholar|CVF|Open Access|Paper Copilot).*$", "", title)
    return _clean_candidate_title(title)


def _clean_candidate_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "")
    title = re.sub(r"^\d+\s*[.)-]\s*", "", title)
    return title.strip()


def _looks_like_paper_title(title: str) -> bool:
    if len(title) < 12 or len(title) > 220:
        return False
    lowered = title.lower()
    noisy_terms = {
        "accepted paper list",
        "all papers",
        "open access",
        "supplementary material",
        "homepage",
        "github",
        "download",
    }
    if any(term in lowered for term in noisy_terms):
        return False
    return bool(re.search(r"[A-Za-z]", title))


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

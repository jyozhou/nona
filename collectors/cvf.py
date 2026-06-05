"""
CVF open access helpers for CVPR/ICCV paper title collection.
"""

import logging
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def collect_cvf_openaccess_papers(conference: str, year: int) -> List[Dict[str, str]]:
    """
    Collect paper titles from the CVF Open Access repository.

    Args:
        conference: CVF conference slug, e.g. "CVPR" or "ICCV".
        year: Conference year.

    Returns:
        Paper list with {title, url, source}.
    """
    conf = conference.upper()
    source = f"{conf}{year}"
    index_url = f"https://openaccess.thecvf.com/{conf}{year}"
    day_urls = _discover_day_urls(index_url)
    urls = [index_url]
    urls.extend(day_urls)
    if not day_urls:
        urls.extend(
            [
                f"https://openaccess.thecvf.com/{conf}{year}?day=all",
                f"https://openaccess.thecvf.com/{conf}{year}?all=1",
            ]
        )

    all_papers: List[Dict[str, str]] = []
    seen_urls = set()
    for url in urls:
        if url in seen_urls:
            continue
        seen_urls.add(url)

        logger.info("Collecting %s papers from %s", source, url)
        papers = _fetch_cvf_page(url, source)
        logger.info("Collected %d papers from %s", len(papers), url)
        all_papers.extend(papers)

    all_papers = _deduplicate(all_papers)
    if not all_papers:
        logger.warning("No papers collected from CVF Open Access for %s", source)
    return all_papers


def _discover_day_urls(index_url: str) -> List[str]:
    try:
        response = requests.get(index_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to discover CVF day pages from %s: %s", index_url, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    day_urls: List[str] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(" ", strip=True).lower()
        if "day=" not in href:
            continue
        if "all" in href.lower() or "all papers" in text:
            continue
        day_urls.append(urljoin(index_url, href))

    return day_urls


def _fetch_cvf_page(url: str, source: str) -> List[Dict[str, str]]:
    papers: List[Dict[str, str]] = []

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to fetch CVF page %s: %s", url, exc)
        return papers

    soup = BeautifulSoup(response.text, "html.parser")

    # CVF pages commonly use <dt class="ptitle"><a>Title</a></dt>.
    title_links = soup.select("dt.ptitle a")
    if not title_links:
        title_links = [
            link
            for link in soup.find_all("a", href=True)
            if "/html/" in link["href"] or "_paper.html" in link["href"]
        ]

    for link in title_links:
        title = " ".join(link.get_text(" ", strip=True).split())
        if not title or len(title) < 8:
            continue

        papers.append(
            {
                "title": title,
                "url": urljoin(url, link.get("href", "")),
                "source": source,
            }
        )

    return _deduplicate(papers)


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

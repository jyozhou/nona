"""
DBLP 辅助工具
提供从 DBLP API 获取会议论文标题的通用方法
"""

import logging
import re
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def fetch_dblp_papers(
    venue_key: str,
    year: int,
    source_label: str,
    max_rows: int = 5000,
) -> List[Dict[str, str]]:
    """
    从 DBLP API 获取指定会议的论文列表

    Args:
        venue_key: DBLP venue key，例如 'conf/iclr'
        year: 年份
        source_label: 存入数据库的 source 字段
        max_rows: 最多拉取的条数

    Returns:
        论文列表，每项包含 {title, url, source}
    """

    base_url = "https://dblp.org/search/publ/api"
    papers: List[Dict[str, str]] = []
    offset = 0
    page_size = 1000

    try:
        while offset < max_rows:
            params = {
                "q": f"toc:{venue_key}/{year}",
                "format": "json",
                "h": min(page_size, max_rows - offset),
                "f": offset,
            }

            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            hits = data.get("result", {}).get("hits", {})
            total = int(hits.get("@total", 0))
            entries = hits.get("hit", [])

            if not entries:
                break

            if isinstance(entries, dict):
                entries = [entries]

            for entry in entries:
                info = entry.get("info", {})
                raw_title = info.get("title", "")
                title = _clean_dblp_title(raw_title)

                if not title:
                    continue

                url = info.get("ee") or info.get("url") or ""
                papers.append(
                    {
                        "title": title,
                        "url": url,
                        "source": source_label,
                    }
                )

            offset += page_size

            if offset >= total:
                break

        if not papers:
            logger.warning(
                "DBLP returned no entries for %s %s. Check if proceedings are published.",
                venue_key,
                year,
            )

        logger.info("Collected %d papers from DBLP for %s %s", len(papers), venue_key, year)
        return _deduplicate(papers)

    except requests.exceptions.RequestException as exc:
        logger.error("Failed to fetch DBLP data for %s %s: %s", venue_key, year, exc)
        return papers
    except Exception as exc:  # pragma: no cover - 防御性
        logger.error("Unexpected error when fetching DBLP data: %s", exc)
        return papers


def build_dblp_conf_page_url(conf_slug: str, year: int) -> str:
    """构造 DBLP 会议 HTML 页面 URL，例如 iclr -> https://dblp.org/db/conf/iclr/iclr2025.html"""
    return f"https://dblp.org/db/conf/{conf_slug}/{conf_slug}{year}.html"


def fetch_dblp_papers_from_html(html_url: str, source_label: str) -> List[Dict[str, str]]:
    """
    直接解析 DBLP 会议 HTML 页面获取论文标题，适用于 API 尚未提供数据的场景
    """

    papers: List[Dict[str, str]] = []

    try:
        response = requests.get(html_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to fetch DBLP HTML page %s: %s", html_url, exc)
        return papers

    soup = BeautifulSoup(response.text, "lxml")

    entries = soup.find_all(
        "li", class_=lambda value: value and "entry" in value
    ) or soup.select("li")

    for entry in entries:
        title_tag = entry.find(class_="title")
        if not title_tag:
            continue

        title = _clean_dblp_title(title_tag.get_text(" ", strip=True))
        if not title:
            continue

        url = ""
        link_tag = entry.select_one("li.ee a[href]") or entry.find("a", href=True)
        if link_tag and link_tag.get("href") and not link_tag["href"].startswith("#"):
            url = link_tag["href"]

        papers.append(
            {
                "title": title,
                "url": url,
                "source": source_label,
            }
        )

    if not papers:
        logger.warning("No papers parsed from DBLP HTML page %s", html_url)
        return papers

    logger.info("Collected %d papers from DBLP HTML page %s", len(papers), html_url)
    return _deduplicate(papers)


def _clean_dblp_title(title: str) -> str:
    """去除 DBLP 返回标题中的 HTML 标签和多余空白"""
    if not title:
        return ""

    # DBLP title 可能包含 HTML 标签，例如 <span class="title">...</span>
    title = re.sub(r"<[^>]+>", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def _deduplicate(papers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """按标题去重"""
    seen = set()
    unique: List[Dict[str, str]] = []

    for paper in papers:
        normalized = paper["title"].lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(paper)

    return unique


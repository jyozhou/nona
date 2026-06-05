"""
Title-level keyword scoring for fast survey candidate screening.
"""

import re
from typing import Dict, Iterable, List, Sequence


def filter_papers_by_keywords(
    papers: Sequence[Dict[str, str]],
    keywords: Iterable[str],
    min_score: float = 1.0,
) -> List[Dict[str, str]]:
    """
    Keep papers whose title matches the keyword profile.

    The score is the sum of matched keyword weights. A keyword can be written as
    "term" or "term:weight"; phrase matching is case-insensitive.
    """
    parsed_keywords = _parse_keywords(keywords)
    if not parsed_keywords:
        return list(papers)

    ranked: List[Dict[str, str]] = []
    for paper in papers:
        score, matched = score_title(paper.get("title", ""), parsed_keywords)
        if score < min_score:
            continue

        enriched = dict(paper)
        enriched["keyword_score"] = f"{score:.2f}"
        enriched["matched_keywords"] = ", ".join(matched)
        ranked.append(enriched)

    ranked.sort(key=lambda item: float(item.get("keyword_score", 0.0)), reverse=True)
    return ranked


def score_title(title: str, keywords: Sequence[tuple[str, float]]) -> tuple[float, List[str]]:
    normalized_title = _normalize(title)
    score = 0.0
    matched: List[str] = []

    for keyword, weight in keywords:
        normalized_keyword = _normalize(keyword)
        if not normalized_keyword:
            continue
        if _contains_term(normalized_title, normalized_keyword):
            score += weight
            matched.append(keyword)

    return score, matched


def _parse_keywords(keywords: Iterable[str]) -> List[tuple[str, float]]:
    parsed: List[tuple[str, float]] = []

    for raw_keyword in keywords:
        raw_keyword = raw_keyword.strip()
        if not raw_keyword:
            continue

        term = raw_keyword
        weight = 1.0
        if ":" in raw_keyword:
            maybe_term, maybe_weight = raw_keyword.rsplit(":", 1)
            try:
                term = maybe_term.strip()
                weight = float(maybe_weight)
            except ValueError:
                term = raw_keyword
                weight = 1.0

        if term:
            parsed.append((term, weight))

    return parsed


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _contains_term(normalized_title: str, normalized_keyword: str) -> bool:
    if " " in normalized_keyword:
        return normalized_keyword in normalized_title
    return re.search(rf"\b{re.escape(normalized_keyword)}\b", normalized_title) is not None

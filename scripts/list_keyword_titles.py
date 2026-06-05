"""
Print keyword-matched ICLR 2026 paper titles for the digital human survey.

This script is intentionally scoped to the previously missing target: ICLR 2026.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import LOG_FORMAT, LOG_LEVEL, TITLE_KEYWORDS
from collectors.iclr import collect_iclr_papers
from collectors.title_filter import filter_papers_by_keywords

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

Collector = Callable[[int], List[Dict[str, str]]]

DEFAULT_TARGETS: List[Tuple[str, int, Collector]] = [
    ("ICLR", 2025, collect_iclr_papers),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List paper titles matched by avatar/head-face-body/3D keywords."
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=4.0,
        help="Minimum keyword score for title filtering. Default: 4.0",
    )
    parser.add_argument(
        "--show-keywords",
        action="store_true",
        help="Print matched keywords for each title.",
    )
    args = parser.parse_args()

    for name, year, collector in DEFAULT_TARGETS:
        print("\n" + "=" * 80)
        print(f"{name} {year} relevant titles")
        print("=" * 80)

        try:
            papers = collector(year)
        except Exception as exc:
            logger.error("Failed to collect %s %s papers: %s", name, year, exc)
            continue

        hits = filter_papers_by_keywords(papers, TITLE_KEYWORDS, args.min_score)
        print(f"collected: {len(papers)}, matched: {len(hits)}\n")

        for index, paper in enumerate(hits, 1):
            score = paper.get("keyword_score", "")
            print(f"{index}. [{score}] {paper['title']}")
            if args.show_keywords:
                print(f"   matched: {paper.get('matched_keywords', '')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
导入手动下载的失败论文 PDF。

把 PDF 放到 data/fixpdfs 后运行本脚本。脚本会自动匹配数据库中：
- 获取详情失败的条目 detail_failures / status=detailFailed
- 下载失败的条目 download_failures / status=downloadFailed

匹配成功后：
1. 复制 PDF 到 data/pdfs/{paper_id}.pdf
2. 转换文本到 data/texts/{paper_id}.txt
3. 将数据库状态更新为 processed
4. 清理对应 failure 记录
"""

import argparse
import logging
import re
import shutil
import sqlite3
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, LOG_FORMAT, LOG_LEVEL, PDF_DIR, PROJECT_ROOT, TEXT_DIR
from database import Database
from processors import convert_pdf_to_text

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="导入手动下载的失败论文 PDF")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "fixpdfs",
        help="手动下载 PDF 所在目录，默认 data/fixpdfs",
    )
    parser.add_argument(
        "--min-match",
        type=float,
        default=0.45,
        help="标题与 PDF 文件名的最低模糊匹配分数，默认 0.45",
    )
    parser.add_argument("--limit", type=int, default=None, help="最多尝试导入多少条失败论文")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示匹配关系，不复制、不转换、不改数据库",
    )
    parser.add_argument(
        "--allow-supplemental",
        action="store_true",
        help="允许把文件名包含 supplemental/supp 的 PDF 当作主论文导入，不推荐",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="如果目标 PDF/TXT 已存在，允许覆盖",
    )
    args = parser.parse_args()

    if not args.source_dir.exists():
        logger.error("PDF目录不存在: %s", args.source_dir)
        return 1

    pdf_files = sorted(args.source_dir.glob("*.pdf"))
    if not pdf_files:
        logger.error("目录中没有 PDF 文件: %s", args.source_dir)
        return 1

    db = Database(str(DB_PATH))
    candidates = _load_failed_candidates(db)
    if args.limit:
        candidates = candidates[: args.limit]

    if not candidates:
        logger.info("没有 detailFailed/downloadFailed 或 failure 表中的失败条目")
        return 0

    logger.info("候选失败论文: %d 条", len(candidates))
    logger.info("手动 PDF: %d 个", len(pdf_files))

    used_files = set()
    success_count = 0
    matched_count = 0

    for paper in candidates:
        title = paper.get("title", "")
        match = _find_best_pdf(title, pdf_files, used_files, args.allow_supplemental)
        if not match:
            logger.warning("未找到匹配 PDF: %s", title)
            continue

        pdf_file, score = match
        if score < args.min_match:
            logger.warning(
                "PDF匹配分数过低，跳过: %s -> %s (score=%.3f)",
                title,
                pdf_file.name,
                score,
            )
            continue

        matched_count += 1
        used_files.add(pdf_file)

        if _import_one_pdf(db, paper, pdf_file, score, args.dry_run, args.overwrite):
            success_count += 1

    logger.info("完成：匹配 %d 条，成功导入 %d 条", matched_count, success_count)
    return 0


def _load_failed_candidates(db: Database) -> List[Dict]:
    papers_by_id = _load_papers_by_id()
    candidates: Dict[str, Dict] = {}

    for failure in db.get_detail_failures():
        paper = _paper_from_failure(failure, papers_by_id, "detail_failure")
        candidates[paper["id"]] = paper

    for failure in db.get_download_failures():
        paper = _paper_from_failure(failure, papers_by_id, "download_failure")
        candidates[paper["id"]] = paper

    for status in ("detailFailed", "downloadFailed"):
        for paper in _load_papers_by_status(status):
            paper["failure_type"] = status
            candidates[paper["id"]] = paper

    return list(candidates.values())


def _paper_from_failure(failure: Dict, papers_by_id: Dict[str, Dict], failure_type: str) -> Dict:
    paper_id = failure.get("paper_id")
    paper = dict(papers_by_id.get(paper_id, {}))

    if not paper:
        paper = {
            "id": paper_id,
            "title": failure.get("title", ""),
            "source": failure.get("source", ""),
            "arxiv_id": failure.get("arxiv_id"),
        }

    paper["failure_type"] = failure_type
    if failure.get("title"):
        paper["title"] = failure["title"]
    if failure.get("source"):
        paper["source"] = failure["source"]
    return paper


def _load_papers_by_id() -> Dict[str, Dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM papers").fetchall()
        return {row["id"]: dict(row) for row in rows}


def _load_papers_by_status(status: str) -> List[Dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM papers WHERE status = ?", (status,)).fetchall()
        return [dict(row) for row in rows]


def _import_one_pdf(
    db: Database,
    paper: Dict,
    pdf_file: Path,
    score: float,
    dry_run: bool,
    overwrite: bool,
) -> bool:
    paper_id = paper.get("id")
    title = paper.get("title", "")
    if not paper_id:
        logger.warning("跳过缺少 paper_id 的条目: %s", title)
        return False

    file_id = paper.get("arxiv_id") or paper_id
    target_pdf = PDF_DIR / f"{file_id}.pdf"
    target_text = TEXT_DIR / f"{file_id}.txt"

    logger.info("匹配: [%s] %s", paper.get("source") or "unknown", title)
    logger.info("  failure_type: %s", paper.get("failure_type"))
    logger.info("  PDF: %s (score=%.3f)", pdf_file.name, score)
    logger.info("  -> %s", target_pdf)

    if dry_run:
        return False

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    if target_pdf.exists() and not overwrite:
        logger.info("目标 PDF 已存在，保留原文件: %s", target_pdf)
    else:
        shutil.copy2(pdf_file, target_pdf)

    if target_text.exists() and overwrite:
        target_text.unlink()

    if not convert_pdf_to_text(target_pdf, target_text):
        logger.warning("文本转换失败，状态不更新为 processed: %s", title)
        return False

    db.update_paper_info(
        paper_id,
        {
            "pdf_url": f"manual:{pdf_file.as_posix()}",
            "status": "processed",
        },
    )
    db.remove_detail_failure(paper_id)
    db.remove_download_failure(paper_id)
    logger.info("✓ 已导入并标记为 processed: %s", title)
    return True


def _find_best_pdf(
    title: str,
    pdf_files: Iterable[Path],
    used_files: set,
    allow_supplemental: bool,
) -> Optional[Tuple[Path, float]]:
    normalized_title = _normalize(title)
    best_file: Optional[Path] = None
    best_score = 0.0

    for pdf_file in pdf_files:
        if pdf_file in used_files:
            continue
        if not allow_supplemental and _looks_like_supplemental(pdf_file):
            continue

        score = _title_filename_score(normalized_title, _normalize(pdf_file.stem))
        if score > best_score:
            best_score = score
            best_file = pdf_file

    if best_file is None:
        return None
    return best_file, best_score


def _title_filename_score(normalized_title: str, normalized_filename: str) -> float:
    ratio = SequenceMatcher(None, normalized_title, normalized_filename).ratio()
    title_tokens = set(normalized_title.split())
    filename_tokens = set(normalized_filename.split())
    if not title_tokens:
        return ratio

    overlap = len(title_tokens & filename_tokens) / len(title_tokens)
    return max(ratio, overlap)


def _looks_like_supplemental(pdf_file: Path) -> bool:
    stem = pdf_file.stem.lower()
    return "supplemental" in stem or re.search(r"\bsupp\b", stem) is not None


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


if __name__ == "__main__":
    raise SystemExit(main())

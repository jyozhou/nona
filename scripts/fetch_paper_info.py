"""
论文信息获取脚本
从数据库读取待处理的论文，获取详细信息
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, LOG_LEVEL, LOG_FORMAT
from database import Database
from fetchers import fetch_paper_info, RateLimitError

# 配置日志
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='获取论文详细信息')
    parser.add_argument('--limit', type=int, default=None, help='处理数量限制')
    parser.add_argument('--status', type=str, default='pendingTitles', help='要处理的论文状态')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("论文信息获取脚本")
    logger.info("="*80)
    
    # 初始化数据库
    db = Database(str(DB_PATH))
    
    # 获取待处理的论文
    papers = db.get_papers_by_status(args.status, args.limit)
    
    if not papers:
        logger.info(f"没有状态为 '{args.status}' 的论文需要处理")
        return
    
    logger.info(f"找到 {len(papers)} 篇论文待处理\n")
    
    # 处理每篇论文
    success_count = 0
    
    for i, paper in enumerate(papers, 1):
        paper_id = paper['id']
        title = paper['title']
        
        logger.info(f"[{i}/{len(papers)}] 处理: {title}")

        while True:
            try:
                info = fetch_paper_info(title)

                if info and info.get("pdf_url"):
                    arxiv_id = info.get("arxiv_id")

                    # 如果 arxiv_id 已存在，说明是重复论文，删除当前 title，跳过即可
                    if arxiv_id:
                        existing = db.get_paper_by_arxiv_id(arxiv_id)
                        if existing and existing.get("id") != paper_id:
                            logger.warning(
                                "检测到重复论文: arxiv_id=%s 已存在于记录(id=%s, title=%r)，"
                                "当前记录(id=%s, title=%r) 将被删除并跳过。",
                                arxiv_id,
                                existing.get("id"),
                                existing.get("title"),
                                paper_id,
                                title,
                            )
                            db.delete_paper(paper_id)
                            db.remove_detail_failure(paper_id)
                            break

                    updates = {
                        'arxiv_id': arxiv_id,
                        'pdf_url': info.get('pdf_url'),
                        'authors': info.get('authors', []),
                        'abstract': info.get('abstract'),
                        'published_date': info.get('published_date'),
                        'status': 'TobeDownloaded'
                    }

                    db.update_paper_info(paper_id, updates)
                    db.remove_detail_failure(paper_id)
                    success_count += 1
                    logger.info("✓ 成功获取信息")
                    break

                logger.warning("首条结果缺少PDF链接，尝试获取备用结果...")
                fallback = fetch_paper_info(title)
                if fallback and fallback.get("pdf_url"):
                    arxiv_id_fb = fallback.get("arxiv_id")

                    if arxiv_id_fb:
                        existing = db.get_paper_by_arxiv_id(arxiv_id_fb)
                        if existing and existing.get("id") != paper_id:
                            logger.warning(
                                "检测到重复论文(备用结果): arxiv_id=%s 已存在于记录(id=%s, title=%r)，"
                                "当前记录(id=%s, title=%r) 将被删除并跳过。",
                                arxiv_id_fb,
                                existing.get("id"),
                                existing.get("title"),
                                paper_id,
                                title,
                            )
                            db.delete_paper(paper_id)
                            db.remove_detail_failure(paper_id)
                            break

                    updates = {
                        'arxiv_id': arxiv_id_fb,
                        'pdf_url': fallback.get('pdf_url'),
                        'authors': fallback.get('authors', []),
                        'abstract': fallback.get('abstract'),
                        'published_date': fallback.get('published_date'),
                        'status': 'TobeDownloaded'
                    }

                    db.update_paper_info(paper_id, updates)
                    db.remove_detail_failure(paper_id)
                    success_count += 1
                    logger.info("✓ 备用结果获取成功")
                    break

                reason = "未找到包含PDF链接的详细信息"
                logger.warning(f"✗ {reason}")
                db.update_paper_status(paper_id, 'detailFailed')
                db.record_detail_failure(paper_id, title, paper.get('source'), reason)
                break

            except RateLimitError as rl_err:
                logger.warning(
                    "arXiv 请求受到限制（status=%s），暂停60秒后重试...",
                    rl_err.status_code,
                )
                time.sleep(60)
                continue

            except Exception as e:
                reason = str(e)
                logger.error(f"✗ 处理失败: {reason}")
                db.update_paper_status(paper_id, 'detailFailed')
                db.record_detail_failure(paper_id, title, paper.get('source'), reason)
                break
        logger.info("Sleeping %.2f seconds after fetch to respect rate limits", 3)
        time.sleep(3)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"处理完成: {success_count}/{len(papers)} 篇成功")
    logger.info(f"{'='*80}\n")
    logger.info("提示：未成功的标题已记录到 detail_failures，可用 scripts/retry_failures.py --type detail 重试。")
    
    # 显示统计信息
    stats = db.get_statistics()
    logger.info("数据库统计:")
    logger.info(f"总论文数: {stats['total_papers']}")
    logger.info(f"状态分布: {stats['status_counts']}")
    logger.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()


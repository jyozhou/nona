"""
论文标题收集脚本
从各个来源收集论文标题并存入数据库
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, LOG_LEVEL, LOG_FORMAT, TITLE_KEYWORDS
from database import Database
import collectors

# 配置日志
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='收集论文标题')
    parser.add_argument('--source', type=str, choices=[
        'arxiv', 'neurips', 'iclr', 'icml', 'corl', 'rss', 'icra', 'iros',
        'cvpr', 'iccv', 'siggraph', 'google', 'all'
    ], default='all', help='论文来源')
    parser.add_argument('--year', type=int, default=2024, help='年份')
    parser.add_argument('--arxiv-category', type=str, default='cs.RO', help='arXiv分类')
    parser.add_argument('--max-results', type=int, default=5000,
                        help='arXiv 最大抓取数量（默认5000，单批次最多1000）')
    parser.add_argument('--query', type=str, default=None,
                        help='Google 搜索 query，例如 "cvpr 2025 paper list"')
    parser.add_argument('--keyword-filter', action='store_true',
                        help='对收集到的标题使用 TITLE_KEYWORDS 做快速预筛')
    parser.add_argument('--keyword', action='append', default=[],
                        help='追加标题筛选关键词，可重复传入，支持 "keyword:weight"')
    parser.add_argument('--min-keyword-score', type=float, default=2.0,
                        help='标题关键词预筛最低分数，默认 2.0')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("论文标题收集脚本")
    logger.info("="*80)
    
    # 初始化数据库
    db = Database(str(DB_PATH))
    
    # 收集论文
    all_papers = []
    
    if args.source == 'all':
        sources = [
            'arxiv', 'neurips', 'iclr', 'icml', 'corl', 'rss', 'icra', 'iros',
            'cvpr', 'iccv', 'siggraph'
        ]
    else:
        sources = [args.source]
    
    for source in sources:
        logger.info(f"\n{'='*80}")
        logger.info(f"收集来源: {source.upper()} ({args.year})")
        logger.info(f"{'='*80}\n")
        
        try:
            if source == 'arxiv':
                papers = collectors.collect_arxiv_papers(
                    args.year,
                    args.arxiv_category,
                    args.max_results
                )
            elif source == 'neurips':
                papers = collectors.collect_neurips_papers(args.year)
            elif source == 'iclr':
                papers = collectors.collect_iclr_papers(args.year)
            elif source == 'icml':
                papers = collectors.collect_icml_papers(args.year)
            elif source == 'corl':
                papers = collectors.collect_corl_papers(args.year)
            elif source == 'rss':
                papers = collectors.collect_rss_papers(args.year)
            elif source == 'icra':
                papers = collectors.collect_icra_papers(args.year)
            elif source == 'iros':
                papers = collectors.collect_iros_papers(args.year)
            elif source == 'cvpr':
                papers = collectors.collect_cvpr_papers(args.year)
            elif source == 'iccv':
                papers = collectors.collect_iccv_papers(args.year)
            elif source == 'siggraph':
                papers = collectors.collect_siggraph_papers(args.year)
            elif source == 'google':
                query = args.query or f"cvpr {args.year} paper list"
                papers = collectors.collect_google_paper_titles(
                    query=query,
                    year=args.year,
                    keywords=[*TITLE_KEYWORDS, *args.keyword],
                    max_results=args.max_results,
                    min_keyword_score=args.min_keyword_score,
                )
            else:
                continue

            if args.keyword_filter and source != 'google':
                papers = collectors.filter_papers_by_keywords(
                    papers,
                    [*TITLE_KEYWORDS, *args.keyword],
                    min_score=args.min_keyword_score,
                )
            
            all_papers.extend(papers)
            logger.info(f"收集到 {len(papers)} 篇论文")
            
        except Exception as e:
            logger.error(f"收集 {source} 时出错: {e}")
            continue
    
    # 存入数据库
    if all_papers:
        logger.info(f"\n{'='*80}")
        logger.info(f"保存到数据库...")
        logger.info(f"{'='*80}\n")
        
        seen_titles = set()
        unique_papers = []
        for paper in all_papers:
            title_key = paper['title'].lower().strip()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_papers.append(paper)
        all_papers = unique_papers
        # 转换格式
        papers_to_insert = []
        for paper in all_papers:
            papers_to_insert.append({
                'title': paper['title'],
                'source': paper.get('source', 'unknown'),
                'published_date': paper.get('published_date', ''),
                'status': 'pendingTitles'
            })
        
        count = db.batch_insert_papers(papers_to_insert)
        logger.info(f"成功保存 {count} 篇论文到数据库")
    else:
        logger.warning("没有收集到任何论文")
    
    # 显示统计信息
    stats = db.get_statistics()
    logger.info(f"\n{'='*80}")
    logger.info("数据库统计")
    logger.info(f"{'='*80}")
    logger.info(f"总论文数: {stats['total_papers']}")
    logger.info(f"状态分布: {stats['status_counts']}")
    logger.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()


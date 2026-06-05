"""
论文分析脚本
使用AI分析论文相关性并生成总结
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, TEXT_DIR, LOG_LEVEL, LOG_FORMAT, RELEVANCE_TAGS, DEFAULT_LLM_PROVIDER
from database import Database
from analyzers import analyze_paper

# 配置日志
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='分析论文相关性')
    parser.add_argument('--limit', type=int, default=None, help='处理数量限制')
    parser.add_argument('--status', type=str, default='processed', help='要处理的论文状态')
    parser.add_argument('--provider', type=str, 
                       default=DEFAULT_LLM_PROVIDER, help='LLM提供商 (custom, openai, anthropic)')
    parser.add_argument('--min-score', type=float, default=0.5, help='最小相关性分数阈值')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("论文相关性分析脚本")
    logger.info("="*80)
    logger.info(f"LLM提供商: {args.provider}")
    logger.info(f"相关性标签: {', '.join(RELEVANCE_TAGS)}")
    logger.info(f"最小分数阈值: {args.min_score}")
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
    relevant_count = 0
    
    for i, paper in enumerate(papers, 1):
        paper_id = paper['id']
        title = paper['title']
        arxiv_id = paper.get('arxiv_id')
        file_id = arxiv_id or paper_id
        
        logger.info(f"[{i}/{len(papers)}] 分析: {title}")
        
        if not title:
            logger.warning(f"✗ 缺少论文标题")
            continue
        
        # 读取文本
        text_path = TEXT_DIR / f"{file_id}.txt"
        
        if not text_path.exists():
            logger.warning(f"✗ 文本文件不存在: {text_path}")
            continue
        
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                paper_text = f.read()
            
            # 限制文本长度
            if len(paper_text) > 50000:
                paper_text = paper_text[:40000] + "\n\n[... 中间部分已省略 ...]\n\n" + paper_text[-10000:]
            
            # 分析论文
            result = analyze_paper(
                paper_text=paper_text,
                paper_info=paper,
                provider=args.provider,
                relevance_tags=RELEVANCE_TAGS
            )
            
            if result:
                # 保存分析结果
                result['paper_id'] = paper_id
                db.insert_analysis_result(result)
                
                # 更新论文状态
                db.update_paper_status(paper_id, 'analyzed')
                
                success_count += 1
                
                if result.get('is_relevant') and result.get('relevance_score', 0) >= args.min_score:
                    relevant_count += 1
                    logger.info(f"✓ 相关 (分数: {result.get('relevance_score'):.2f})")
                else:
                    logger.info(f"○ 不相关 (分数: {result.get('relevance_score', 0):.2f})")
            else:
                logger.warning(f"✗ 分析失败")
                
        except Exception as e:
            logger.error(f"✗ 处理失败: {e}")
            continue
    
    logger.info(f"\n{'='*80}")
    logger.info("分析完成:")
    logger.info(f"  成功分析: {success_count}/{len(papers)} 篇")
    logger.info(f"  相关论文: {relevant_count} 篇")
    logger.info(f"  相关率: {relevant_count/success_count*100:.1f}%" if success_count > 0 else "  相关率: N/A")
    logger.info(f"{'='*80}\n")
    
    # 显示统计信息
    stats = db.get_statistics()
    logger.info("数据库统计:")
    logger.info(f"总论文数: {stats['total_papers']}")
    logger.info(f"已分析: {stats['analyzed_papers']}")
    logger.info(f"相关论文: {stats['relevant_papers']}")
    logger.info(f"状态分布: {stats['status_counts']}")
    logger.info(f"{'='*80}\n")
    
    # 显示最相关的论文
    relevant_papers = db.get_relevant_papers(args.min_score)
    
    if relevant_papers:
        logger.info("最相关的论文（Top 10）:")
        logger.info("="*80)
        
        for i, p in enumerate(relevant_papers[:10], 1):
            logger.info(f"\n{i}. {p['title']}")
            logger.info(f"   分数: {p.get('relevance_score', 0):.2f}")
            logger.info(f"   理由: {p.get('reasoning', 'N/A')[:100]}...")
        
        logger.info("\n" + "="*80)


if __name__ == '__main__':
    main()


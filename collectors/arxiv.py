"""
arXiv论文收集器
收集指定年份和类别的arXiv论文标题
"""

import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


def collect_arxiv_papers(
    year: int = 2025,
    category: str = "cs.RO",
    max_results: int = 5000
) -> List[Dict[str, str]]:
    """
    收集arXiv论文标题
    
    Args:
        year: 年份
        category: 分类（默认cs.RO - 机器人）
        max_results: 最大结果数
        
    Returns:
        论文列表，每个元素包含 {title, url, source}
    """
    logger.info(f"Collecting arXiv papers for {year}, category: {category}")
    
    papers = []
    base_url = "http://export.arxiv.org/api/query"
    
    try:
        # 构建查询：指定分类和年份范围
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        
        # arXiv API查询
        query = f"cat:{category} AND submittedDate:[{start_date} TO {end_date}]"
        
        # 分批获取（每次最多获取1000条）
        batch_size = min(1000, max_results)
        start_index = 0
        
        while start_index < max_results:
            params = {
                'search_query': query,
                'start': start_index,
                'max_results': batch_size,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            
            # 解析XML响应
            batch_papers = _parse_arxiv_response(response.content, year)
            
            if not batch_papers:
                logger.info(f"No more results at offset {start_index}")
                break
            
            papers.extend(batch_papers)
            logger.info(f"Collected {len(papers)} papers so far...")
            
            start_index += batch_size
            
            # 如果返回的结果少于batch_size，说明已经没有更多结果了
            if len(batch_papers) < batch_size:
                break
        
        logger.info(f"Successfully collected {len(papers)} papers from arXiv {year}")
        return papers
        
    except Exception as e:
        logger.error(f"Error collecting arXiv papers: {e}")
        return papers


def _parse_arxiv_response(xml_content: bytes, year: int) -> List[Dict[str, str]]:
    """
    解析arXiv API的XML响应
    
    Args:
        xml_content: XML内容
        year: 年份（用于source标识）
        
    Returns:
        论文列表
    """
    papers = []
    
    try:
        root = ET.fromstring(xml_content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entries = root.findall('atom:entry', namespace)
        
        for entry in entries:
            try:
                # 提取标题
                title_elem = entry.find('atom:title', namespace)
                if title_elem is None:
                    continue
                
                title = title_elem.text.strip()
                # 标准化标题的空白字符
                title = ' '.join(title.split())
                
                # 提取arXiv链接
                id_elem = entry.find('atom:id', namespace)
                url = id_elem.text.strip() if id_elem is not None else ''
                
                # 提取发布日期
                published_elem = entry.find('atom:published', namespace)
                published_date = ''
                if published_elem is not None:
                    published_date = published_elem.text.strip()
                
                papers.append({
                    'title': title,
                    'url': url,
                    'source': f'arXiv{year}',
                    'published_date': published_date
                })
                
            except Exception as e:
                logger.warning(f"Error parsing entry: {e}")
                continue
        
        return papers
        
    except Exception as e:
        logger.error(f"Error parsing arXiv XML response: {e}")
        return []


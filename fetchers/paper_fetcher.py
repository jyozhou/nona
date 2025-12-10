"""
论文信息获取器
使用arXiv和OpenAlex API搜索论文详细信息
参考Reference/tools/paper/中的实现
"""

import logging
import requests
import xml.etree.ElementTree as ET
import re
import time
import difflib
from typing import Dict, List, Optional
from tqdm import tqdm

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when arXiv returns rate-limit responses."""

    def __init__(self, status_code: Optional[int] = None):
        self.status_code = status_code
        message = f"Rate limited by arXiv (status: {status_code})" if status_code else "Rate limited by arXiv"
        super().__init__(message)


def fetch_paper_info(title: str, url: str = None) -> Optional[Dict]:
    """
    获取论文详细信息
    
    Args:
        title: 论文标题
        url: 论文URL（可选，如果提供则尝试从URL提取信息）
        
    Returns:
        论文信息字典，包含: title, arxiv_id, pdf_url, authors, abstract, published_date
        如果找不到返回None
    """
    if not title:
        logger.error("Title is required")
        return None
    
    logger.info(f"Fetching info for: {title}")
    
    # 如果提供了URL，尝试从URL提取信息
    if url:
        result = _extract_from_url(title, url)
        if result and result.get('arxiv_id'):
            return result
    
    # 使用组合搜索策略：arXiv + OpenAlex
    result = _combined_search(title)
    
    if result:
        logger.info(f"✓ Found paper: {result.get('title')}")
        return result
    else:
        logger.warning(f"✗ Could not find paper: {title}")
        return None


def batch_fetch_papers(papers: List[Dict], show_progress: bool = True) -> List[Dict]:
    """
    批量获取论文信息
    
    Args:
        papers: 论文列表，每个元素应包含'title'字段，可选'url'字段
        show_progress: 是否显示进度条
        
    Returns:
        获取到信息的论文列表
    """
    results = []
    
    iterator = tqdm(papers, desc="Fetching papers") if show_progress else papers
    
    for paper in iterator:
        title = paper.get('title')
        url = paper.get('url')
        
        if not title:
            continue
        
        try:
            info = fetch_paper_info(title, url)
            
            if info:
                # 添加原始source信息
                info['source'] = paper.get('source', 'unknown')
                results.append(info)
            
        except Exception as e:
            logger.error(f"Error fetching paper '{title}': {e}")
            continue
    
    logger.info(f"Successfully fetched {len(results)}/{len(papers)} papers")
    return results


def _combined_search(title: str, max_results_per_source: int = 10) -> Optional[Dict]:
    """
    组合搜索策略：arXiv + OpenAlex
    参考Reference/tools/paper/search_openalex.py中的实现
    """
    arxiv_results = _search_arxiv(title, max_results_per_source)
    arxiv_candidates = [r for r in arxiv_results if r]

    # 先在 arXiv 里选一个与标题最相似的结果
    best_from_arxiv = _pick_best_match(title, arxiv_candidates, source_name="arXiv")
    if best_from_arxiv and best_from_arxiv.get("pdf_url"):
        return best_from_arxiv

    # 再尝试 OpenAlex
    openalex_results = _search_openalex(title, max_results_per_source)
    openalex_candidates = [r for r in openalex_results if r]

    best_from_openalex = _pick_best_match(title, openalex_candidates, source_name="OpenAlex")
    if best_from_openalex and best_from_openalex.get("pdf_url"):
        return best_from_openalex

    # 都没有足够相似的结果，就认为查不到，返回 None
    return None


def _normalize_title(text: str) -> str:
    """简单归一化标题：小写 + 压缩空白"""
    if not text:
        return ""
    return " ".join(text.lower().split())


def _title_similarity(query_title: str, candidate_title: str) -> float:
    """计算两个标题的相似度 (0~1)"""
    q = _normalize_title(query_title)
    c = _normalize_title(candidate_title)
    if not q or not c:
        return 0.0
    return difflib.SequenceMatcher(None, q, c).ratio()


def _pick_best_match(
    query_title: str,
    candidates: List[Dict],
    source_name: str,
    min_similarity: float = 0.8,
) -> Optional[Dict]:
    """
    从候选结果中选择与 query_title 最相似的一条，要求相似度 >= min_similarity
    """
    if not candidates:
        return None

    best = None
    best_score = 0.0

    for cand in candidates:
        cand_title = cand.get("title", "") or ""
        score = _title_similarity(query_title, cand_title)
        if score > best_score:
            best_score = score
            best = cand

    if not best:
        return None

    logger.info(
        "Best %s match for %r is %r (similarity=%.3f)",
        source_name,
        query_title,
        best.get("title"),
        best_score,
    )

    if best_score < min_similarity:
        logger.warning(
            "%s 返回了 %d 条结果，但与标题 %r 的最佳相似度只有 %.3f，"
            "认为匹配不可靠，放弃这些结果。",
            source_name,
            len(candidates),
            query_title,
            best_score,
        )
        return None

    return best


def _search_arxiv(title: str, max_results: int = 10) -> List[Dict]:
    """
    使用arXiv API搜索论文
    参考Reference/tools/paper/search_openalex.py中的实现
    """
    base_url = "http://export.arxiv.org/api/query"

    def _request(params):
        try:
            resp = requests.get(base_url, params=params, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            if status in (429, 443, 503):
                raise RateLimitError(status) from exc
            raise

    try:
        # 策略1：精确标题搜索
        query = f'ti:"{title}"'
        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        response = _request(params)
        results = _parse_arxiv_response(response.content)

        if results:
            logger.info(f"Found {len(results)} results from arXiv")
            return results

        # 策略2：关键词搜索
        keywords = re.sub(r'\b(a|an|the|and|or|of|for|in|on|at|to|with|by|from)\b', '', title.lower())
        keywords = re.sub(r'[^\w\s]', ' ', keywords)
        keywords = ' '.join(keywords.split())

        query2 = f'all:{keywords}'
        params['search_query'] = query2

        response2 = _request(params)
        results = _parse_arxiv_response(response2.content)
        logger.info(f"Found {len(results)} results from arXiv (keywords)")
        return results

    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"Error searching arXiv: {e}")
        return []


def _parse_arxiv_response(xml_content: bytes) -> List[Dict]:
    """解析arXiv API的XML响应"""
    try:
        root = ET.fromstring(xml_content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom', 
                    'arxiv': 'http://arxiv.org/schemas/atom'}
        
        entries = root.findall('atom:entry', namespace)
        results = []
        
        for entry in entries:
            try:
                # 提取arXiv ID
                id_url = entry.find('atom:id', namespace).text
                arxiv_id = id_url.split('/')[-1]
                if 'v' in arxiv_id:
                    arxiv_id = arxiv_id.split('v')[0]
                
                # 提取标题
                title_elem = entry.find('atom:title', namespace)
                title = ' '.join(title_elem.text.strip().split()) if title_elem is not None else ''
                
                # 提取作者
                authors = []
                for author in entry.findall('atom:author', namespace):
                    name_elem = author.find('atom:name', namespace)
                    if name_elem is not None:
                        authors.append(name_elem.text.strip())
                
                # 提取摘要
                summary_elem = entry.find('atom:summary', namespace)
                abstract = ' '.join(summary_elem.text.strip().split()) if summary_elem is not None else ''
                
                # 提取发布日期
                published_elem = entry.find('atom:published', namespace)
                published_date = published_elem.text.strip() if published_elem is not None else ''
                
                result = {
                    'title': title,
                    'arxiv_id': arxiv_id,
                    'pdf_url': f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    'authors': authors,
                    'abstract': abstract,
                    'published_date': published_date
                }
                
                results.append(result)
                
            except Exception as e:
                logger.warning(f"Error parsing arXiv entry: {e}")
                continue
        
        return results
        
    except Exception as e:
        logger.error(f"Error parsing arXiv response: {e}")
        return []


def _search_openalex(title: str, max_results: int = 10) -> List[Dict]:
    """
    使用OpenAlex API搜索论文
    参考Reference/tools/paper/search_openalex.py中的实现
    """
    base_url = "https://api.openalex.org/works"
    
    try:
        encoded_query = title.replace(' ', '%20')
        url = f"{base_url}?search={encoded_query}&per-page={min(max_results, 25)}"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        works = data.get('results', [])
        
        if not works:
            return []
        
        results = []
        
        for work in works:
            try:
                # 提取基本信息
                result = {
                    'title': work.get('display_name', ''),
                    'authors': [],
                    'abstract': work.get('abstract', ''),
                    'published_date': str(work.get('publication_year', '')),
                    'arxiv_id': None,
                    'pdf_url': None
                }
                
                # 提取作者
                for authorship in work.get('authorships', []):
                    if authorship and authorship.get('author'):
                        author_name = authorship['author'].get('display_name')
                        if author_name:
                            result['authors'].append(author_name)
                
                # 提取arXiv ID
                arxiv_id = None
                
                # 从locations中查找arXiv
                for location in work.get('locations', []):
                    if not location:
                        continue
                    source = location.get('source')
                    if source and 'arxiv' in source.get('display_name', '').lower():
                        pdf_url = location.get('pdf_url', '')
                        if pdf_url and 'arxiv.org' in pdf_url:
                            match = re.search(r'arxiv\.org/(?:pdf/|abs/)?(\d+\.\d+)', pdf_url)
                            if match:
                                arxiv_id = match.group(1)
                                break
                
                # 从external IDs中查找
                if not arxiv_id:
                    external_ids = work.get('ids', {})
                    if external_ids and 'arxiv' in external_ids:
                        arxiv_url = external_ids['arxiv']
                        if arxiv_url:
                            match = re.search(r'arxiv\.org/(?:abs/|pdf/)?(\d+\.\d+)', arxiv_url)
                            if match:
                                arxiv_id = match.group(1)
                
                result['arxiv_id'] = arxiv_id
                
                # 确定PDF URL
                if arxiv_id:
                    result['pdf_url'] = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                else:
                    # 尝试从locations获取PDF
                    primary_location = work.get('primary_location')
                    if primary_location and primary_location.get('pdf_url'):
                        result['pdf_url'] = primary_location['pdf_url']
                
                results.append(result)
                
            except Exception as e:
                logger.warning(f"Error processing OpenAlex result: {e}")
                continue
        
        logger.info(f"Found {len(results)} results from OpenAlex")
        return results
        
    except Exception as e:
        logger.error(f"Error searching OpenAlex: {e}")
        return []


def _extract_from_url(title: str, url: str) -> Optional[Dict]:
    """
    从提供的URL中提取论文信息
    """
    arxiv_id = None
    pdf_url = None
    
    # 尝试从URL提取arXiv ID
    arxiv_patterns = [
        r'arxiv\.org/abs/(\d+\.\d+)',
        r'arxiv\.org/pdf/(\d+\.\d+)',
    ]
    
    for pattern in arxiv_patterns:
        match = re.search(pattern, url)
        if match:
            arxiv_id = match.group(1)
            break
    
    if arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        logger.info(f"Extracted arXiv ID from URL: {arxiv_id}")
        
        return {
            'title': title,
            'arxiv_id': arxiv_id,
            'pdf_url': pdf_url,
            'authors': [],
            'abstract': '',
            'published_date': ''
        }
    
    return None


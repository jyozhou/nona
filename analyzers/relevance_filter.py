"""
论文相关性分析器
使用LLM判断论文是否与指定主题相关，并生成总结
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from tqdm import tqdm
from llm_client import call_llm

logger = logging.getLogger(__name__)


def analyze_paper(
    paper_text: str,
    paper_info: Dict,
    provider: str = "custom",
    relevance_tags: List[str] = None
) -> Optional[Dict]:
    """
    分析论文相关性
    
    Args:
        paper_text: 论文文本内容
        paper_info: 论文基本信息（标题、作者等）
        provider: LLM提供商（custom, openai, anthropic等）
        relevance_tags: 相关性标签列表
        
    Returns:
        分析结果字典: {
            'is_relevant': bool,
            'relevance_score': float,
            'reasoning': str,
            'summary': str
        }
    """
    try:
        logger.info(f"Analyzing paper: {paper_info.get('title', 'Unknown')}")
        
        # 如果没有提供标签，使用默认标签
        if relevance_tags is None:
            from config import RELEVANCE_TAGS
            relevance_tags = RELEVANCE_TAGS
        
        # 获取配置
        from config import get_api_key, get_model_name, get_base_url
        
        api_key = get_api_key(provider)
        model = get_model_name(provider)
        base_url = get_base_url(provider)
        
        if not api_key:
            logger.error(f"API key not configured for provider: {provider}")
            return None
        
        if not model:
            logger.error(f"Model not configured for provider: {provider}")
            return None
        
        if not base_url:
            logger.error(f"Base URL not configured for provider: {provider}")
            return None
        
        # 构建提示词
        prompt = _build_analysis_prompt(paper_text, paper_info, relevance_tags)
        
        # 构建消息
        messages = [
            {"role": "system", "content": "你是一个专业的科研论文分析助手，擅长判断论文的研究方向和相关性。"},
            {"role": "user", "content": prompt}
        ]
        
        # 调用LLM
        response = call_llm(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        
        if not response:
            logger.error("Failed to get response from LLM")
            return None
        
        content = response.get('content', '')
        
        # 解析JSON响应
        result = _parse_llm_response(content)
        
        if result:
            logger.info(f"✓ Analysis complete. Relevant: {result.get('is_relevant')}, Score: {result.get('relevance_score')}")
            return result
        else:
            logger.error("Failed to parse LLM response")
            return None
            
    except Exception as e:
        logger.error(f"Error analyzing paper: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def batch_analyze_papers(
    papers: List[Dict],
    text_dir: Path,
    provider: str = "custom",
    relevance_tags: List[str] = None,
    show_progress: bool = True
) -> List[Dict]:
    """
    批量分析论文
    
    Args:
        papers: 论文列表
        text_dir: 文本文件目录
        provider: LLM提供商
        relevance_tags: 相关性标签
        show_progress: 是否显示进度条
        
    Returns:
        分析结果列表
    """
    results = []
    
    iterator = tqdm(papers, desc="Analyzing papers") if show_progress else papers
    
    for paper in iterator:
        paper_id = paper.get('arxiv_id') or paper.get('id')
        
        if not paper_id:
            logger.warning(f"Missing paper ID for: {paper.get('title')}")
            continue
        
        # 读取文本文件
        text_path = text_dir / f"{paper_id}.txt"
        
        if not text_path.exists():
            logger.warning(f"Text file not found: {text_path}")
            continue
        
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                paper_text = f.read()
            
            # 限制文本长度（避免超过token限制）
            paper_text = _truncate_text(paper_text, max_chars=50000)
            
            # 分析论文
            result = analyze_paper(paper_text, paper, provider, relevance_tags)
            
            if result:
                # 添加paper_id到结果中
                result['paper_id'] = paper_id
                results.append(result)
                
        except Exception as e:
            logger.error(f"Error processing paper {paper_id}: {e}")
            continue
    
    logger.info(f"Successfully analyzed {len(results)}/{len(papers)} papers")
    return results


def _build_analysis_prompt(
    paper_text: str,
    paper_info: Dict,
    relevance_tags: List[str]
) -> str:
    """构建分析提示词"""
    
    tags_str = ", ".join(relevance_tags)
    
    prompt = f"""请分析以下论文，判断它是否与这些研究主题相关：{tags_str}

当前调研主题是数字人物/人脸/人头三维重建，重点关注近两年的 CVPR、ICCV、SIGGRAPH、ICLR 等会议论文。请优先判断：
1. 是否聚焦 avatar、人脸、人头、上半身或人体的 3D/4D 重建、生成、跟踪、动画或神经渲染；
2. 是否可能适用于 Nersemble 等人头/人脸数据集；
3. 方法是偏前馈式还是优化式，若是 LAM/LHM 这类高成本前馈方法，请说明可作为特征提取或预处理组件；
4. 论文或项目是否开源，以及文中提到的显卡/训练时长/推理成本。

论文标题：{paper_info.get('title', 'Unknown')}

论文作者：{', '.join(paper_info.get('authors', [])[:5]) if isinstance(paper_info.get('authors'), list) else paper_info.get('authors', 'N/A')}

论文摘要：
{paper_info.get('abstract', 'N/A')[:1000]}

论文内容（部分）：
{paper_text[:10000]}

请按照以下JSON格式返回分析结果：
{{
    "is_relevant": true/false,
    "relevance_score": 0.0-1.0,
    "reasoning": "判断理由（中文，2-3句话）",
    "summary": "论文总结（中文，200-350字，必须覆盖：任务定义/输入输出、方法类型与核心模型、是否偏前馈式或优化式、代码是否开源、显卡或计算成本信息；若原文未说明请写未提及）"
}}

评分标准：
- 1.0: 高度相关，核心研究内容直接关联
- 0.7-0.9: 相关性强，有显著关联
- 0.4-0.6: 中等相关，有一定关联
- 0.1-0.3: 弱相关，仅有少量关联
- 0.0: 不相关

请只返回JSON，不要有其他内容。
"""
    
    return prompt


def _parse_llm_response(content: str) -> Optional[Dict]:
    """
    解析LLM响应内容
    
    Args:
        content: LLM返回的文本内容
        
    Returns:
        解析后的字典，包含 is_relevant, relevance_score, reasoning, summary
    """
    try:
        # 清理内容
        json_text = content.strip()
        
        # 移除可能的markdown代码块标记
        if json_text.startswith('```json'):
            json_text = json_text[7:]
        elif json_text.startswith('```'):
            json_text = json_text[3:]
        
        if json_text.endswith('```'):
            json_text = json_text[:-3]
        
        json_text = json_text.strip()
        
        # 解析JSON
        result = json.loads(json_text)
        
        # 验证必要字段
        required_fields = ['is_relevant', 'relevance_score', 'reasoning', 'summary']
        for field in required_fields:
            if field not in result:
                logger.warning(f"Missing field '{field}' in LLM response")
                # 提供默认值
                if field == 'is_relevant':
                    result[field] = False
                elif field == 'relevance_score':
                    result[field] = 0.0
                elif field == 'reasoning':
                    result[field] = "无法解析"
                elif field == 'summary':
                    result[field] = "无法生成总结"
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.error(f"Content: {content[:200]}...")
        return None
    
    except Exception as e:
        logger.error(f"Error parsing LLM response: {e}")
        return None


def _truncate_text(text: str, max_chars: int = 50000) -> str:
    """
    截断文本到指定长度
    保留开头和结尾部分
    """
    if len(text) <= max_chars:
        return text
    
    # 保留前80%和后20%
    head_chars = int(max_chars * 0.8)
    tail_chars = int(max_chars * 0.2)
    
    head = text[:head_chars]
    tail = text[-tail_chars:]
    
    return head + "\n\n[... 中间部分已省略 ...]\n\n" + tail

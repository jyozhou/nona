# 具身智能论文Survey工具

自动收集、处理和筛选具身智能领域论文的Python工具。

## 功能

- 从NeurIPS、ICLR、ICML、CoRL、RSS、ICRA、IROS和arXiv收集论文
- 获取论文详细信息（arXiv ID、PDF链接等）
- 下载PDF并转换为文本
- 使用LLM分析论文相关性并生成总结

## 安装

```bash
git clone https://github.com/jyozhou/nona.git
cd nona
pip install -r requirements.txt
```

## 配置

1. 复制配置文件：
```bash
cp env.example .env
```

2. 编辑 `.env`，配置LLM API：
```bash
DEFAULT_LLM_PROVIDER=custom
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-chat
```

支持的服务：OpenRouter、DeepSeek、Gemini、智谱AI、硅基流动、OpenAI等。详见 `env.example`。

3. 测试配置：
```bash
python tests/test_llm_config.py
```

## 使用方法

### 1. 收集论文标题

```bash
# 基本格式
python scripts/collect_titles.py --source <来源> --year <年份>

# 收集各会议论文
python scripts/collect_titles.py --source neurips --year 2024
python scripts/collect_titles.py --source iclr --year 2025
python scripts/collect_titles.py --source icml --year 2024
python scripts/collect_titles.py --source corl --year 2024
python scripts/collect_titles.py --source rss --year 2024
python scripts/collect_titles.py --source icra --year 2024
python scripts/collect_titles.py --source iros --year 2024

# 收集arXiv论文（可指定分类(默认RO)和最大数量）
python scripts/collect_titles.py --source arxiv --year 2025 --max-results 3000
python scripts/collect_titles.py --source arxiv --year 2025 --arxiv-category cs.AI --max-results 8000

# 收集所有来源
python scripts/collect_titles.py --source all --year 2024 --max-results 6000
```

**参数说明**：
- `--source`: 论文来源，可选值：`arxiv`, `neurips`, `iclr`, `icml`, `corl`, `rss`, `icra`, `iros`, `all`（默认：`all`）
- `--year`: 年份（默认：`2024`）
- `--arxiv-category`: arXiv分类，仅对`arxiv`有效（默认：`cs.RO`），常见分类：`cs.RO`, `cs.AI`, `cs.CV`, `cs.LG`, `cs.CL`
- `--max-results`: arXiv最大抓取数量（默认 `5000`，单批次最多 `1000`，脚本会自动分页）

### 2. 获取论文详细信息

```bash
# 获取待处理论文的详细信息（ArxivID、PDF下载url等）
python scripts/fetch_paper_info.py

# 限制处理数量
python scripts/fetch_paper_info.py --limit 100

# 处理指定状态的论文
python scripts/fetch_paper_info.py --status pendingTitles --limit 50
```

**参数说明**：
- `--limit`: 处理数量限制（可选，不指定则处理所有）
- `--status`: 要处理的论文状态（默认：`pendingTitles`），可选值：`pendingTitles`, `TobeDownloaded`, `processed`, `analyzed`

### 3. 处理PDF文件

```bash
# 下载并处理PDF
python scripts/process_pdfs.py

# 限制处理数量
python scripts/process_pdfs.py --limit 50

# 只下载PDF，不进行文本转换
python scripts/process_pdfs.py --skip-convert --limit 100

# 只进行文本转换，跳过下载（适用于已下载的PDF）
python scripts/process_pdfs.py --skip-download

```

**参数说明**：
- `--limit`: 处理数量限制（可选）
- `--status`: 要处理的论文状态（默认：`TobeDownloaded`）
- `--skip-download`: 跳过下载步骤，只进行文本转换
- `--skip-convert`: 跳过文本转换步骤，只进行下载

**注释**：
- corl、iclr、icml、icra、iros等会议第一篇文章下载失败是正常现象，在dblp爬取会议接收文章标题列表时获取到的第一个标题是当年会议记录出版信息
- 获取详情失败的标题会被保存到`detail_failures`表，PDF下载失败的记录会被保存到`download_failures`表，可通过 `scripts/retry_failures.py` 重新入队
- 在海量数据里存在一定比例的详情获取/下载失败是正常情况，脚本会自动跳过并记录到上述失败列表中，整体任务仍会继续执行

### 4. AI分析和筛选

```bash
# 分析论文相关性
python scripts/analyze_papers.py

# 使用特定的LLM提供商
python scripts/analyze_papers.py --provider custom
python scripts/analyze_papers.py --provider openai
python scripts/analyze_papers.py --provider anthropic

# 限制处理数量
python scripts/analyze_papers.py --limit 20

# 设置最小相关性分数阈值（0.0-1.0）
python scripts/analyze_papers.py --min-score 0.7 --limit 20

# 处理指定状态的论文
python scripts/analyze_papers.py --status processed --limit 50
```

**参数说明**：
- `--limit`: 处理数量限制（可选）
- `--status`: 要处理的论文状态（默认：`processed`）
- `--provider`: LLM提供商，可选值：`custom`, `openai`, `anthropic`（默认：`.env`中配置的`DEFAULT_LLM_PROVIDER`）
- `--min-score`: 最小相关性分数阈值（默认：`0.5`），只有分数≥此值的论文才会被标记为相关

### 5. 辅助操作
```
# 删除数据库与全部pdf、txt文本（谨慎操作）
python scripts/clean_data.py

# 检查当前数据库情况
python scripts/quick_verify.py

# 将获取详情失败的条目重新放回pendingTitles队列
python scripts/retry_failures.py --type detail

# 将下载失败的条目重新放回TobeDownloaded队列
python scripts/retry_failures.py --type download

# 启动网页端可视化（FastAPI）
uvicorn web.app:app --reload
```


## 完整工作流示例

```bash
# 1. 收集论文标题
python scripts/collect_titles.py --source arxiv --year 2025

# 2. 获取论文信息（限制100篇避免API超额）
python scripts/fetch_paper_info.py --limit 100

# 3. 下载并处理PDF（限制50篇节省空间和时间）
python scripts/process_pdfs.py --limit 50

# 4. AI分析论文相关性（限制20篇控制成本）
python scripts/analyze_papers.py --limit 20
```

## 数据

所有数据保存在 `data/papers.db` 数据库中。

**论文状态流程**：
```
pendingTitles → TobeDownloaded → processed → analyzed
```

### Web 可视化功能

- 首页按状态折叠展示论文标题列表，可展开查看
- 点击某篇论文可在浏览器中查看 PDF 预览、文本片段、相关性评分与总结
- 运行 `uvicorn web.app:app --reload`（默认 http://127.0.0.1:8000）即可打开界面

**查询相关论文**：
```sql
SELECT p.title, a.relevance_score, a.reasoning, a.summary
FROM papers p
JOIN analysis_results a ON p.id = a.paper_id
WHERE a.is_relevant = 1
ORDER BY a.relevance_score DESC;
```

## 自定义

编辑 `config.py` 中的 `RELEVANCE_TAGS` 列表来自定义筛选主题：

```python
RELEVANCE_TAGS = [
    "机器人",
    "具身智能",
    "灵巧手",
    # 添加你的关键词
]
```


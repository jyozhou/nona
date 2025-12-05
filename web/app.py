import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from config import DB_PATH, PDF_DIR, TEXT_DIR
from database import Database

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="论文管理可视化", version="1.0.0")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

db = Database(str(DB_PATH))


def _get_file_id(paper: Dict) -> str:
    return paper.get("arxiv_id") or paper.get("id")


def _load_text(file_id: str) -> Optional[str]:
    text_path = TEXT_DIR / f"{file_id}.txt"
    if text_path.exists():
        try:
            with open(text_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(text_path, "r", encoding="latin-1") as f:
                return f.read()
    return None


def _get_analysis(paper_id: str) -> Optional[Dict]:
    return db.get_analysis_result(paper_id)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    status_sections = [
        ("pendingTitles", "📄 待获取详细信息"),
        ("TobeDownloaded", "⬇️ 待下载PDF"),
        ("processed", "🧾 已处理文本"),
        ("analyzed", "✅ 已分析"),
        ("detailFailed", "⚠️ 详情获取失败"),
        ("downloadFailed", "⚠️ PDF下载失败"),
    ]

    section_data: List[Dict] = []
    for key, label in status_sections:
        papers = db.get_papers_by_status(key, limit=200)
        section_data.append(
            {
                "status": key,
                "label": label,
                "count": len(papers),
                "papers": papers,
            }
        )

    stats = db.get_statistics()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "sections": section_data,
            "stats": stats,
        },
    )


@app.get("/papers/{paper_id}", response_class=HTMLResponse)
async def paper_detail(paper_id: str, request: Request):
    paper = db.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    file_id = _get_file_id(paper)
    pdf_path = PDF_DIR / f"{file_id}.pdf"
    text_content = _load_text(file_id)
    text_preview = text_content[:5000] + "..." if text_content and len(text_content) > 5000 else text_content
    analysis = _get_analysis(paper_id)

    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "paper": paper,
            "file_id": file_id,
            "has_pdf": pdf_path.exists(),
            "text_preview": text_preview,
            "analysis": analysis,
        },
    )


@app.get("/pdf/{paper_id}")
async def serve_pdf(paper_id: str):
    paper = db.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    file_id = _get_file_id(paper)
    pdf_path = PDF_DIR / f"{file_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    headers = {"Content-Disposition": f'inline; filename="{pdf_path.name}"'}
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers=headers,
    )


@app.get("/text/{paper_id}", response_class=HTMLResponse)
async def serve_text(paper_id: str):
    paper = db.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    file_id = _get_file_id(paper)
    text_content = _load_text(file_id)
    if text_content is None:
        raise HTTPException(status_code=404, detail="Text not found")

    return HTMLResponse(text_content.replace("\n", "<br />"))



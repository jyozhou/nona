"""
SQLite数据库操作模块
提供论文数据的CRUD操作
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """数据库操作类"""
    
    def __init__(self, db_path: str):
        """初始化数据库连接"""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    arxiv_id TEXT UNIQUE,
                    pdf_url TEXT,
                    authors TEXT,
                    abstract TEXT,
                    published_date TEXT,
                    source TEXT,
                    status TEXT DEFAULT 'pendingTitles',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id TEXT NOT NULL,
                    is_relevant INTEGER DEFAULT 0,
                    relevance_score REAL DEFAULT 0.0,
                    reasoning TEXT,
                    summary TEXT,
                    analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (paper_id) REFERENCES papers(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS detail_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    source TEXT,
                    reason TEXT,
                    failed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS download_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    arxiv_id TEXT,
                    pdf_url TEXT,
                    reason TEXT,
                    failed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引以提高查询性能
            conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_paper_id ON analysis_results(paper_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_detail_failures_time ON detail_failures(failed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_download_failures_time ON download_failures(failed_at)")

            self._migrate_status_names(conn)
            conn.commit()
            logger.info("Database initialized successfully")
    
    def insert_paper(self, paper_data: Dict) -> bool:
        """
        插入论文记录
        
        Args:
            paper_data: 论文数据字典
            
        Returns:
            是否插入成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 生成ID（优先使用arxiv_id，否则使用title的hash）
                paper_id = paper_data.get('arxiv_id') or str(hash(paper_data['title']))
                
                conn.execute("""
                    INSERT OR IGNORE INTO papers 
                    (id, title, arxiv_id, pdf_url, authors, abstract, published_date, source, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paper_id,
                    paper_data.get('title'),
                    paper_data.get('arxiv_id'),
                    paper_data.get('pdf_url'),
                    json.dumps(paper_data.get('authors', [])),
                    paper_data.get('abstract'),
                    paper_data.get('published_date'),
                    paper_data.get('source'),
                    paper_data.get('status', 'pendingTitles')
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting paper: {e}")
            return False
    
    def batch_insert_papers(self, papers: List[Dict]) -> int:
        """
        批量插入论文记录
        
        Args:
            papers: 论文数据列表
            
        Returns:
            成功插入的数量
        """
        count = 0
        for paper in papers:
            if self.insert_paper(paper):
                count += 1
        logger.info(f"Batch inserted {count}/{len(papers)} papers")
        return count
    
    def get_paper_by_id(self, paper_id: str) -> Optional[Dict]:
        """根据ID获取论文"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None

    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict]:
        """根据arXiv ID获取论文"""
        if not arxiv_id:
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None
    
    def get_papers_by_status(self, status: str, limit: int = None) -> List[Dict]:
        """
        根据状态获取论文列表
        
        Args:
        status: 论文状态 (pendingTitles, TobeDownloaded, processed, analyzed)
            limit: 返回数量限制
            
        Returns:
            论文列表
        """
        query = "SELECT * FROM papers WHERE status = ?"
        params = [status]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def update_paper_status(self, paper_id: str, status: str) -> bool:
        """更新论文状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE papers SET status = ? WHERE id = ?",
                    (status, paper_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating paper status: {e}")
            return False
    
    def update_paper_info(self, paper_id: str, updates: Dict) -> bool:
        """更新论文信息"""
        try:
            # 构建更新语句
            normalized_updates = dict(updates)
            if "authors" in normalized_updates and isinstance(normalized_updates["authors"], list):
                normalized_updates["authors"] = json.dumps(normalized_updates["authors"])

            set_clause = ", ".join([f"{key} = ?" for key in normalized_updates.keys()])
            values = list(normalized_updates.values()) + [paper_id]
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"UPDATE papers SET {set_clause} WHERE id = ?",
                    values
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating paper info: {e}")
            return False
    
    def insert_analysis_result(self, result_data: Dict) -> bool:
        """插入分析结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO analysis_results 
                    (paper_id, is_relevant, relevance_score, reasoning, summary)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    result_data['paper_id'],
                    result_data.get('is_relevant', 0),
                    result_data.get('relevance_score', 0.0),
                    result_data.get('reasoning'),
                    result_data.get('summary')
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting analysis result: {e}")
            return False
    
    def get_analysis_result(self, paper_id: str) -> Optional[Dict]:
        """获取论文的分析结果"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM analysis_results WHERE paper_id = ? ORDER BY analyzed_at DESC LIMIT 1",
                (paper_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    def get_relevant_papers(self, min_score: float = 0.5) -> List[Dict]:
        """获取相关的论文列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT p.*, a.relevance_score, a.reasoning, a.summary
                FROM papers p
                JOIN analysis_results a ON p.id = a.paper_id
                WHERE a.is_relevant = 1 AND a.relevance_score >= ?
                ORDER BY a.relevance_score DESC
            """, (min_score,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            # 总论文数
            total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            
            # 各状态的论文数
            status_counts = {}
            for row in conn.execute("SELECT status, COUNT(*) as count FROM papers GROUP BY status"):
                status_counts[row[0]] = row[1]
            
            # 已分析的论文数
            analyzed = conn.execute("SELECT COUNT(*) FROM analysis_results").fetchone()[0]
            
            # 相关论文数
            relevant = conn.execute(
                "SELECT COUNT(*) FROM analysis_results WHERE is_relevant = 1"
            ).fetchone()[0]

            detail_failures = conn.execute("SELECT COUNT(*) FROM detail_failures").fetchone()[0]
            download_failures = conn.execute("SELECT COUNT(*) FROM download_failures").fetchone()[0]
            
            return {
                "total_papers": total,
                "status_counts": status_counts,
                "analyzed_papers": analyzed,
                "relevant_papers": relevant,
                "failure_counts": {
                    "detail_failures": detail_failures,
                    "download_failures": download_failures,
                },
            }

    def delete_paper(self, paper_id: str) -> bool:
        """删除论文记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting paper: {e}")
            return False

    def record_detail_failure(self, paper_id: str, title: str, source: Optional[str] = None, reason: str = "") -> None:
        """记录获取详细信息失败"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO detail_failures (paper_id, title, source, reason, failed_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(paper_id) DO UPDATE SET
                    title=excluded.title,
                    source=excluded.source,
                    reason=excluded.reason,
                    failed_at=CURRENT_TIMESTAMP
                """,
                (paper_id, title, source, reason),
            )
            conn.commit()

    def record_download_failure(
        self,
        paper_id: str,
        title: str,
        arxiv_id: Optional[str],
        pdf_url: Optional[str],
        reason: str = "",
    ) -> None:
        """记录PDF下载失败"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO download_failures (paper_id, title, arxiv_id, pdf_url, reason, failed_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(paper_id) DO UPDATE SET
                    title=excluded.title,
                    arxiv_id=excluded.arxiv_id,
                    pdf_url=excluded.pdf_url,
                    reason=excluded.reason,
                    failed_at=CURRENT_TIMESTAMP
                """,
                (paper_id, title, arxiv_id, pdf_url, reason),
            )
            conn.commit()

    def get_detail_failures(self, limit: Optional[int] = None) -> List[Dict]:
        """获取详细信息失败列表"""
        query = "SELECT * FROM detail_failures ORDER BY failed_at DESC"
        params: List = []

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_download_failures(self, limit: Optional[int] = None) -> List[Dict]:
        """获取PDF下载失败列表"""
        query = "SELECT * FROM download_failures ORDER BY failed_at DESC"
        params: List = []

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def remove_detail_failure(self, paper_id: str) -> None:
        """移除指定论文的详细信息失败记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM detail_failures WHERE paper_id = ?", (paper_id,))
            conn.commit()

    def remove_download_failure(self, paper_id: str) -> None:
        """移除指定论文的PDF下载失败记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM download_failures WHERE paper_id = ?", (paper_id,))
            conn.commit()

    def _migrate_status_names(self, conn: sqlite3.Connection) -> None:
        """迁移旧的状态命名"""
        try:
            conn.execute("UPDATE papers SET status='pendingTitles' WHERE status='pending'")
            conn.execute("UPDATE papers SET status='TobeDownloaded' WHERE status='downloaded'")
        except sqlite3.OperationalError as exc:
            logger.debug("Status migration skipped: %s", exc)


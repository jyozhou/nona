"""
标题去重脚本
在数据库中按 title 去重，保留一条代表记录，其余重复记录删除

策略：
- 先按 title 分组，找到 count > 1 的标题
- 对于每个重复标题：
  - 优先保留 arxiv_id 不为空的记录
  - 在同等条件下，保留 created_at 最早的一条
  - 其余记录全部删除

默认仅打印（dry-run），需要实际执行删除时加 --apply
"""

import sys
from pathlib import Path
import sqlite3
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH


def deduplicate_titles(apply: bool = False) -> None:
    db_path = str(DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print("=" * 80)
    print("标题去重")
    print("=" * 80)
    print(f"数据库: {db_path}")
    print(f"模式: {'实际删除(执行)' if apply else '仅预览(dry-run)'}")

    # 找出所有有重复的标题
    dup_titles = conn.execute(
        """
        SELECT title, COUNT(*) AS cnt
        FROM papers
        GROUP BY title
        HAVING cnt > 1
        ORDER BY cnt DESC
        """
    ).fetchall()

    if not dup_titles:
        print("未发现重复标题，数据库已是去重状态。")
        conn.close()
        return

    print(f"发现 {len(dup_titles)} 个存在重复的标题。\n")

    total_deleted = 0

    for row in dup_titles:
        title = row["title"]
        cnt = row["cnt"]

        # 取出该标题的所有记录，优先 arxiv_id 非空，其次 created_at 早
        records: List[sqlite3.Row] = conn.execute(
            """
            SELECT *
            FROM papers
            WHERE title = ?
            ORDER BY (arxiv_id IS NOT NULL) DESC, created_at ASC
            """,
            (title,),
        ).fetchall()

        if len(records) <= 1:
            continue

        keep = records[0]
        to_delete = records[1:]

        print("-" * 80)
        print(f"标题: {title!r}  (共 {cnt} 条，保留 1 条，删除 {cnt - 1} 条)")
        print(
            f"  保留: id={keep['id']}, arxiv_id={keep['arxiv_id']}, "
            f"status={keep['status']}, created_at={keep['created_at']}"
        )

        for rec in to_delete:
            print(
                f"  删除: id={rec['id']}, arxiv_id={rec['arxiv_id']}, "
                f"status={rec['status']}, created_at={rec['created_at']}"
            )

        if apply:
            ids = [(rec["id"],) for rec in to_delete]
            conn.executemany("DELETE FROM papers WHERE id = ?", ids)
            total_deleted += len(ids)

    if apply and total_deleted:
        conn.commit()

    print("\n" + "=" * 80)
    if apply:
        print(f"✓ 去重完成，共删除 {total_deleted} 条重复记录。")
    else:
        print("预览完成。未执行删除，如需实际删除请使用:")
        print("  python scripts/deduplicate_titles.py --apply")
    print("=" * 80)

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="按标题去重 papers 表")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际执行删除（默认仅预览，不修改数据库）",
    )

    args = parser.parse_args()
    deduplicate_titles(apply=args.apply)



"""
列出获取论文详细信息失败的条目标题。

这些条目可通过 scripts/retry_failures.py --type detail 重新加入 pendingTitles 队列。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH
from database import Database


def main() -> int:
    parser = argparse.ArgumentParser(description="列出获取详情失败的论文标题")
    parser.add_argument("--limit", type=int, default=None, help="最多显示多少条")
    parser.add_argument(
        "--with-reason",
        action="store_true",
        help="同时显示失败原因和失败时间",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="只输出标题，便于重定向或复制",
    )
    args = parser.parse_args()

    db = Database(str(DB_PATH))
    failures = db.get_detail_failures(args.limit)

    if not failures:
        print("没有获取详情失败的条目。")
        return 0

    if not args.plain:
        print(f"获取详情失败条目数: {len(failures)}")
        print("=" * 80)

    for index, failure in enumerate(failures, 1):
        title = failure.get("title", "")
        if args.plain:
            print(title)
            continue

        source = failure.get("source") or "unknown"
        print(f"{index}. [{source}] {title}")

        if args.with_reason:
            reason = failure.get("reason") or "未记录"
            failed_at = failure.get("failed_at") or "unknown"
            print(f"   failed_at: {failed_at}")
            print(f"   reason: {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

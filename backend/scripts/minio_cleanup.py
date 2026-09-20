"""MinIO 清理：web-tests 孤儿 + 超保留期报告产物

删除集合 = web-tests/ 下满足任一条件的对象：
  1. 孤儿（不被任何 DB 列引用）
  2. 报告产物（report-*.zip / test-report-*.zip / *report*.html）且超过保留期

保护（绝不删除）：
  - test-script.* / test-plan.* / test-cases.json（测试定义本体）——除非已是孤儿
  - screenshots_path 前缀下的截图（web_test_runs 仍引用）
  - /storage-state/ 下的登录态与失败截图
  - documents/、api-tests/、scenario-reports/ 前缀（只报告）

DB 联动（对已删除且被引用的对象）：
  - web_test_runs / test_run_script_jobs / test_run_execution_snapshot_jobs
    的 report_path 置 NULL
  - attachments 中 object_name 匹配的行删除

用法：
  python backend/scripts/minio_cleanup.py             # dry-run
  python backend/scripts/minio_cleanup.py --apply     # 执行（保留期默认 7 天）
  python backend/scripts/minio_cleanup.py --apply --days 30
"""
import argparse
import os
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from minio import Minio
from minio.deleteobjects import DeleteObject

REF_COLUMNS = [
    ("attachments", "object_name", False),
    ("web_tests", "script_path", False),
    ("web_test_runs", "report_path", False),
    ("web_test_runs", "screenshots_path", True),
    ("web_test_results", "screenshot_path", False),
    ("android_tests", "script_path", False),
    ("android_test_runs", "report_path", False),
    ("android_test_runs", "screenshots_path", True),
    ("android_test_results", "screenshot_path", False),
    ("api_tests", "script_path", False),
    ("api_tests", "schema_path", False),
    ("api_test_runs", "report_path", False),
    ("pentest_reports", "file_path", False),
    ("scenario_runs", "report_path", False),
    ("test_run_script_jobs", "report_path", False),
    ("test_run_execution_snapshot_jobs", "report_path", False),
    ("storage_state_jobs", "output_path", False),
]

REPORT_PATH_TABLES = [
    "web_test_runs",
    "test_run_script_jobs",
    "test_run_execution_snapshot_jobs",
]

REPORT_ZIP = re.compile(r"(^|/)(test-)?report-[^/]*\.zip$")
REPORT_HTML = re.compile(r"(^|/)(test-report-[^/]*\.html|report\.html)$")


def is_report_artifact(name: str) -> bool:
    return bool(REPORT_ZIP.search(name) or REPORT_HTML.search(name))


def load_references(conn):
    exact, prefixes = set(), set()
    for table, column, is_prefix in REF_COLUMNS:
        try:
            with conn.cursor() as cur:
                cur.execute(f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL')
                rows = [r[0] for r in cur.fetchall() if r[0]]
        except psycopg2.Error as e:
            conn.rollback()
            print(f"[warn] 查询 {table}.{column} 失败: {e.pgerror or e}")
            continue
        (prefixes if is_prefix else exact).update(rows)
    return exact, prefixes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际执行（默认 dry-run）")
    parser.add_argument("--days", type=int, default=7, help="报告保留天数（默认 7）")
    args = parser.parse_args()

    conn = psycopg2.connect(os.environ["POSTGRES_URI"])
    exact_refs, prefix_refs = load_references(conn)
    print(f"DB 引用: 精确 {len(exact_refs)} 条, 前缀 {len(prefix_refs)} 条")

    client = Minio(
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = os.environ.get("MINIO_BUCKET", "test-management")
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    delete_set = {}   # name -> size
    reasons = defaultdict(lambda: [0, 0])

    for obj in client.list_objects(bucket, prefix="web-tests/", recursive=True):
        name, size = obj.object_name, obj.size or 0
        referenced = name in exact_refs or any(name.startswith(p) for p in prefix_refs)
        protected = (
            "/storage-state/" in name
            or any(name.startswith(p) for p in prefix_refs)
        )
        if not referenced and not protected:
            delete_set[name] = size
            reasons["孤儿"][0] += 1
            reasons["孤儿"][1] += size
        elif is_report_artifact(name) and obj.last_modified < cutoff and not protected:
            delete_set[name] = size
            reasons[f"超{args.days}天报告"][0] += 1
            reasons[f"超{args.days}天报告"][1] += size

    total = sum(delete_set.values())
    print(f"\n待删除: {len(delete_set)} 个对象, {total/1024/1024:.1f} MB")
    for r, (n, s) in reasons.items():
        print(f"  {r}: {n} 个, {s/1024/1024:.1f} MB")

    if not delete_set:
        print("无可删除对象。")
        conn.close()
        return

    if not args.apply:
        print("\n[dry-run] 未执行。确认后加 --apply。")
        for name, size in sorted(delete_set.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {size/1024/1024:>8.1f} MB  {name}")
        conn.close()
        return

    # 1. 删除 MinIO 对象
    errors = list(client.remove_objects(bucket, [DeleteObject(n) for n in delete_set]))
    failed = {e.object_name for e in errors}
    deleted = [n for n in delete_set if n not in failed]
    freed = sum(delete_set[n] for n in deleted)
    print(f"\nMinIO 删除: 成功 {len(deleted)}/{len(delete_set)}, 释放 {freed/1024/1024:.1f} MB")
    if errors:
        print(f"[warn] {len(errors)} 个失败:")
        for e in errors[:10]:
            print(f"  {e.object_name}: {e.message}")

    # 2. DB 联动清理（仅针对删除成功的对象）
    if deleted:
        with conn.cursor() as cur:
            for table in REPORT_PATH_TABLES:
                cur.execute(
                    f'UPDATE "{table}" SET report_path = NULL WHERE report_path = ANY(%s)',
                    (deleted,),
                )
                if cur.rowcount:
                    print(f"  {table}.report_path 置空: {cur.rowcount} 行")
            cur.execute(
                "DELETE FROM attachments WHERE object_name = ANY(%s)",
                (deleted,),
            )
            if cur.rowcount:
                print(f"  attachments 清理: {cur.rowcount} 行")
        conn.commit()
    conn.close()
    print("完成。")


if __name__ == "__main__":
    main()

"""清理系统库中同 case_number 的重复测试用例（保留最新一条）。

背景：早期"纯新建"入库会产生多条同编号记录，导致 upsert 按编号查重时
多行命中（MultipleResultsFound → HTTP 500，相关用例无法入库）。
repo 层已修复为 latest-wins（test_case_repo.get_by_identifier 按
created_at 倒序取第一条），本脚本用于一次性清理存量重复数据。

用法（在 backend 目录下，用项目 venv 执行）：
    python scripts/cleanup_duplicate_case_numbers.py                 # dry-run，只报告
    python scripts/cleanup_duplicate_case_numbers.py --apply         # 实际删除
    python scripts/cleanup_duplicate_case_numbers.py --project PR-2  # 只处理指定项目

规则：
- 按 (project_id, case_number) 分组，保留 created_at 最新的一条
- 较旧副本若被 test_run_test_cases / api_tests / web_tests 引用 → 跳过并报告（不删）
- 无引用的旧副本 → 删除（steps 等关联行随 ORM 级联删除）
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

# 允许以脚本方式直接运行（python scripts/xxx.py）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 控制台默认 GBK，打印 emoji/特殊字符会 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, Exception):
    pass

from sqlalchemy import func, select

from app.config.database import async_session_factory
from app.models.test_case import TestCase


async def find_duplicate_groups(session, project_identifier: str | None):
    """按 (project_id, case_number) 找出有重复的分组，返回 {key: [TestCase...]}（按创建时间倒序）。"""
    stmt = (
        select(TestCase.project_id, TestCase.case_number, func.count().label("cnt"))
        .where(TestCase.case_number.isnot(None))
        .group_by(TestCase.project_id, TestCase.case_number)
        .having(func.count() > 1)
    )
    if project_identifier:
        from app.models.project import Project

        proj = await session.execute(
            select(Project.id).where(Project.identifier == project_identifier)
        )
        project_id = proj.scalar_one_or_none()
        if project_id is None:
            print(f"⚠️ 项目 {project_identifier} 不存在，无操作")
            return {}
        stmt = stmt.where(TestCase.project_id == project_id)

    groups: dict[tuple, list] = {}
    rows = (await session.execute(stmt)).all()
    for project_id, case_number, _cnt in rows:
        cases = (
            (
                await session.execute(
                    select(TestCase)
                    .where(TestCase.project_id == project_id)
                    .where(TestCase.case_number == case_number)
                    .order_by(TestCase.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        groups[(project_id, case_number)] = list(cases)
    return groups


async def reference_counts(session, test_case_id) -> dict[str, int]:
    """统计一条用例被 run / api_tests / web_tests 引用的数量。"""
    from app.models.api_test import APITest
    from app.models.test_run import TestRunTestCase
    from app.models.web_test import WebTest

    counts = {}
    for label, model, column in (
        ("test_runs", TestRunTestCase, TestRunTestCase.test_case_id),
        ("api_tests", APITest, APITest.test_case_id),
        ("web_tests", WebTest, WebTest.test_case_id),
    ):
        result = await session.execute(
            select(func.count()).select_from(model).where(column == test_case_id)
        )
        counts[label] = result.scalar_one()
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="实际执行删除（默认为 dry-run 只报告）")
    parser.add_argument("--project", help="只处理指定项目（identifier），默认全部项目")
    args = parser.parse_args()

    async with async_session_factory() as session:
        groups = await find_duplicate_groups(session, args.project)
        if not groups:
            print("✅ 未发现同编号重复用例")
            return

        total_duplicates = 0
        deleted = 0
        skipped: list[tuple[str, dict]] = []

        for (project_id, case_number), cases in sorted(groups.items(), key=lambda x: str(x[0])):
            keep = cases[0]  # created_at 最新
            duplicates = cases[1:]
            total_duplicates += len(duplicates)
            print(f"\n📌 {case_number}（共 {len(cases)} 条，保留最新 {keep.created_at}）")

            for dup in duplicates:
                refs = await reference_counts(session, dup.id)
                if any(refs.values()):
                    skipped.append((case_number, refs))
                    print(f"   ⏭️  跳过 {dup.id}（{dup.created_at}）：被引用 {refs}")
                    continue
                print(f"   🗑️  {'删除' if args.apply else '将删除'} {dup.id}（{dup.created_at}）")
                if args.apply:
                    await session.delete(dup)
                    deleted += 1

        print("\n" + "=" * 60)
        print(f"重复分组：{len(groups)} 个；多余副本：{total_duplicates} 条")
        if args.apply:
            await session.commit()
            print(f"✅ 已删除 {deleted} 条无引用副本；{len(skipped)} 条因被引用而跳过")
        else:
            print(f"（dry-run）将删除 {total_duplicates - len(skipped)} 条；"
                  f"{len(skipped)} 条因被引用将跳过。加 --apply 实际执行")
        if skipped:
            print("\n被引用而跳过的副本（需人工在前台处理）：")
            for case_number, refs in skipped:
                print(f"  - {case_number}: {refs}")


if __name__ == "__main__":
    asyncio.run(main())

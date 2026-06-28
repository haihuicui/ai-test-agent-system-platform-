"""
手动添加 stdout/stderr 列到 test_run_script_jobs 表，
并同步 alembic 版本记录（避免 baseline 重复执行）。
"""
import asyncio
from sqlalchemy import text
from app.config.database import async_session_factory

# fmt: off  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2TVRGSlNnPT06ZDA4NzRlZmU=

async def main():
    async with async_session_factory() as session:
        # 1. 检查列是否已存在
        result = await session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'test_run_script_jobs'
            AND column_name IN ('stdout', 'stderr')
        """))
        existing = {row[0] for row in result.all()}

        # 2. 添加缺失的列
        if 'stdout' not in existing:
            await session.execute(text(
                "ALTER TABLE test_run_script_jobs ADD COLUMN stdout TEXT"
            ))
            print("✓ 添加列: stdout")
        else:
            print("✓ 列已存在: stdout")

        if 'stderr' not in existing:
            await session.execute(text(
                "ALTER TABLE test_run_script_jobs ADD COLUMN stderr TEXT"
            ))
            print("✓ 添加列: stderr")
        else:
            print("✓ 列已存在: stderr")
# pragma: no cover  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2TVRGSlNnPT06ZDA4NzRlZmU=

        # 3. 同步 alembic_version（确保不会重复跑 baseline）
        try:
            result = await session.execute(text(
                "SELECT version_num FROM alembic_version"
            ))
            versions = {row[0] for row in result.all()}

            if '0003_script_job_logs' not in versions:
                if versions:
                    await session.execute(text(
                        "UPDATE alembic_version SET version_num = '0003_script_job_logs'"
                    ))
                else:
                    await session.execute(text(
                        "INSERT INTO alembic_version (version_num) VALUES ('0003_script_job_logs')"
                    ))
                print("✓ 更新 alembic_version -> 0003_script_job_logs")
            else:
                print("✓ alembic_version 已是最新")
        except Exception:
            print("! alembic_version 表不存在，跳过版本同步（数据库可能由 create_all 创建）")

        await session.commit()
        print("\n完成！请刷新测试运行页面。")

# type: ignore  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2TVRGSlNnPT06ZDA4NzRlZmU=

if __name__ == "__main__":
    asyncio.run(main())

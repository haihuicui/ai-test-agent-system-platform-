"""add_scenario_step 并行调用行锁回归验证（一次性脚本，验证后删除临时场景）。

复现方式：模拟 AI 同消息并行发起 N 个 add_scenario_step 工具调用（不传
step_order），验证修复后 total_steps == N 且 step_order 为 1..N 无重复。

运行（仓库根目录）：
  backend/.venv/Scripts/python.exe backend/scripts/verify_add_step_concurrency.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.tools.api.scenario_tools import create_test_scenario, add_scenario_step
from app.config.database import async_session_factory
from app.models.test_scenario import TestScenario, ScenarioStep
from sqlalchemy import select, delete

PROJECT_IDENTIFIER = "PR-1"
ENDPOINT_ID = "1730f052-6217-4428-a357-4eb63bba349e"
PARALLEL = 6


async def main():
    conv_id = "verify-concurrency-001"

    # 1. 创建临时场景
    raw = await create_test_scenario.ainvoke(
        {"project_identifier": PROJECT_IDENTIFIER, "name": "并发锁验证-临时场景"},
        config={"configurable": {"conversation_id": conv_id}},
    )
    resp = json.loads(raw)
    assert resp["success"], resp
    scenario_id = resp["data"]["scenario_id"]
    print(f"临时场景: {resp['data']['identifier']} ({scenario_id})")

    try:
        # 2. 并行发起 N 个 add_scenario_step（不传 step_order，模拟最坏竞争）
        results = await asyncio.gather(*[
            add_scenario_step.ainvoke(
                {
                    "scenario_id": scenario_id,
                    "endpoint_id": ENDPOINT_ID,
                    "name": f"并发步骤-{i}",
                },
                config={"configurable": {"conversation_id": conv_id}},
            )
            for i in range(PARALLEL)
        ])
        for i, r in enumerate(results):
            parsed = json.loads(r)
            assert parsed["success"], f"第 {i} 个调用失败: {parsed}"

        # 3. 校验最终状态
        async with async_session_factory() as session:
            s = await session.execute(
                select(TestScenario).where(TestScenario.id == scenario_id)
            )
            scenario = s.scalar_one()
            steps = (
                await session.execute(
                    select(ScenarioStep)
                    .where(ScenarioStep.scenario_id == scenario_id)
                    .order_by(ScenarioStep.step_order)
                )
            ).scalars().all()

        orders = [st.step_order for st in steps]
        print(f"total_steps = {scenario.total_steps} (期望 {PARALLEL})")
        print(f"step_order  = {orders} (期望 1..{PARALLEL} 无重复)")
        assert scenario.total_steps == PARALLEL, "total_steps 校验失败"
        assert sorted(orders) == list(range(1, PARALLEL + 1)), "step_order 校验失败"
        print("[PASS] 并行调用行锁验证通过")
    finally:
        # 4. 清理临时场景（级联删除步骤）
        async with async_session_factory() as session:
            await session.execute(
                delete(TestScenario).where(TestScenario.id == scenario_id)
            )
            await session.commit()
        print("临时场景已清理")


if __name__ == "__main__":
    asyncio.run(main())

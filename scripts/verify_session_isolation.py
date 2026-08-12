# -*- coding: utf-8 -*-
"""会话级 workspace 隔离的真实环境双会话验证。

同项目 PR-VERIFY 下并发创建两个 LangGraph 会话，各自保存内容不同的
功能矩阵，验证文件落盘到 backend/workspace/testcase/PR-VERIFY/<thread_id>/
各自独立目录且内容正确。
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from langgraph_sdk import get_client

WS = Path(__file__).parent / "backend" / "workspace" / "testcase"
PROJECT = "PR-VERIFY"
ASSISTANT = "testcase_generator_agent"
TIMEOUT_S = 720  # 单会话总超时

PROMPT_TMPL = """【系统联调验证，直接执行，不要走需求分析/评审流程，不要调用其他工具】
请立即调用 save_feature_matrix_tool 保存以下功能矩阵（project_identifier 使用运行时上下文注入的当前值）：
[
  {{"id":"FP-001","module":"{module}","feature":"{feature}","test_points":["{tp1}","{tp2}"],"priority":"P0","risk_level":"高","test_type":["功能"],"source":"双会话隔离联调"}}
]
保存成功后，只需回复工具返回的 read_path，不要做任何其他事情。"""

SESSIONS = [
    ("A", "登录模块Alpha", "手机号验证码登录", "验证码有效期5分钟", "错误5次锁定30分钟"),
    ("B", "登录模块Beta", "邮箱密码登录", "密码错误3次需图形验证码", "连续失败触发滑块验证"),
]


async def wait_run(client, tid, run_id, deadline):
    while time.time() < deadline:
        run = await client.runs.get(tid, run_id)
        if run["status"] in ("success", "error", "interrupted", "timeout"):
            return run
        await asyncio.sleep(4)
    return {"status": "client_timeout"}


async def run_session(client, tag, module, feature, tp1, tp2):
    thread = await client.threads.create()
    tid = thread["thread_id"]
    log = lambda m: print(f"[会话{tag} {tid[:8]}] {m}", flush=True)
    log(f"thread 创建，目标目录 {PROJECT}/{tid}/")

    ctx = {
        "project_identifier": PROJECT,
        "folder_id": "",
        "template_type": "test_case",
        "enable_rag": False,
    }
    msg = PROMPT_TMPL.format(module=module, feature=feature, tp1=tp1, tp2=tp2)

    deadline = time.time() + TIMEOUT_S
    matrix_file = WS / PROJECT / tid / "feature_matrix.jsonl"

    run = await client.runs.create(tid, ASSISTANT, input={"messages": [{"role": "user", "content": msg}]}, context=ctx)
    log(f"run {run['run_id'][:8]} 已创建")

    for round_i in range(4):  # 最多 resume 3 次
        run = await wait_run(client, tid, run["run_id"], deadline)
        status = run["status"]
        log(f"run 状态: {status}")
        if matrix_file.exists():
            log(f"✅ 矩阵文件已出现: {matrix_file}")
            return tid, True, status
        if status == "interrupted":
            # 走了完整流程的 Phase 评审 → approve 放行到保存动作
            state = await client.threads.get_state(tid)
            interrupts = []
            for task in state.get("tasks", []) or []:
                interrupts.extend(task.get("interrupts", []) or [])
            phase = ""
            if interrupts:
                val = interrupts[0].get("value") or {}
                phase = val.get("phase", "") if isinstance(val, dict) else ""
            log(f"interrupt（phase={phase or '?'}），resume approve")
            run = await client.runs.create(
                tid, ASSISTANT,
                command={"resume": {"decision": "approve", "_phase": phase or "requirement-analysis"}},
            )
            continue
        break  # success / error / timeout
    return tid, matrix_file.exists(), status


async def main():
    client = get_client(url="http://localhost:2026")
    results = await asyncio.gather(*[
        run_session(client, *s) for s in SESSIONS
    ])

    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    all_ok = True
    for (tag, module, feature, *_), (tid, file_ok, status) in zip(SESSIONS, results):
        matrix_file = WS / PROJECT / tid / "feature_matrix.jsonl"
        print(f"\n会话{tag}: thread={tid}")
        print(f"  run 终态: {status}  文件存在: {file_ok}")
        if not file_ok:
            all_ok = False
            # 列出 PR-VERIFY 下实际目录帮助诊断
            proj_dir = WS / PROJECT
            if proj_dir.exists():
                print(f"  {PROJECT}/ 下实际内容: {[p.name for p in proj_dir.iterdir()]}")
            continue
        data = [json.loads(line) for line in matrix_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        fp = data[0] if data else {}
        content_ok = fp.get("module") == module and fp.get("feature") == feature
        print(f"  内容校验: module={fp.get('module')!r} feature={fp.get('feature')!r} -> {'✅' if content_ok else '❌'}")
        if not content_ok:
            all_ok = False

    # 隔离性：两个 thread 目录互不相同
    tids = [tid for tid, _, _ in results]
    dirs = {WS / PROJECT / tid for tid in tids}
    print(f"\n目录隔离: {len(dirs)} 个独立目录 -> {'✅' if len(dirs) == 2 else '❌'}")
    print(f"\n{'🎉 全部通过' if all_ok and len(dirs) == 2 else '❌ 验证未通过'}")


asyncio.run(main())

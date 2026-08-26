"""E2E 验证：用户提供接口造数信息 → web agent 探索期 web_api_request 验证 → 脚本 request fixture。

驱动 LangGraph HTTP API 跑一轮真实需求，自动处理意图确认/执行邀约中断，
结束后输出验证报告（web_api_request 调用、计划 API Data Setup、脚本 request fixture、执行结果）。

用法（root .venv）：
    .venv/Scripts/python.exe scripts/e2e_api_seed_verify.py
"""

import json
import sys
import time
import urllib.request

BASE = "http://localhost:2026"

REQUIREMENT = """测试客户管理菜单下的客户列表-删除客户功能（仅删除：删除列表中一条客户记录并验证列表不再显示该记录）。

造数接口（开发已确认可用，请直接用于前置数据准备，先验证再写入计划）：
- 创建客户：POST https://xmetrix-sit-15000.chromxhealth.com/api/xmetrix-data/customer
- 请求体字段：name（客户名称，必填）、description（客户描述，选填）

测试地址：https://xmetrix-sit-15000.chromxhealth.com/gz/customer-management/customers/index"""


def _req(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=60) as resp:
        body = resp.read().decode()
        return json.loads(body) if body else {}


def _wait_run(tid: str, rid: str, timeout_s: int = 1500) -> dict:
    """轮询 run 直到 success/interrupted/error。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        run = _req("GET", f"/threads/{tid}/runs/{rid}")
        status = run.get("status")
        print(f"  [run {rid[:8]}] status={status}", flush=True)
        if status in ("success", "interrupted", "error", "timeout"):
            return run
        time.sleep(20)
    raise TimeoutError(f"run {rid} 超时")


def _thread_state(tid: str) -> dict:
    return _req("GET", f"/threads/{tid}/state")


def _full_messages(tid: str) -> list:
    """完整消息列表（/state 只含最新 checkpoint 的尾段，报告采集必须走 thread 详情）。"""
    return _req("GET", f"/threads/{tid}")["values"]["messages"]


def _pending_interrupt_kind(state: dict) -> str | None:
    """返回中断类型：intent / invitation / None。"""
    for task in state.get("tasks", []) or []:
        for intr in task.get("interrupts", []) or []:
            text = json.dumps(intr.get("value", ""), ensure_ascii=False)
            if "intent" in text or "意图" in text:
                return "intent"
            if "execution" in text or "执行" in text:
                return "invitation"
            return "unknown"
    return None


def main() -> int:
    existing_tid = sys.argv[1] if len(sys.argv) > 1 else None
    if existing_tid:
        tid = existing_tid
        rid = ""
        print(f"resume existing thread_id={tid}", flush=True)
    else:
        thread = _req("POST", "/threads", {})
        tid = thread["thread_id"]
        print(f"thread_id={tid}", flush=True)

        run = _req(
            "POST",
            f"/threads/{tid}/runs",
            {
                "assistant_id": "web_agent",
                "input": {"messages": [{"role": "human", "content": REQUIREMENT}]},
                "context": {"project_identifier": "PR-1"},
            },
        )
        rid = run["run_id"]

    rounds = 0
    while True:
        if rid:
            run = _wait_run(tid, rid)
            if run.get("status") in ("error", "timeout"):
                print(f"RUN FAILED: {json.dumps(run, ensure_ascii=False)[:500]}")
                return 1
        # run success ≠ 无中断：中间件 interrupt 持久化在 thread state 的 tasks 里，
        # 必须检查 pending interrupts 决定是否 resume。
        state = _thread_state(tid)
        kind = _pending_interrupt_kind(state)
        if not kind:
            break
        rounds += 1
        decision = {"intent": "expand", "invitation": "execute"}.get(kind, "expand")
        print(f">> interrupt kind={kind}, resume decision={decision}", flush=True)
        run = _req(
            "POST",
            f"/threads/{tid}/runs",
            {
                "assistant_id": "web_agent",
                "command": {"resume": {"decision": decision}},
                # resume run 必须重传 context：LangGraph 不跨 run 继承 context，
                # 缺了 project_identifier 会导致 storageState 不注入（登录态丢失）
                "context": {"project_identifier": "PR-1"},
            },
        )
        rid = run["run_id"]
        if rounds > 6:
            print("中断轮次过多，退出")
            return 1

    # ===== 验证报告 =====
    msgs = _full_messages(tid)
    report = {"thread_id": tid, "web_api_request_calls": [], "plan_api_setup": "", "script_uses_request_fixture": None, "exec_results": []}
    for m in msgs:
        if m["type"] == "ai":
            for tc in m.get("tool_calls", []):
                if tc["name"] == "web_api_request":
                    report["web_api_request_calls"].append(
                        {"args": tc["args"]}
                    )
                if tc["name"] == "save_web_test_plan":
                    content = tc["args"].get("plan_content", "")
                    if "## API Data Setup" in content:
                        idx = content.find("## API Data Setup")
                        report["plan_api_setup"] = content[idx: idx + 800]
                if tc["name"] == "save_web_test_script":
                    sc = tc["args"].get("script_content", "") or ""
                    if sc:
                        report["script_uses_request_fixture"] = "request." in sc
        elif m["type"] == "tool" and m.get("name") == "web_api_request":
            try:
                content = json.loads(m["content"])
            except Exception:
                content = {"raw": str(m["content"])[:300]}
            report["web_api_request_calls"][-1]["result"] = content
        elif m["type"] == "tool" and m.get("name") == "execute_web_script":
            try:
                content = json.loads(m["content"])
                er = content.get("execution_result", {})
                report["exec_results"].append(
                    {"success": er.get("success"), "return_code": er.get("return_code")}
                )
            except Exception:
                pass

    print("\n===== E2E 验证报告 =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = (
        len(report["web_api_request_calls"]) > 0
        and report["script_uses_request_fixture"] is True
    )
    print(f"\n结论: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

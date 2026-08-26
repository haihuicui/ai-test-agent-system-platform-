"""在线 trace 哨兵：Langfuse 生产 trace → 轨迹断言 → 违规样本自动收编。

补齐 eval 体系的在线侧缺口（此前 Langfuse 只看不评，缺陷靠人肉翻 trace）：

    Langfuse traces ──拉取──► 生成观测(generation)中还原消息历史
                            ──traj_extract.extract──► Trajectory
                            ──traj_rules 18 条红线断言──► 违规清单
                            ──含 error 的 trace 自动落盘──► dataset/trajectories/
                                                           (收编进离线回归集,只增不减)

关键实现选择：
- **走 REST API 而非 SDK**：eval 代码跑在 backend/.venv（未必装 langfuse 包），
  stdlib urllib + Basic Auth 零新增依赖；SDK 版本漂移也影响不到这里。
- **轨迹还原取「消息数最多的那次 generation 的 input」**：LangChain 回调里
  每次模型调用的 input 都是截至当时的完整消息历史，最后一次即全量轨迹——
  无需拼接多代 generation。
- **截断容错**：生产 trace 经 mask 截断（langfuse_trace_max_chars），但 mask
  只截断字符串值、不动 JSON 结构，消息列表/工具调用参数保持完整；
  个别被截坏的消息跳过不炸栈。
- **只评不拦**：在线侧是观测哨兵（报告 + 收编样本），不做实时阻断；
  门禁仍由 pre-push 的 golden 轨迹承担。

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.trace_sentry                 # 最近 24h 全部 Agent
    ./.venv/Scripts/python.exe -m tests.eval.trace_sentry --hours 72 --limit 100
    ./.venv/Scripts/python.exe -m tests.eval.trace_sentry --agent web     # 只看 web_agent
    ./.venv/Scripts/python.exe -m tests.eval.trace_sentry --no-harvest    # 只报告不收编
    ./.venv/Scripts/python.exe -m tests.eval.trace_sentry --json          # 机器可读
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.eval.traj_extract import Trajectory, detect_agent, extract
from tests.eval.traj_rules import run_rules

OUT_DIR = Path(__file__).resolve().parent / "dataset" / "trajectories"
# 收编索引：trace_id → 落盘文件名（防重复收编；同一 trace 重拉不覆盖）
INDEX_FILE = OUT_DIR / ".sentry_index.json"

# trace name 即 agent 名（with_langfuse_tracing 的 run_name）
AGENT_TRACE_NAMES = {"testcase": "testcase", "web": "web", "api": "api"}


# ── 配置与 HTTP ─────────────────────────────────────────────────────


def load_langfuse_config() -> tuple[str, str, str]:
    """从环境变量或根 .env 读 Langfuse 配置（不导入 app.config，保持 eval 独立性）。"""
    keys = ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    values = {k: os.environ.get(k) for k in keys}
    if not all(values.values()):
        env_file = Path(__file__).resolve().parents[3] / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k in keys and not values[k]:
                    values[k] = v
    missing = [k for k in keys if not values[k]]
    if missing:
        raise RuntimeError(f"缺 Langfuse 配置：{', '.join(missing)}（环境变量或根 .env）")
    host = values["LANGFUSE_HOST"].rstrip("/")  # type: ignore[union-attr]
    return host, values["LANGFUSE_PUBLIC_KEY"], values["LANGFUSE_SECRET_KEY"]  # type: ignore[return-value]


def _api_get(host: str, pk: str, sk: str, path: str, params: dict) -> dict:
    """Langfuse Public API GET（Basic Auth，urllib 零依赖）。"""
    url = f"{host}/api/public/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_recent_traces(host: str, pk: str, sk: str, hours: int, limit: int,
                        agent: str = "") -> list[dict]:
    params: dict = {
        "limit": limit,
        "fromTimestamp": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(),
    }
    if agent and agent in AGENT_TRACE_NAMES:
        params["name"] = AGENT_TRACE_NAMES[agent]
    data = _api_get(host, pk, sk, "traces", params)
    return data.get("data", [])


def fetch_generations(host: str, pk: str, sk: str, trace_id: str,
                      max_pages: int = 10) -> list[dict]:
    """拉取一个 trace 的全部 generation 观测（分页）。"""
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        data = _api_get(host, pk, sk, "observations", {
            "traceId": trace_id, "type": "GENERATION", "limit": 100, "page": page,
        })
        batch = data.get("data", [])
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


# ── trace → 消息转储 ────────────────────────────────────────────────


def _normalize_chat_message(msg: dict, idx: int) -> dict | None:
    """Langfuse generation input 里的消息（OpenAI/LangChain 两种形态）→ 转储格式。"""
    if not isinstance(msg, dict):
        return None
    role = msg.get("role") or msg.get("type") or ""
    type_map = {"system": None, "user": "HumanMessage", "human": "HumanMessage",
                "assistant": "AIMessage", "ai": "AIMessage", "tool": "ToolMessage"}
    mtype = type_map.get(str(role).lower(), None)
    if mtype is None:
        return None  # system 消息不进轨迹（规则不看系统提示）
    out: dict = {"i": idx, "type": mtype, "content": msg.get("content") or ""}
    tool_calls = msg.get("tool_calls") or []
    normalized_calls = []
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        if "function" in tc:  # OpenAI 形态：{"function": {"name":..., "arguments": str}}
            fn = tc.get("function") or {}
            normalized_calls.append({"name": fn.get("name", ""), "args": fn.get("arguments", "")})
        else:  # LangChain 形态：{"name":..., "args": dict}
            normalized_calls.append({"name": tc.get("name", ""), "args": tc.get("args", {})})
    if normalized_calls:
        out["tool_calls"] = normalized_calls
    if msg.get("name"):
        out["name"] = msg["name"]
    return out


def trace_to_messages(generations: list[dict]) -> list[dict]:
    """从 generation 观测还原全量消息历史：取消息数最多的一次模型调用的 input。

    LangChain 回调每次模型调用的 input 都是截至当时的完整消息列表，
    最大者即轨迹全集；取不到（纯工具 trace / 输入被截空）时返回空列表。
    """
    best_input: list = []
    for gen in generations:
        gen_input = gen.get("input")
        if isinstance(gen_input, list) and len(gen_input) > len(best_input):
            best_input = gen_input
    messages = []
    for idx, msg in enumerate(best_input):
        normalized = _normalize_chat_message(msg, idx)
        if normalized:
            messages.append(normalized)
    return messages


# ── 收编 ────────────────────────────────────────────────────────────


def _load_index() -> dict:
    if INDEX_FILE.is_file():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def harvest_trace(trace_id: str, agent: str, messages: list[dict], index: dict) -> str | None:
    """把含 error 违规的 trace 落盘为回归样本；已收编过则跳过。返回文件名。"""
    if trace_id in index:
        return index[trace_id]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"sentry_{agent}_{trace_id[:8]}.json"
    (OUT_DIR / filename).write_text(
        json.dumps(messages, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    index[trace_id] = filename
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return filename


# ── 主流程 ──────────────────────────────────────────────────────────


def audit_trace(host: str, pk: str, sk: str, trace: dict,
                harvest: bool, index: dict) -> dict:
    """单条 trace：还原轨迹 → 跑规则 → 视情况收编。"""
    trace_id = trace.get("id", "?")
    name = trace.get("name") or ""
    result: dict = {"trace_id": trace_id, "name": name, "violations": [],
                    "harvested": None, "note": ""}

    generations = fetch_generations(host, pk, sk, trace_id)
    messages = trace_to_messages(generations)
    if not messages:
        result["note"] = "未取到消息历史（纯工具 trace 或输入为空）"
        return result

    traj = extract(messages)
    agent = detect_agent(traj) if name not in AGENT_TRACE_NAMES.values() else \
        {v: k for k, v in AGENT_TRACE_NAMES.items()}.get(name, "unknown")
    result["agent"] = agent
    result["tool_calls"] = len(traj.calls)

    violations = run_rules(traj, agent) if agent != "unknown" else []
    result["violations"] = [
        {"rule": v.rule_id, "severity": v.severity, "message": v.message} for v in violations
    ]
    if harvest and any(v.severity == "error" for v in violations):
        result["harvested"] = harvest_trace(trace_id, agent, messages, index)
    return result


def render_text(results: list[dict], hours: int) -> str:
    lines = [f"在线 trace 哨兵（最近 {hours}h，{len(results)} 条 trace，零 token 断言）", ""]
    audited = [r for r in results if "agent" in r]
    by_rule: dict[str, int] = {}
    err_traces = 0
    harvested = 0
    for r in results:
        if "agent" not in r:
            lines.append(f"⏭️  {r['name'] or r['trace_id'][:8]}：{r['note']}")
            continue
        errs = [v for v in r["violations"] if v["severity"] == "error"]
        warns = [v for v in r["violations"] if v["severity"] == "warning"]
        for v in errs:
            by_rule[v["rule"]] = by_rule.get(v["rule"], 0) + 1
        if errs:
            err_traces += 1
        if r["harvested"]:
            harvested += 1
        status = "❌" if errs else ("⚠️" if warns else "✅")
        lines.append(
            f"{status} {r['name']:<10} {r['trace_id'][:8]} agent={r['agent']:<8} "
            f"调用 {r['tool_calls']:>3} / error {len(errs)} / warning {len(warns)}"
            + (f" → 已收编 {r['harvested']}" if r["harvested"] else "")
        )
        for v in r["violations"]:
            lines.append(f"    [{v['rule']}] {v['severity']}: {v['message']}")
    lines += ["",
              f"合计：{len(audited)} 条可评，{err_traces} 条含 error，收编 {harvested} 条新样本"]
    if by_rule:
        lines.append("error 规则分布：" + "，".join(f"{k}×{v}" for k, v in
                                                   sorted(by_rule.items(), key=lambda x: -x[1])))
    return "\n".join(lines)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="Langfuse 在线 trace 轨迹哨兵")
    parser.add_argument("--hours", type=int, default=24, help="回看窗口（小时）")
    parser.add_argument("--limit", type=int, default=50, help="最多拉取 trace 数")
    parser.add_argument("--agent", default="", choices=["", "testcase", "web", "api"])
    parser.add_argument("--no-harvest", action="store_true", help="只报告，不收编违规样本")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        host, pk, sk = load_langfuse_config()
    except RuntimeError as exc:
        print(f"⏭️  {exc}，哨兵跳过（fail-open，不影响任何主流程）")
        sys.exit(0)

    traces = fetch_recent_traces(host, pk, sk, args.hours, args.limit, args.agent)
    if not traces:
        print(f"最近 {args.hours}h 无 trace（{host}）")
        sys.exit(0)

    index = _load_index()
    results = [audit_trace(host, pk, sk, t, not args.no_harvest, index) for t in traces]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        print(render_text(results, args.hours))


if __name__ == "__main__":
    main()

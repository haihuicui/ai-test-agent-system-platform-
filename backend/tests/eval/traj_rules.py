"""轨迹规则：把三个 Agent 系统提示词里的「流程红线」翻译为零 token 断言。

每条规则对应提示词中一条可判定的纪律（"必须先 X""禁止 Y""上限 N 次"），
只依赖 Trajectory（工具调用序列 + 消息文本），不调用 LLM、不做文件 I/O。

规则分级与 lint_cases 对齐：
- error   违反必导致交付物不可信/流程失控（门禁可拦截）
- warning 纪律瑕疵（统计观察用， golden 样本可容忍）

规则 ID 命名：{AGENT}-T{序号}，与维度地图（DIMENSIONS.md）第三层并列。
每条规则的 docstring/描述里注明提示词出处，prompt 改版时同步维护
（双载体纪律：与 testcase 评审规则双载体同理，见 README 红线）。

注意：轨迹审计评的是「过程是否合规」，与运行时中间件拦截互补——
中间件拦住的违规不会体现在轨迹里（调用被剥离），所以这里的违规
都是**绕过防线真实发生过**的事件，权重更高。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from tests.eval.traj_extract import ToolCall, Trajectory


@dataclass
class Violation:
    rule_id: str
    severity: str           # "error" | "warning"
    message: str
    msg_index: int | None = None  # 事发消息下标（定位用）


@dataclass
class Rule:
    rule_id: str
    agent: str              # testcase / web / api
    severity: str
    description: str        # 提示词出处 + 规则含义
    check: Callable[[Trajectory], list[Violation]]


# ============================================================================
# 通用小工具
# ============================================================================

def _invitation_then_decision(traj: Trajectory, before_msg_index: int) -> bool:
    """指定消息之前是否已获得用户执行许可。

    三种证据形态（满足其一即可）：
    1. 完整闭环：邀约标记 + 其后的 Human 消息（离线 thread dump 可见全程）；
    2. 仅决策消息：Human 消息含「[执行邀约」前缀（Langfuse 在线 trace 以 run 为
       单位，resume 产生的执行 run 是新 trace——邀约标记在上一条 trace 里，
       本 trace 只有决策消息与执行调用，不应误判为绕过门禁）；
    3. 直接执行指令：最近的 Human 消息本身含执行意图（前端执行入口
       「请执行测试脚本 Script ID: xxx」——用户主动发起即许可，不走邀约流）。
    """
    nearest_human = None
    for i, text in traj.human_texts:
        if i >= before_msg_index:
            break
        nearest_human = text
        if text.lstrip().startswith("[执行邀约"):
            return True
    if nearest_human and any(kw in nearest_human for kw in ("执行", "运行", "run ")):
        return True
    for inv_idx in traj.invitation_positions():
        if inv_idx >= before_msg_index:
            continue
        after = traj.human_after(inv_idx)
        if after is not None and after[0] < before_msg_index:
            return True
    return False


# ============================================================================
# testcase agent 规则
# ============================================================================

def tc_t01_first_call_is_todos(traj: Trajectory) -> list[Violation]:
    """SYSTEM_PROMPT 铁律 3：收到需求后第一条工具调用必须是 write_todos
    （PDF 附件场景例外：parse_document_from_url 优先）。

    三类豁免（生产 trace 实证）：
    - 摘要续跑：首条 human 是 summarization 注入（"has been summarized"），
      首调用发生在压缩前，轨迹不可判；
    - 直接指令：首条 human 显式点名调用某工具（"请直接调用 rag_query_data…"），
      用户指令优先于阶段流程；
    - 意图路由：IntentRouterMiddleware 放行简单任务（纯导出/评审等），
      全轨迹无任何阶段产物工具时不适用本规则。
    """
    if len(traj.calls) < 2:
        return []  # 纯问答/单工具轨迹不适用
    first = traj.first_call()
    if first is None or first.name in ("write_todos", "parse_document_from_url"):
        return []
    first_human = traj.human_texts[0][1] if traj.human_texts else ""
    if "has been summarized" in first_human:
        return []
    if first.name in first_human:
        return []  # 用户显式点名调用的工具
    phase_tools = {"write_todos", "save_feature_matrix_tool", "save_test_cases_file",
                   "batch_create_test_cases_tool", "module_self_check_tool"}
    if not any(c.name in phase_tools for c in traj.calls):
        return []  # 简单任务路径（导出/单点评审等），无阶段流程可判
    return [Violation(
        "TC-T01", "error",
        f"首个工具调用是 {first.name}，应为 write_todos（PDF 场景为 parse_document_from_url）",
        first.msg_index,
    )]


def tc_t02_pdf_parse_first(traj: Trajectory) -> list[Violation]:
    """PDF 附件优先（强制）：携带 PDF 附件提示的消息出现后，
    其后的首个工具调用必须含 parse_document_from_url。"""
    out = []
    for msg_idx, text in traj.human_texts:
        if "PDF 文件" not in text or "parse_document_from_url" in text:
            # 第二条分支排除掉「系统提示里教模型调用 parse」的注入文本被
            # 转储保留下来的情况（注入在请求侧，正常不落 state，双保险）
            continue
        if "用户上传" not in text:
            continue
        following = [c for c in traj.calls if c.msg_index > msg_idx]
        if following and following[0].name != "parse_document_from_url":
            out.append(Violation(
                "TC-T02", "error",
                f"PDF 附件消息（#{msg_idx}）之后的首个工具调用是 {following[0].name}，"
                "应为 parse_document_from_url",
                following[0].msg_index,
            ))
    return out


_SHARD_SUFFIX_RE = re.compile(r"(_p\d+|_part\d+)?\.jsonl$", re.IGNORECASE)
_SHARD_LETTER_RE = re.compile(r"(\d)[a-z]$")  # 01b/01c → 01（字母分片后缀）
_CONTENT_MODULE_RE = re.compile(r'"module"\s*:\s*"([^"]+)"')


def _module_key(call: ToolCall) -> str:
    """提取 save_test_cases_file 的模块键（生产 trace 实证的双通道）。

    1. file_path 存在 → 文件名去扩展名/分片后缀（_pN、01b→01 同组——
       分批硬约束允许单模块多次 save，自检按模块而非按 save 次数配对）；
    2. file_path 缺省（工具按模块名自动命名文件）→ 从 content 里
       用例的 module 字段提取，与自检的 expected_module 对应。
    """
    fp = str(call.args.get("file_path") or "")
    if fp:
        name = fp.rsplit("/", 1)[-1]
        name = _SHARD_SUFFIX_RE.sub("", name)
        name = _SHARD_LETTER_RE.sub(r"\1", name)
        return name
    content = call.args.get("content")
    if isinstance(content, str):
        m = _CONTENT_MODULE_RE.search(content)
        if m:
            return m.group(1)
    return fp or "?"


def tc_t03_save_then_self_check(traj: Trajectory) -> list[Violation]:
    """Phase 3 模块级 checkpoint：每批用例保存完成后、进入下一批保存或
    统一入库之前，必须调用 module_self_check_tool 覆盖该批全部模块。

    判定细节（生产 trace 实证修正）：
    - 分片同组：_pN 后缀与 01b/01c 字母后缀归并同模块；
    - 连续保存段（burst）语义：模块的多个分片/补充文件通常连续保存后
      一起自检（03 与 03_extra 同批），故按「连续 save 段」配对，
      段内每个模块键都必须被段后、下一段（或入库）前的某次自检覆盖；
    - 自检覆盖匹配：模块键出现在自检 args（input_files 路径或 expected_module）；
    - 轨迹在最后一段保存后直接结束（run 被截断/续跑）时，该段不判。
    """
    out = []
    saves = traj.calls_of("save_test_cases_file")
    if not saves:
        return out
    checks = traj.calls_of("module_self_check_tool")
    check_points = sorted(c.seq for c in checks)
    batch_seqs = [c.seq for c in traj.calls_of("batch_create_test_cases_tool")]

    # 切分连续保存段：两个 save 之间有自检即分段
    bursts: list[list[ToolCall]] = [[]]
    save_seqs = sorted(s.seq for s in saves)
    for i, save in enumerate(saves):
        bursts[-1].append(save)
        if i + 1 < len(saves):
            nxt = saves[i + 1]
            if any(save.seq < cp < nxt.seq for cp in check_points):
                bursts.append([])
    bursts = [b for b in bursts if b]

    for bi, burst in enumerate(bursts):
        burst_end = burst[-1].seq
        # 翻篇边界：下一段首次 save，或统一入库
        boundary = None
        if bi + 1 < len(bursts):
            boundary = bursts[bi + 1][0].seq
        nxt_batch = next((s for s in batch_seqs if s > burst_end), None)
        if nxt_batch is not None and (boundary is None or nxt_batch < boundary):
            boundary = nxt_batch
        if boundary is None:
            continue  # 最后一段无后续事件，run 可能被截断，不判
        # 段内每个模块键都须被 (burst_end, boundary) 间的自检覆盖
        keys = {_module_key(s) for s in burst}
        for key in keys:
            covered = any(
                burst_end < c.seq < boundary
                and key in json.dumps(c.args, ensure_ascii=False)
                for c in checks
            )
            if not covered:
                out.append(Violation(
                    "TC-T03", "error",
                    f"模块「{key}」保存后进入下一阶段/入库，未执行 module_self_check_tool",
                    burst[-1].msg_index,
                ))
    return out


def tc_t04_coverage_before_persist(traj: Trajectory) -> list[Violation]:
    """Phase 4 覆盖对照（强制）：batch_create_test_cases_tool 入库前
    必须调用过 compute_coverage_report。"""
    out = []
    for call in traj.calls_of("batch_create_test_cases_tool"):
        if not any(c.name == "compute_coverage_report" and c.seq < call.seq for c in traj.calls):
            out.append(Violation(
                "TC-T04", "error",
                "入库（batch_create_test_cases_tool）前未执行 compute_coverage_report 覆盖核对",
                call.msg_index,
            ))
    return out


def tc_t05_batch_size_limit(traj: Trajectory) -> list[Violation]:
    """分批硬约束：save_test_cases_file 单次 ≤10 条；禁止向
    batch_create_test_cases_tool 内联传入大 test_cases 列表。

    用例数统计兼容两种传参形态（生产实证）：test_cases 列表直接计数；
    content 为 JSON 字符串时按 case_number 出现次数计数（免全量解析，
    对截断/脏格式容错）。"""
    out = []

    def _count_cases(call: ToolCall) -> int:
        cases = call.args.get("test_cases") or call.args.get("cases")
        if isinstance(cases, list):
            return len(cases)
        content = call.args.get("content")
        if isinstance(content, str):
            return content.count('"case_number"')
        return 0

    for call in traj.calls_of("save_test_cases_file"):
        n = _count_cases(call)
        if n > 10:
            out.append(Violation(
                "TC-T05", "error",
                f"save_test_cases_file 单次传入约 {n} 条（硬上限 10，超出须拆分片文件）",
                call.msg_index,
            ))
    for call in traj.calls_of("batch_create_test_cases_tool"):
        cases = call.args.get("test_cases")
        if isinstance(cases, list) and cases:
            out.append(Violation(
                "TC-T05", "error",
                f"batch_create_test_cases_tool 内联传入了 {len(cases)} 条用例"
                "（禁止内联，必须走 input_file 文件清单）",
                call.msg_index,
            ))
    return out


def tc_t06_verify_citations_after_review(traj: Trajectory) -> list[Violation]:
    """隔离评审契约：adversarial-reviewer task 之后必须调用
    verify_review_citations 校验阻断举证，再整合进评审报告。"""
    tasks = [c for c in traj.calls_of("task")
             if "adversarial" in str(c.args.get("subagent_type", "")) + str(c.args.get("description", ""))]
    if not tasks:
        return []
    last_task = tasks[-1]
    if not any(c.name == "verify_review_citations" and c.seq > last_task.seq for c in traj.calls):
        return [Violation(
            "TC-T06", "error",
            "adversarial-reviewer 评审后未调用 verify_review_citations 校验阻断举证",
            last_task.msg_index,
        )]
    return []


def tc_t07_duplicate_call_spin(traj: Trajectory) -> list[Violation]:
    """重复工具调用：同工具同参数连续 ≥2 次（DuplicateToolCallMiddleware
    拦截后仍出现的模式，提示主 Agent 生成纪律问题）。"""
    out = []
    for run in traj.consecutive_same_call_runs():
        out.append(Violation(
            "TC-T07", "warning",
            f"{run[0].name} 同参数连续调用 {len(run)} 次（疑似重复发送）",
            run[0].msg_index,
        ))
    return out


# ============================================================================
# web agent 规则（红线出处：prompts/base.md）
# ============================================================================

def wb_t01_setup_before_browser(traj: Trajectory) -> list[Violation]:
    """base.md 铁律：任何 browser_* 工具前必须先 planner_setup_page
    或 generator_setup_page（每个调用段独立判定——browser_close 后重新导航需重新 setup）。"""
    out = []
    setup_done = False
    for call in traj.calls:
        if call.name in ("planner_setup_page", "generator_setup_page"):
            setup_done = True
            continue
        if call.name == "browser_close":
            setup_done = False  # base.md 崩溃恢复路径：close 后必须重新 setup
            continue
        if call.name.startswith("browser_") and not setup_done:
            out.append(Violation(
                "WB-T01", "error",
                f"{call.name} 调用前未执行 planner_setup_page/generator_setup_page",
                call.msg_index,
            ))
            setup_done = True  # 同一失控段只报一次
    return out


def wb_t02_invitation_before_execute(traj: Trajectory) -> list[Violation]:
    """execute_web_script 是唯一权威执行入口，且调用前必须完成
    EXECUTION_INVITATION 邀约 → 用户决策闭环。"""
    out = []
    for call in traj.calls_of("execute_web_script"):
        if not _invitation_then_decision(traj, call.msg_index):
            out.append(Violation(
                "WB-T02", "error",
                "execute_web_script 之前未完成「执行邀约 → 用户决策」闭环",
                call.msg_index,
            ))
    return out


def wb_t04_no_mcp_test_run_for_result(traj: Trajectory) -> list[Violation]:
    """base.md：不要用 MCP test_run / test_list 替代 execute_web_script
    获取执行结果。可判定形态：出现过 test_run/test_list，但全程无 execute_web_script。"""
    mcp_runs = traj.calls_of("test_run", "test_list")
    if mcp_runs and not traj.calls_of("execute_web_script"):
        return [Violation(
            "WB-T04", "error",
            f"使用了 MCP {mcp_runs[0].name} 且全程未走 execute_web_script"
            "（执行结果判定入口被旁路）",
            mcp_runs[0].msg_index,
        )]
    return []


def wb_t05_unsafe_code_spin(traj: Trajectory) -> list[Violation]:
    """base.md：browser_run_code_unsafe 是最后手段，连续失败 2 次后必须
    回到 browser_snapshot 重建页面认知。连续段只报一次（标注段长）。"""
    out = []
    calls = traj.calls_of("browser_run_code_unsafe")
    run_start: int | None = None
    run_len = 0
    for i in range(1, len(calls)):
        between = [c for c in traj.calls if calls[i - 1].seq < c.seq < calls[i].seq]
        if any(c.name == "browser_snapshot" for c in between):
            run_start, run_len = None, 0
            continue
        if run_start is None:
            run_start, run_len = calls[i - 1].msg_index, 2
        else:
            run_len += 1
    if run_start is not None:
        out.append(Violation(
            "WB-T05", "warning",
            f"browser_run_code_unsafe 连续使用 {run_len} 次，中间未回 browser_snapshot 重建认知",
            run_start,
        ))
    return out


def wb_t06_browser_call_spin(traj: Trajectory) -> list[Violation]:
    """连败纠偏纪律：同一 browser_* 工具同参数连续 ≥3 次（自旋收敛）。"""
    out = []
    for run in traj.consecutive_same_call_runs(name_prefix="browser_"):
        if len(run) >= 3:
            out.append(Violation(
                "WB-T06", "warning",
                f"{run[0].name} 同参数连续 {len(run)} 次（自旋，应切换策略）",
                run[0].msg_index,
            ))
    return out


# ============================================================================
# api agent 规则（红线出处：api/agent.py SYSTEM_PROMPT + _STAGE_RULES）
# ============================================================================

def api_t01_invitation_before_execute(traj: Trajectory) -> list[Violation]:
    """执行邀约（强制执行门禁）：execute_api_script / execute_scenario
    之前必须完成 EXECUTION_INVITATION → 用户决策闭环。
    （运行时中间件会硬拒无邀约执行，轨迹里出现此类调用说明防线曾被绕过或
    发生在防线生效前的历史数据——都应浮出水面。）"""
    out = []
    for call in traj.calls_of("execute_api_script", "execute_scenario"):
        if not _invitation_then_decision(traj, call.msg_index):
            out.append(Violation(
                "API-T01", "error",
                f"{call.name} 之前未完成「执行邀约 → 用户决策」闭环",
                call.msg_index,
            ))
    return out


def api_t02_audit_before_save_script(traj: Trajectory) -> list[Violation]:
    """save_test_script 保存前先 audit_script_assertions 预检。"""
    out = []
    for call in traj.calls_of("save_test_script"):
        if not any(c.name == "audit_script_assertions" and c.seq < call.seq for c in traj.calls):
            out.append(Violation(
                "API-T02", "error",
                "save_test_script 前未执行 audit_script_assertions 断言预检",
                call.msg_index,
            ))
    return out


def api_t03_skeleton_before_cases(traj: Trajectory) -> list[Violation]:
    """必须用骨架：save_test_cases 前必须 derive_test_skeleton。
    快速路径豁免：纯 GET + 无参数可跳过骨架，但 get_endpoint_details 不可省。"""
    out = []
    for call in traj.calls_of("save_test_cases"):
        prior = [c for c in traj.calls if c.seq < call.seq]
        if any(c.name == "derive_test_skeleton" for c in prior):
            continue
        if any(c.name == "get_endpoint_details" for c in prior):
            out.append(Violation(
                "API-T03", "warning",
                "save_test_cases 前未 derive_test_skeleton（仅纯 GET 快速路径允许跳过，需人工确认）",
                call.msg_index,
            ))
        else:
            out.append(Violation(
                "API-T03", "error",
                "save_test_cases 前既未 derive_test_skeleton 也未 get_endpoint_details",
                call.msg_index,
            ))
    return out


def api_t04_annotations_consumed(traj: Trajectory) -> list[Violation]:
    """红线 4：必须消费业务语义标注——save_test_cases / save_test_script
    之前必须调用过 get_endpoint_annotations。"""
    out = []
    for call in traj.calls_of("save_test_cases", "save_test_script"):
        if not any(c.name == "get_endpoint_annotations" and c.seq < call.seq for c in traj.calls):
            out.append(Violation(
                "API-T04", "error",
                f"{call.name} 前未调用 get_endpoint_annotations（业务语义标注未消费）",
                call.msg_index,
            ))
    return out


def api_t05_execute_requires_env(traj: Trajectory) -> list[Violation]:
    """红线 10：execute_api_script 必传 execution_config.env_id。"""
    out = []
    for call in traj.calls_of("execute_api_script"):
        cfg = call.args.get("execution_config")
        env_id = cfg.get("env_id") if isinstance(cfg, dict) else None
        if not env_id:
            out.append(Violation(
                "API-T05", "error",
                "execute_api_script 未传 execution_config.env_id",
                call.msg_index,
            ))
    return out


def api_t06_retry_budget(traj: Trajectory) -> list[Violation]:
    """红线 7：同一操作在同一问题上失败 ≥3 次必须切换策略。
    可判定形态：同工具同参数连续 ≥3 次且结果均为错误。"""
    out = []
    for run in traj.consecutive_same_call_runs():
        if len(run) < 3:
            continue
        errors = 0
        for call in run:
            result = next(
                (r for r in traj.results
                 if r.msg_index > call.msg_index
                 and (r.name == call.name or not r.name)),
                None,
            )
            if result and result.is_error:
                errors += 1
        if errors >= 3:
            out.append(Violation(
                "API-T06", "warning",
                f"{run[0].name} 同参数连续失败 {errors} 次仍未切换策略（重试上限 3）",
                run[0].msg_index,
            ))
    return out


# ============================================================================
# 规则注册表
# ============================================================================

RULES: list[Rule] = [
    # testcase
    Rule("TC-T01", "testcase", "error", "首工具调用必须 write_todos（PDF 场景 parse 优先）", tc_t01_first_call_is_todos),
    Rule("TC-T02", "testcase", "error", "PDF 附件消息后首调用必须 parse_document_from_url", tc_t02_pdf_parse_first),
    Rule("TC-T03", "testcase", "error", "save_test_cases_file 后必须 module_self_check_tool", tc_t03_save_then_self_check),
    Rule("TC-T04", "testcase", "error", "入库前必须 compute_coverage_report", tc_t04_coverage_before_persist),
    Rule("TC-T05", "testcase", "error", "保存分批 ≤10 条 / 入库禁内联大列表", tc_t05_batch_size_limit),
    Rule("TC-T06", "testcase", "error", "对抗评审后必须 verify_review_citations", tc_t06_verify_citations_after_review),
    Rule("TC-T07", "testcase", "warning", "同工具同参数连续重复（生成纪律）", tc_t07_duplicate_call_spin),
    # web
    Rule("WB-T01", "web", "error", "browser_* 前必须 planner/generator_setup_page", wb_t01_setup_before_browser),
    Rule("WB-T02", "web", "error", "execute_web_script 前必须邀约+用户决策", wb_t02_invitation_before_execute),
    Rule("WB-T04", "web", "error", "禁止用 MCP test_run 替代 execute_web_script 判结果", wb_t04_no_mcp_test_run_for_result),
    Rule("WB-T05", "web", "warning", "browser_run_code_unsafe 连用需回 snapshot", wb_t05_unsafe_code_spin),
    Rule("WB-T06", "web", "warning", "browser_* 同参数连续 ≥3 次（自旋）", wb_t06_browser_call_spin),
    # api
    Rule("API-T01", "api", "error", "execute_* 前必须邀约+用户决策", api_t01_invitation_before_execute),
    Rule("API-T02", "api", "error", "save_test_script 前必须 audit_script_assertions", api_t02_audit_before_save_script),
    Rule("API-T03", "api", "error", "save_test_cases 前必须骨架/端点详情", api_t03_skeleton_before_cases),
    Rule("API-T04", "api", "error", "保存前必须 get_endpoint_annotations", api_t04_annotations_consumed),
    Rule("API-T05", "api", "error", "execute_api_script 必传 env_id", api_t05_execute_requires_env),
    Rule("API-T06", "api", "warning", "同操作连续失败 ≥3 次须切换策略", api_t06_retry_budget),
]

RULES_BY_AGENT: dict[str, list[Rule]] = {}
for _rule in RULES:
    RULES_BY_AGENT.setdefault(_rule.agent, []).append(_rule)


def run_rules(traj: Trajectory, agent: str) -> list[Violation]:
    """对轨迹执行指定 Agent 的全部规则。"""
    out: list[Violation] = []
    for rule in RULES_BY_AGENT.get(agent, []):
        out.extend(rule.check(traj))
    return out

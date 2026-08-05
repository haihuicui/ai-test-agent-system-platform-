"""Tests for PhaseReviewMiddleware 的评分提取与评审轮次计算。

覆盖 _extract_quality_score（从报告文本提取综合评分）与
_compute_review_round（基于历史消息中的评审元数据计算当前轮次）。
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Overwrite

from langchain.agents.middleware.types import ToolCallRequest

from app.agents.testcase.phase_review_middleware import (
    PhaseReviewMiddleware,
    _advance_phase_todos,
    _compute_review_round,
    _detect_phase,
    _detect_phase3_coverage_gap,
    _detect_uncovered_p0,
    _extract_quality_score,
    _get_completed_phases,
    _guard_todo_status_regression,
    _has_case_preview,
    _has_coverage_mapping,
    _has_empty_suggestion_table,
)


def _review_msg(phase: str, round_: int) -> HumanMessage:
    """构造一条带评审元数据的 HumanMessage。"""
    return HumanMessage(
        content=f"[阶段评审：{phase}] 用户反馈：请修改",
        additional_kwargs={"_review_round": {"phase": phase, "round": round_}},
    )


class TestExtractQualityScore:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("综合评分：85 分", 85.0),
            ("综合评分:85分", 85.0),
            ("综合评分： 82.5 分", 82.5),
            ("评分：72 分", 72.0),
            ("质量得分 88", 88.0),
            ("质量得分：91", 91.0),
            ("综合评分：0 分", 0.0),
            ("综合评分：100 分", 100.0),
            ("报告综合评分：76 分，详见下表", 76.0),
        ],
    )
    def test_valid_scores(self, content, expected):
        assert _extract_quality_score(content) == expected

    @pytest.mark.parametrize(
        "content",
        [
            "",
            "本报告未给出评分",
            "综合评分：120 分",  # 超出 0-100 上限
            "综合评分：-5 分",   # 负号无法被 \d 匹配
            "评分：abc 分",
        ],
    )
    def test_no_valid_score(self, content):
        assert _extract_quality_score(content) is None


class TestDetectPhase:
    PHASE = "test-case-generation"

    @pytest.mark.parametrize(
        "content",
        [
            "## 测试用例生成完成",
            "✅ 测试用例生成完成",            # 回归：emoji 标题曾导致评审卡片不弹出
            "🎉 测试用例生成完成",
            "📋 用例生成汇总",
            "测试用例生成完成",                # 裸标题行
            "前文\n\n✅ 测试用例生成完成\n\n一、汇总表",  # 标题位于消息中段
        ],
    )
    def test_phase3_heading_variants(self, content):
        assert _detect_phase(content) == self.PHASE

    @pytest.mark.parametrize(
        "content",
        [
            "输出完成标记 测试用例生成完成 后等待评审",  # 行内提及，非独立标题行
            "- 测试用例生成完成：共 26 条",                # 列表项且标题后带内容
            "全部模块已设计完成，共 26 条用例",            # 无标题
        ],
    )
    def test_phase3_non_heading_not_detected(self, content):
        assert _detect_phase(content) != self.PHASE

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("✅ 需求解析报告", "requirement-analysis"),
            ("📋 功能测试矩阵", "requirement-analysis"),
            ("功能测试矩阵", "requirement-analysis"),
            ("✅ 测试策略报告", "test-strategy"),
            ("测试策略报告", "test-strategy"),
            ("📊 测试用例质量评审报告", "quality-review"),
            ("## 📊 测试用例质量评审报告", "quality-review"),
            ("✅ 输出格式化", "output-format-selection"),
            ("🎉 交付物格式选择", "output-format-selection"),
        ],
    )
    def test_other_phases_heading_variants(self, content, expected):
        """所有阶段均应识别 emoji/装饰符/裸标题行（与 Phase 3 同款兜底）。"""
        assert _detect_phase(content) == expected

    @pytest.mark.parametrize(
        "content",
        [
            "- 测试策略报告：见下文",
            "输出格式化：请选择 Markdown 或 Excel",
            "请先阅读 功能测试矩阵 再设计用例",
        ],
    )
    def test_other_phases_non_heading_not_detected(self, content):
        assert _detect_phase(content) is None


class TestAdvancePhaseTodos:
    def test_approve_completes_current_and_advances_next(self):
        state = {"todos": [
            {"content": "Phase 1: 需求分析", "status": "completed"},
            {"content": "Phase 2: 测试策略", "status": "in_progress"},
            {"content": "Phase 3: 用例设计", "status": "pending"},
        ]}
        todos = _advance_phase_todos(state, "test-strategy")["todos"]
        assert [t["status"] for t in todos] == ["completed", "completed", "in_progress"]

    def test_approve_heals_earlier_incomplete_phases(self):
        """回归：Phase 3 评审卡片未弹出时，Phase 4 通过应一并完成 Phase 3。"""
        state = {"todos": [
            {"content": "Phase 1: 需求分析", "status": "completed"},
            {"content": "Phase 2: 测试策略", "status": "completed"},
            {"content": "Phase 3: 用例设计 - 已覆盖 FP-001~FP-008", "status": "in_progress"},
            {"content": "Phase 4: 质量评审", "status": "in_progress"},
            {"content": "Phase 5: 输出格式化", "status": "pending"},
        ]}
        todos = _advance_phase_todos(state, "quality-review")["todos"]
        assert [t["status"] for t in todos] == [
            "completed", "completed", "completed", "completed", "in_progress",
        ]

    def test_no_matching_todos_returns_empty(self):
        state = {"todos": [{"content": "整理交付物", "status": "pending"}]}
        assert _advance_phase_todos(state, "quality-review") == {}

    def test_unknown_phase_returns_empty(self):
        state = {"todos": [{"content": "Phase 1: 需求分析", "status": "in_progress"}]}
        assert _advance_phase_todos(state, "output-format-selection") == {}


def _make_tool_request(tool_name: str, args: dict, state: dict) -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={"id": "call_1", "name": tool_name, "args": args},
        tool=None,
        state=state,
        runtime=None,
    )


class TestTodoStatusRegressionGuard:
    def test_completed_phase_status_preserved(self):
        """回归：评审通过后模型整表重写 todos，已完成阶段不得回退为 in_progress。"""
        state = {"todos": [
            {"content": "Phase 3: 用例设计", "status": "completed"},
            {"content": "Phase 4: 质量评审", "status": "completed"},
            {"content": "Phase 5: 输出格式化", "status": "in_progress"},
        ]}
        request = _make_tool_request("write_todos", {"todos": [
            {"content": "Phase 3: 用例设计 - 已覆盖 FP-001~FP-008", "status": "in_progress"},
            {"content": "Phase 4: 质量评审 - 综合评分 94 分，用户已通过", "status": "in_progress"},
            {"content": "Phase 5: 输出格式化", "status": "in_progress"},
        ]}, state)
        todos = _guard_todo_status_regression(request).tool_call["args"]["todos"]
        assert todos[0]["status"] == "completed"
        assert todos[1]["status"] == "completed"
        assert todos[2]["status"] == "in_progress"  # 未完成阶段不受影响

    def test_non_phase_todos_untouched(self):
        state = {"todos": [{"content": "Phase 1: 需求分析", "status": "completed"}]}
        request = _make_tool_request(
            "write_todos", {"todos": [{"content": "整理交付物", "status": "pending"}]}, state
        )
        assert _guard_todo_status_regression(request) is request  # 无回退时原样放行

    def test_other_tools_untouched(self):
        request = _make_tool_request("read_file", {"file_path": "a.jsonl"}, {"todos": []})
        assert _guard_todo_status_regression(request) is request

    def test_original_request_not_mutated(self):
        state = {"todos": [{"content": "Phase 4: 质量评审", "status": "completed"}]}
        args = {"todos": [{"content": "Phase 4: 质量评审", "status": "in_progress"}]}
        _guard_todo_status_regression(_make_tool_request("write_todos", args, state))
        assert args["todos"][0]["status"] == "in_progress"  # 入参不被原地修改


class TestComputeReviewRound:
    PHASE = "quality-review"

    def test_empty_history_is_first_round(self):
        assert _compute_review_round([], self.PHASE) == 1

    def test_messages_without_review_metadata(self):
        messages = [HumanMessage(content="请生成用例"), AIMessage(content="好的")]
        assert _compute_review_round(messages, self.PHASE) == 1

    def test_single_prior_review(self):
        messages = [_review_msg(self.PHASE, 1)]
        assert _compute_review_round(messages, self.PHASE) == 2

    def test_multiple_prior_reviews_take_max(self):
        messages = [_review_msg(self.PHASE, 1), _review_msg(self.PHASE, 2)]
        assert _compute_review_round(messages, self.PHASE) == 3

    def test_other_phase_ignored(self):
        messages = [_review_msg("requirement-analysis", 3)]
        assert _compute_review_round(messages, self.PHASE) == 1

    def test_mixed_phases_only_counts_target(self):
        messages = [_review_msg("requirement-analysis", 5), _review_msg(self.PHASE, 1)]
        assert _compute_review_round(messages, self.PHASE) == 2

    def test_malformed_metadata_ignored(self):
        messages = [
            # _review_round 不是 dict
            HumanMessage(content="x", additional_kwargs={"_review_round": "not-a-dict"}),
            # 缺 round 字段，按 0 处理
            HumanMessage(content="y", additional_kwargs={"_review_round": {"phase": self.PHASE}}),
        ]
        assert _compute_review_round(messages, self.PHASE) == 1

    def test_ai_message_metadata_ignored(self):
        messages = [
            AIMessage(
                content="x",
                additional_kwargs={"_review_round": {"phase": self.PHASE, "round": 5}},
            )
        ]
        assert _compute_review_round(messages, self.PHASE) == 1


class TestHasCasePreview:
    def test_only_summary_without_cases(self):
        content = """
## 测试用例生成完成

| 模块 | 用例数 | P0 | P1 |
|------|--------|----|----|
| 登录 | 3 | 1 | 2 |

共 3 条用例，已保存到文件。
"""
        assert _has_case_preview(content) is False

    def test_summary_with_case_details(self):
        content = """
## 测试用例生成完成

| 模块 | 用例数 | P0 | P1 |
|------|--------|----|----|
| 登录 | 3 | 1 | 2 |

### 关键用例抽样

- 用例编号：TC-PROJ-LOGIN-001
- 测试步骤：
  1. 输入用户名密码
  2. 点击登录
- 测试数据：
  ```
  username: test001
  ```
"""
        assert _has_case_preview(content) is True

    def test_chinese_field_names(self):
        content = """
## 测试用例生成完成

**用例编号**：TC-PROJ-LOGIN-001
**测试步骤**：输入用户名密码，点击登录
**测试数据**：username: test001
"""
        assert _has_case_preview(content) is True

    def test_case_number_without_steps_or_data(self):
        content = """
## 测试用例生成完成

用例编号：TC-PROJ-LOGIN-001
用例编号：TC-PROJ-LOGIN-002
"""
        assert _has_case_preview(content) is False

    def test_synonym_steps_and_data(self):
        """操作步骤/输入数据等同义词应被识别为具体用例"""
        content = """
## 测试用例生成完成

用例编号：TC-PROJ-LOGIN-001
操作步骤：输入用户名密码，点击登录
输入数据：username: test001
"""
        assert _has_case_preview(content) is True

    def test_synonym_only_case_number_and_steps(self):
        """用例编号 + 步骤（无数据）应被识别"""
        content = """
## 测试用例生成完成

用例编号：TC-PROJ-LOGIN-001
执行步骤：
  1. 输入用户名
  2. 点击登录
"""
        assert _has_case_preview(content) is True

    def test_tc_number_pattern_without_explicit_label(self):
        """未写 case_number/用例编号 字样，但出现 TC-XXX 编号 + 步骤 + 数据时应被识别"""
        content = """
## 测试用例生成完成

P0 用例：连接可用设备成功（TC-SC-CONN-007）
前置条件：设备已通电
测试数据：{"端口号": "COM1"}
步骤：①输入 COM1 ②点击连接
"""
        assert _has_case_preview(content) is True

    def test_tc_number_pattern_only_steps(self):
        """TC-XXX 编号 + 操作步骤（无测试数据）应被识别"""
        content = """
## 测试用例生成完成

边界用例：端口号输入 - 边界值（TC-SC-CONN-006）
操作步骤：
  1. 输入 1 并移出焦点
  2. 输入 65536 并移出焦点
"""
        assert _has_case_preview(content) is True

    def test_only_tc_numbers_without_steps_or_data(self):
        """仅列出 TC-XXX 编号但无步骤/数据时仍应被拦截"""
        content = """
## 测试用例生成完成

已生成用例：TC-001、TC-002、TC-003。
共 3 条用例。
"""
        assert _has_case_preview(content) is False


class TestPhaseReviewAuditabilityFallback:
    def _make_state(self, ai_content: str, human_messages: list | None = None):
        return {
            "messages": [
                *(human_messages or []),
                AIMessage(content=ai_content),
            ]
        }

    def test_phase3_without_preview_returns_request_changes(self):
        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 测试用例生成完成

| 模块 | 用例数 |
|------|--------|
| 登录 | 3 |
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        assert result.get("jump_to") == "model"

        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "系统未检测到具体用例内容" in msg.content
        assert "preview_test_cases" in msg.content
        assert "人工评审卡片" in msg.content
        assert "expected_result" in msg.content
        assert "预期结果" in msg.content

    def test_phase3_with_preview_does_not_return_fallback(self, monkeypatch):
        # 模拟 interrupt 返回 approve 决策，避免在单测环境外调用 langgraph interrupt
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 测试用例生成完成

| 模块 | 用例数 |
|------|--------|
| 登录 | 3 |

### 关键用例

- case_number: TC-PROJ-LOGIN-001
- test_case_steps: 输入用户名密码，点击登录
- test_data: username: test001
- expected_result: 页面跳转 /home
""")
        result = middleware.after_model(state, None)

        # 通过可审性检测后应走正常 interrupt 流程，返回结果中不能包含 HumanMessage fallback
        assert result is not None
        assert "messages" in result
        assert not any(
            isinstance(m, HumanMessage) and "缺少具体用例内容" in m.content
            for m in result.get("messages", [])
        )

    def test_non_phase3_title_ignored(self, monkeypatch):
        # 模拟 interrupt 返回 approve 决策
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 需求解析报告

只包含汇总信息。
""")
        result = middleware.after_model(state, None)
        # 需求分析阶段没有可审性兜底，不应返回要求补充的 HumanMessage
        assert result is not None
        assert "messages" in result
        assert not any(
            isinstance(m, HumanMessage) and "缺少具体用例内容" in m.content
            for m in result.get("messages", [])
        )


class TestHasCoverageMapping:
    """测试 Phase 4 覆盖对照表的检测逻辑。"""

    def test_mentions_feature_matrix(self):
        """条件1：提到了 feature_matrix 文件 → 通过"""
        content = """
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl，共 15 个功能点。

### 质量评分
综合评分：85 分
"""
        assert _has_coverage_mapping(content) is True

    def test_has_fp_tc_coverage_table(self):
        """条件2：包含 FP- + TC- 编号的覆盖对照表 → 通过"""
        content = """
## 📊 测试用例质量评审报告

| 功能点 ID | 模块 | 功能点 | 是否已覆盖 | 对应用例编号 |
|----------|------|--------|----------|------------|
| FP-001 | 用户认证 | 登录 | ✅ | TC-AUTH-001 |
| FP-002 | 用户认证 | 注册 | ❌ | - |

覆盖率：50%（1/2）
"""
        assert _has_coverage_mapping(content) is True

    def test_has_chinese_field_mapping(self):
        """条件2 变体：中文"功能点"+"用例编号"+"覆盖" → 通过"""
        content = """
## 📊 测试用例质量评审报告

功能点：手机号登录 → 用例编号 TC-AUTH-001 → 已覆盖
功能点：密码找回 → 未覆盖

覆盖度分析：以上 2 个功能点中有 1 个已覆盖
"""
        assert _has_coverage_mapping(content) is True

    def test_fallback_no_matrix_notation(self):
        """条件3：标注了 [无结构化矩阵] → 通过（合法降级）"""
        content = """
## 📊 测试用例质量评审报告

[无结构化矩阵] 覆盖度基于对话历史判断，可能存在遗漏。

综合评分：80 分
"""
        assert _has_coverage_mapping(content) is True

    def test_only_has_coverage_but_no_mapping(self):
        """仅有"覆盖率"字样但无 FP-/TC- 编号 → 不通过"""
        content = """
## 📊 测试用例质量评审报告

所有功能点已完整覆盖，覆盖率 100%。

综合评分：90 分
"""
        assert _has_coverage_mapping(content) is False

    def test_only_score_no_coverage_info(self):
        """仅有评分，没有任何覆盖信息 → 不通过"""
        content = """
## 📊 测试用例质量评审报告

综合评分：88 分

### 准确性检查
预期结果均可验证。
"""
        assert _has_coverage_mapping(content) is False

    def test_only_fp_no_tc(self):
        """有 FP- 编号但无 TC- 编号 → 不通过（条件2要求两者同时出现）"""
        content = """
## 📊 测试用例质量评审报告

已覆盖功能点：FP-001, FP-002, FP-003

综合评分：85 分
"""
        assert _has_coverage_mapping(content) is False

    def test_has_tc_but_no_fp(self):
        """有 TC- 编号但无 FP- 编号 → 不通过"""
        content = """
## 📊 测试用例质量评审报告

生成的用例：TC-AUTH-001 ~ TC-AUTH-020，覆盖完整。

综合评分：85 分
"""
        assert _has_coverage_mapping(content) is False


class TestPhase4CoverageFallback:
    """测试 Phase 4 覆盖对照表的兜底拦截。"""

    def _make_state(self, ai_content: str, human_messages: list | None = None):
        return {
            "messages": [
                *(human_messages or []),
                AIMessage(content=ai_content),
            ]
        }

    def test_phase4_without_coverage_mapping_returns_request_changes(self):
        """Phase 4 报告缺少覆盖对照 → 拦截要求补充"""
        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 📊 测试用例质量评审报告

所有用例质量良好，覆盖完整。

综合评分：90 分

### 准确性检查
预期结果均可验证。
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        assert result.get("jump_to") == "model"

        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "缺少功能覆盖对照信息" in msg.content
        assert "compute_coverage_report" in msg.content
        assert "逐功能点" in msg.content

    def test_phase4_with_feature_matrix_mention_passes(self, monkeypatch):
        """Phase 4 报告提到了 feature_matrix → 通过覆盖检查，进入正常 interrupt"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl，共 15 个功能点，其中 14 个已覆盖，1 个未覆盖（FP-012 退款流程）。

综合评分：88 分
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        # 不应包含兜底拦截的 HumanMessage
        assert not any(
            isinstance(m, HumanMessage) and "缺少功能覆盖对照信息" in m.content
            for m in result.get("messages", [])
        )

    def test_phase4_with_fallback_notation_passes(self, monkeypatch):
        """Phase 4 标注了 [无结构化矩阵] → 通过"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 📊 测试用例质量评审报告

[无结构化矩阵] 覆盖度基于对话历史判断，可能存在遗漏。

综合评分：80 分
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        assert not any(
            isinstance(m, HumanMessage) and "缺少功能覆盖对照信息" in m.content
            for m in result.get("messages", [])
        )


    def test_non_quality_review_phase_ignored(self, monkeypatch):
        """非 Phase 4 报告不应触发覆盖对照检查"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 需求解析报告

共 5 个模块，15 个功能点。

（这是一份 Phase 1 报告，不应触发 Phase 4 的覆盖检查）
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        assert not any(
            isinstance(m, HumanMessage) and "缺少功能覆盖对照信息" in m.content
            for m in result.get("messages", [])
        )

    def _make_low_score_state(self):
        """构造 Phase 4 低分报告 state（Phase 3 已评审，避免跳步检测优先拦截）。"""
        return self._make_state(
            """
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl。覆盖率 60%（9/15）。

| FP-001 | 用户认证 | 登录 | P0 | ✅ | TC-AUTH-001 |
| FP-002 | 用户认证 | 注册 | P0 | ❌ | - |

综合评分：60 分
""",
            human_messages=[
                HumanMessage(
                    content="[阶段评审：test-case-generation] 用户反馈：已确认",
                    additional_kwargs={
                        "_review_round": {
                            "phase": "test-case-generation",
                            "round": 1,
                            "decision": "approve",
                        }
                    },
                ),
            ],
        )

    def test_phase4_low_score_triggers_rework_card(self, monkeypatch):
        """Phase 4 低分报告：弹出返工确认卡片（interrupt 携带 rework 标记），
        用户选择开始返工后注入返工反馈。"""
        captured = {}

        def fake_interrupt(request):
            captured["request"] = request
            return {"decision": "request_changes", "message": "", "checklist": {}}

        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            fake_interrupt,
        )

        middleware = PhaseReviewMiddleware()
        result = middleware.after_model(self._make_low_score_state(), None)

        # 验证 interrupt payload 携带 rework 标记与评分信息
        action_request = captured["request"]["action_requests"][0]
        assert action_request["name"] == "quality-review_rework"
        assert action_request["args"]["rework"]["score"] == 60.0
        assert action_request["args"]["rework"]["threshold"] == 75.0

        # 用户确认返工 → 注入返工反馈
        assert result is not None
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "用户已确认开始返工" in msg.content
        assert "缺少功能覆盖对照信息" not in msg.content

    def test_phase4_low_score_skip_rework(self, monkeypatch):
        """Phase 4 低分报告：用户在返工确认卡片上选择跳过返工 → 推进到下一阶段。"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "skip", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        result = middleware.after_model(self._make_low_score_state(), None)

        assert result is not None
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "跳过返工" in msg.content
        assert "风险自负" in msg.content


class TestStaleResumeRejection:
    """过期/错投 resume 的拒绝与重弹测试（防止"幽灵确认"）。

    背景：前端 SDK 将所有 submit 串行排队，Phase 1 评审卡片的重复提交
    会被 Phase 2 的 pending interrupt 消费。_phase 绑定校验确保错投的
    resume 不能消费当前阶段的评审卡片。
    """

    def test_stale_resume_triggers_reinterrupt(self, monkeypatch):
        """_phase 不匹配的 resume 被拒绝并重新弹出当前阶段卡片。"""
        responses = iter([
            # 第一次：来自 requirement-analysis 卡片的过期 payload
            {"decision": "approve", "message": "旧卡片评论", "_phase": "requirement-analysis"},
            # 第二次：用户对当前阶段的真实决策
            {"decision": "approve", "message": "真实决策", "_phase": "test-strategy"},
        ])
        calls = []

        def fake_interrupt(request):
            calls.append(request)
            return next(responses)

        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            fake_interrupt,
        )

        middleware = PhaseReviewMiddleware()
        state = {"messages": [AIMessage(content="## 测试策略报告\n\n策略内容...")]}
        result = middleware.after_model(state, None)

        # 过期 payload 被拒绝，卡片重新弹出一次
        assert len(calls) == 2
        assert result is not None
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        # 使用的是真实决策，而不是旧卡片的评论
        assert "真实决策" in msg.content
        assert "旧卡片评论" not in msg.content

    def test_resume_without_phase_passes_through(self, monkeypatch):
        """未携带 _phase 的旧版前端 payload 直接放行（向后兼容）。"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = {"messages": [AIMessage(content="## 测试策略报告\n\n策略内容...")]}
        result = middleware.after_model(state, None)

        assert result is not None
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "报告已确认" in msg.content


class TestFormatSelectionDedup:
    """输出格式选择面板的防重复触发测试。"""

    def _make_state(self, ai_content: str, human_messages: list | None = None):
        return {
            "messages": [
                *(human_messages or []),
                AIMessage(content=ai_content),
            ]
        }

    def test_format_selection_not_retriggered_after_decision(self):
        """用户已选择过格式后，交付汇报消息标题（如「## 输出格式化（Excel）」）
        再次命中正则时不再触发 interrupt。"""
        middleware = PhaseReviewMiddleware()
        state = self._make_state(
            """
## 输出格式化（Excel）

导出文件：/PR-2/PR2_测试用例集.xlsx，共 89 条用例。
""",
            human_messages=[
                HumanMessage(
                    content="[阶段评审：output-format-selection] 用户反馈：用户选择输出格式：excel。请按该格式输出最终交付物。",
                    additional_kwargs={
                        "_review_round": {
                            "phase": "output-format-selection",
                            "round": 1,
                            "decision": "approve",
                        }
                    },
                ),
            ],
        )
        result = middleware.after_model(state, None)
        assert result is None


class TestPhaseReportToolCallSeparation:
    """测试阶段报告与工具调用混排时的兜底拆分。"""

    def _make_state_with_tool_call(self, ai_content: str) -> dict:
        return {
            "messages": [
                HumanMessage(content="分析需求"),
                AIMessage(
                    content=ai_content,
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "save_feature_matrix_tool",
                            "args": {"features": []},
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

    def test_phase1_with_tool_calls_returns_split_feedback(self):
        """Phase 1 报告附带工具调用时应拆分并要求分步输出"""
        middleware = PhaseReviewMiddleware()
        state = self._make_state_with_tool_call("""
## 需求解析报告

以上为 Phase 1 需求分析。
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        assert result.get("jump_to") == "model"

        updated = result["messages"]
        assert isinstance(updated, Overwrite)
        msgs = updated.value
        assert len(msgs) == 3

        # 原 HumanMessage 保留
        assert isinstance(msgs[0], HumanMessage)
        # 原 AI 消息被拆分为纯文本（无 tool_calls）
        cleaned_ai = msgs[1]
        assert isinstance(cleaned_ai, AIMessage)
        assert "## 需求解析报告" in str(cleaned_ai.content)
        assert not cleaned_ai.tool_calls
        # 追加系统反馈，要求模型分步输出
        feedback = msgs[2]
        assert isinstance(feedback, HumanMessage)
        assert "阶段报告与工具调用混在一起" in feedback.content
        assert "人工评审卡片无法弹出" in feedback.content
        assert "不要附带任何工具调用" in feedback.content

    def test_phase1_with_tool_calls_preserves_other_messages(self):
        """拆分时应保留阶段报告之前的所有消息"""
        middleware = PhaseReviewMiddleware()
        state = {
            "messages": [
                HumanMessage(content="开始分析"),
                AIMessage(content="调用 write_todos", tool_calls=[{"id": "call_0", "name": "write_todos", "args": {}, "type": "tool_call"}]),
                HumanMessage(content="工具结果"),
                AIMessage(
                    content="## 功能测试矩阵\n\n| FP-001 | ... |",
                    tool_calls=[{"id": "call_1", "name": "save_feature_matrix_tool", "args": {}, "type": "tool_call"}],
                ),
            ]
        }
        result = middleware.after_model(state, None)

        assert result is not None
        updated = result["messages"]
        assert isinstance(updated, Overwrite)
        msgs = updated.value
        assert len(msgs) == 5
        assert isinstance(msgs[0], HumanMessage)
        assert isinstance(msgs[1], AIMessage)
        assert isinstance(msgs[2], HumanMessage)
        cleaned_ai = msgs[3]
        assert isinstance(cleaned_ai, AIMessage)
        assert "## 功能测试矩阵" in str(cleaned_ai.content)
        assert not cleaned_ai.tool_calls
        assert isinstance(msgs[4], HumanMessage)

    def test_phase1_without_tool_calls_triggers_interrupt(self, monkeypatch):
        """Phase 1 报告无工具调用时应正常触发 interrupt"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = {"messages": [HumanMessage(content="分析需求"), AIMessage(content="## 需求解析报告\n以上为 Phase 1。")]}
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        # 正常触发评审，返回的 messages 不是 Overwrite，而是包含评审反馈 HumanMessage 的列表
        assert not isinstance(result["messages"], Overwrite)
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "阶段评审" in msg.content


class TestExtractQualityScoreTableFormat:
    """验证表格格式评分的提取（修复自动退回失效的根因）。"""

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            # 表格加粗格式 — 完整 Markdown 行（这是 bug 根源的格式）
            (
                "| **综合评分** | — | **[58.1]** | **[58.1]%** |",
                58.1,
            ),
            # 表格无加粗格式
            ("综合评分 | — | 72.5 | 72.5%", 72.5),
            # 列间无空格变体
            ("**综合评分**|—|**[85.0]**|**85.0%**|", 85.0),
            # 多列表格上下文（使用不带格式的纯表格文本）
            (
                "| **基础评分** | **100** | **[63.1]** | **[63.1%]** |\n"
                "| **综合评分** | — | **[58.1]** | **[58.1%]** |",
                58.1,
            ),
        ],
    )
    def test_table_format_scores(self, content, expected):
        assert _extract_quality_score(content) == expected

    def test_table_format_multiline_full_report(self):
        """完整质量评审报告表格中提取评分。"""
        content = (
            "| **完整性** | 30 | 18 | 60% |\n"
            "| **准确性** | 25 | 14 | 56% |\n"
            "| **有效性** | 25 | 14.5 | 58% |\n"
            "| **可执行性** | 20 | 11.6 | 58% |\n"
            "| **基础评分** | **100** | **[63.1]** | **[63.1%]** |\n"
            "| 交叉验证减分 | — | -5 | — |\n"
            "| **综合评分** | — | **[58.1]** | **[58.1%]** |"
        )
        assert _extract_quality_score(content) == 58.1

    @pytest.mark.parametrize(
        "content",
        [
            # 范围外分数应返回 None
            "综合评分：-5",
            "综合评分：120 分",
        ],
    )
    def test_table_out_of_range_returns_none(self, content):
        assert _extract_quality_score(content) is None


class TestDetectPhase3CoverageGap:
    """验证 Phase 3 覆盖率缺口检测。"""

    def test_all_covered_returns_empty(self):
        content = """
| ModuleA | 3 | 10 | 100% ✅ | all covered |
| ModuleB | 4 | 16 | 100% ✅ | all covered |
"""
        assert _detect_phase3_coverage_gap(content) == []

    def test_mixed_coverage_detects_uncovered(self):
        """部分覆盖、部分未覆盖的场景应正确识别未覆盖模块。"""
        # 使用表格行直接构建，避免三引号内中文在特定环境下编码问题
        covered_row = "| CoveredModule | 3 | 10 | 100% ✅ | all covered |"
        uncovered_1 = "| UncoveredModA | 4 | 0 | 0% ❌ | no cases |"
        uncovered_2 = "| UncoveredModB | 2 | 0 | 0% ❌ | no cases |"
        content = "\n".join([uncovered_1, uncovered_2, covered_row])

        result = _detect_phase3_coverage_gap(content)

        # 应识别出 2 个未覆盖模块，覆盖模块不在结果中
        assert "UncoveredModA" in result
        assert "UncoveredModB" in result
        assert "CoveredModule" not in result
        assert len(result) == 2

    def test_zero_cases_chinese_format(self):
        content = """
| 系统配置 | 1 | 0条 | 0% ❌ | 无用例 |
"""
        result = _detect_phase3_coverage_gap(content)
        assert "系统配置" in result

    def test_no_coverage_table_returns_empty(self):
        """无覆盖对照表时返回空（由其他检查兜底）"""
        content = "共生成 10 条用例。全部模块已完成。"
        assert _detect_phase3_coverage_gap(content) == []

    def test_header_row_excluded(self):
        """表头行不应被识别为未覆盖模块"""
        content = """
| 模块 | 功能点数 | 用例数 | 覆盖率 |
|------|---------|--------|--------|
| 登录 | 3 | 5 | 100% ✅ |
"""
        assert _detect_phase3_coverage_gap(content) == []

    def test_summary_row_excluded(self):
        """汇总行不应被识别为模块"""
        content = """
| 合计 | 38 | 43 | 0% ❌ | 仅 34.2% |
"""
        assert _detect_phase3_coverage_gap(content) == []


class TestPhase3CoverageGate:
    """集成测试：Phase 3 覆盖率不全时中间件自动退回。"""

    def _make_state(self, ai_content: str, human_messages=None):
        return {
            "messages": [
                *(human_messages or []),
                AIMessage(content=ai_content),
            ]
        }

    def test_uncovered_modules_trigger_auto_reject(self):
        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 测试用例生成完成

### 关键用例抽样
- case_number: TC-PR2-BG-001
- test_case_steps: 输入数据
- test_data: {"name": "test"}

### 覆盖度分析
| 模块 | 功能点数 | 用例数 | 覆盖率 | 缺口说明 |
|------|---------|--------|--------|---------|
| 标气管理 | 3 | 10 | 100% ✅ | 全部覆盖 |
| 设备管理 | 4 | 0 | 0% ❌ | 无用例 |
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        assert result.get("jump_to") == "model"
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "设备管理" in msg.content
        assert ("继续设计" in msg.content or "完成后再输出" in msg.content)

    def test_full_coverage_proceeds_normally(self, monkeypatch):
        """全部覆盖时不应触发门禁，正常走 interrupt"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 测试用例生成完成

### 关键用例抽样
- case_number: TC-PR2-BG-001
- test_case_steps: 输入数据
- test_data: {"name": "test"}

### 覆盖度分析
| 模块 | 功能点数 | 用例数 | 覆盖率 |
|------|---------|--------|--------|
| 标气管理 | 3 | 10 | 100% ✅ |
| 配气模板 | 4 | 16 | 100% ✅ |
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        assert not any(
            isinstance(m, HumanMessage) and "继续设计" in str(m.content)
            for m in result.get("messages", [])
        )

    def test_no_coverage_table_skips_gate(self, monkeypatch):
        """报告中无覆盖对照表时应跳过门禁（由 _has_case_preview 等其他兜底处理）"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 测试用例生成完成

### 关键用例抽样
- case_number: TC-PR2-BG-001
- test_case_steps: 打开页面，验证列表加载
- test_data: {"page": 1}
- expected_result: 列表正常显示
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert "messages" in result
        # 没有覆盖表时不应触发覆盖率退回
        assert not any(
            isinstance(m, HumanMessage) and "覆盖率不完整" in str(m.content)
            for m in result.get("messages", [])
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestDetectUncoveredP0:
    """验证 Phase 4 报告中未覆盖 P0 功能点的检测。"""

    def test_no_uncovered_p0_returns_empty(self):
        content = """
| FP-001 | 配气模板 | 创建模板 | P0 | ✅ 已覆盖 | TC-PR-PT-001~008 |
| FP-002 | 任务管理 | 批次号 | P0 | ✅ 已覆盖 | TC-PR-TASK-001~004 |
"""
        assert _detect_uncovered_p0(content) == []

    def test_uncovered_p0_detected_single(self):
        content = """
| FP-016 | 数据隔离 | 实验室切换 | P0 | 🔴 未覆盖 | — |
| FP-017 | 数据隔离 | 隔离模块 | P0 | ✅ 已覆盖 | TC-PR-ISOLATE-001 |
"""
        result = _detect_uncovered_p0(content)
        assert "FP-016" in result
        assert "FP-017" not in result
        assert len(result) == 1

    def test_uncovered_p0_detected_multiple(self):
        content = """
| FP-016 | 数据隔离 | 实验室切换 | P0 | 🔴 未覆盖 | — |
| FP-020 | 进样列表 | 质控字段 | P0 | 🔴 未覆盖 | — |
| FP-001 | 配气模板 | 创建模板 | P0 | ✅ 已覆盖 | TC-001 |
"""
        result = _detect_uncovered_p0(content)
        assert "FP-016" in result
        assert "FP-020" in result
        assert len(result) == 2

    def test_p1_uncovered_ignored(self):
        """只有 P1 未覆盖时不报警"""
        content = """
| FP-005 | 模板列表 | 分页 | P1 | 0% ❌ | 无用例 |
| FP-006 | 任务管理 | 导出 | P2 | 0% ❌ | 无用例 |
"""
        assert _detect_uncovered_p0(content) == []

    def test_chinese_paragraph_format(self):
        content = "FP-016、FP-020 完全未覆盖（P0），需回退 Phase 3 补充。"
        result = _detect_uncovered_p0(content)
        assert "FP-016" in result
        assert "FP-020" in result

    def test_emoji_markers(self):
        content = """
| FP-019 | 结果对比 | 判定结论 | P0 | ❌ 未覆盖 | — |
"""
        result = _detect_uncovered_p0(content)
        assert "FP-019" in result

    def test_no_coverage_table_returns_empty(self):
        """无对照表时返回空列表"""
        content = "综合评分：85 分。所有 P0 功能点均已覆盖。"
        assert _detect_uncovered_p0(content) == []


class TestGetCompletedPhases:
    """验证已完成阶段的提取。"""

    def test_no_completed_phases(self):
        messages = [HumanMessage(content="开始分析")]
        assert _get_completed_phases(messages) == set()

    def test_approved_phase_returned(self):
        msg = HumanMessage(
            content="[阶段评审：requirement-analysis] 用户反馈：已确认",
            additional_kwargs={
                "_review_round": {
                    "phase": "requirement-analysis",
                    "round": 1,
                    "decision": "approve",
                }
            },
        )
        assert _get_completed_phases([msg]) == {"requirement-analysis"}

    def test_skipped_phase_returned(self):
        msg = HumanMessage(
            content="[阶段评审：test-strategy] 用户反馈：跳过",
            additional_kwargs={
                "_review_round": {
                    "phase": "test-strategy",
                    "round": 1,
                    "decision": "skip",
                }
            },
        )
        assert _get_completed_phases([msg]) == {"test-strategy"}

    def test_request_changes_not_returned(self):
        """request_changes 不算完成"""
        msg = HumanMessage(
            content="[阶段评审：quality-review] 用户反馈：需要修改",
            additional_kwargs={
                "_review_round": {
                    "phase": "quality-review",
                    "round": 1,
                    "decision": "request_changes",
                }
            },
        )
        assert _get_completed_phases([msg]) == set()

    def test_multiple_phases(self):
        msgs = [
            HumanMessage(
                content="[阶段评审：requirement-analysis]",
                additional_kwargs={
                    "_review_round": {"phase": "requirement-analysis", "round": 1, "decision": "approve"}
                },
            ),
            HumanMessage(
                content="[阶段评审：test-strategy]",
                additional_kwargs={
                    "_review_round": {"phase": "test-strategy", "round": 1, "decision": "approve"}
                },
            ),
        ]
        assert _get_completed_phases(msgs) == {"requirement-analysis", "test-strategy"}


class TestCrossPhaseSkipDetection:
    """集成测试：跨阶段跳步检测。"""

    def _make_state(self, ai_content: str, human_msgs=None):
        return {
            "messages": [
                *(human_msgs or []),
                AIMessage(content=ai_content),
            ]
        }

    def test_skip_detected_when_phase4_without_phase3(self):
        """Phase 4 报告出现但 Phase 3 从未评审，且有用例上下文 → 拦截"""
        middleware = PhaseReviewMiddleware()
        state = self._make_state(
            """
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl。功能覆盖率 90%。

| FP-001 | 配气模板 | 创建模板 | P0 | ✅ 已覆盖 | TC-PR-PT-001 |
| FP-002 | 任务管理 | 批次号 | P0 | ✅ 已覆盖 | TC-PR-TASK-001 |

综合评分：85 分
""",
            human_msgs=[
                HumanMessage(content="设计测试用例"),
                AIMessage(content="TC-PR-PT-001: 验证创建模板", tool_calls=[]),
            ],
        )
        result = middleware.after_model(state, None)

        assert result is not None
        assert result.get("jump_to") == "model"
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "Phase 3" in msg.content
        assert "尚未经过人工评审" in msg.content
        assert "测试用例生成完成" in msg.content

    def test_no_skip_when_phase3_was_completed(self, monkeypatch):
        """Phase 3 已完成评审 → Phase 4 正常通过"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )
        middleware = PhaseReviewMiddleware()
        state = self._make_state(
            """
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl。

| FP-001 | 配气模板 | P0 | ✅ | TC-PR-PT-001 |

综合评分：90 分
""",
            human_msgs=[
                HumanMessage(
                    content="[阶段评审：test-case-generation] 用户反馈：已确认",
                    additional_kwargs={
                        "_review_round": {
                            "phase": "test-case-generation",
                            "round": 1,
                            "decision": "approve",
                        }
                    },
                ),
                AIMessage(content="Phase 3 已通过"),
            ],
        )
        result = middleware.after_model(state, None)

        assert result is not None
        # 不应触发跨阶段跳步拦截
        assert not any(
            isinstance(m, HumanMessage) and "Phase 3" in str(m.content) and "人工评审" in str(m.content)
            for m in result.get("messages", [])
        )

    def test_no_skip_when_no_case_context(self, monkeypatch):
        """对话中无用例上下文时（如 Phase 4 直接从 Phase 2 后开始），不触发跳步拦截"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )
        middleware = PhaseReviewMiddleware()
        state = self._make_state(
            """
## 📊 测试用例质量评审报告

[无结构化矩阵] 覆盖度基于对话历史判断。

综合评分：80 分
""",
            human_msgs=[
                HumanMessage(
                    content="[阶段评审：test-strategy] 用户反馈：已确认",
                    additional_kwargs={
                        "_review_round": {"phase": "test-strategy", "round": 1, "decision": "approve"}
                    },
                ),
            ],
        )
        # 没有 TC- 或 batch_create_test_cases 的上下文
        result = middleware.after_model(state, None)

        # 不应触发跨阶段跳步拦截
        if result and "messages" in result:
            assert not any(
                isinstance(m, HumanMessage) and "Phase 3" in str(m.content) and "尚未经过人工评审" in str(m.content)
                for m in result.get("messages", [])
            )


class TestPhase4UncoveredP0Gate:
    """集成测试：Phase 4 未覆盖 P0 门禁。"""

    def _make_state(self, ai_content: str, human_msgs=None):
        return {
            "messages": [
                *(human_msgs or []),
                AIMessage(content=ai_content),
            ]
        }

    def test_uncovered_p0_blocks_auto_approve(self, monkeypatch):
        """评审报告中有未覆盖 P0 → 阻止自动审批，弹出人工评审卡片"""
        interrupt_called = []

        def capture_interrupt(request):
            interrupt_called.append(request)
            return {"decision": "approve", "message": "已知悉风险", "checklist": {}}

        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            capture_interrupt,
        )
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware._get_auto_approve_threshold",
            lambda runtime, messages: 80.0,
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state(
            """
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl。

| FP-001 | 配气模板 | P0 | ✅ 已覆盖 | TC-001 |
| FP-016 | 数据隔离 | 实验室切换 | P0 | 🔴 未覆盖 | — |
| FP-020 | 进样列表 | 质控字段 | P0 | 🔴 未覆盖 | — |

综合评分：85 分
""",
            human_msgs=[
                HumanMessage(
                    content="[阶段评审：test-case-generation] 用户反馈：已确认",
                    additional_kwargs={
                        "_review_round": {"phase": "test-case-generation", "round": 1, "decision": "approve"}
                    },
                ),
            ],
        )

        result = middleware.after_model(state, None)

        assert result is not None
        # 应该触发了 interrupt（人工评审卡片），而不是自动通过
        assert len(interrupt_called) > 0
        # 检查返回的消息中包含未覆盖 P0 警告
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "FP-016" in msg.content
        assert "FP-020" in msg.content
        assert "P0" in msg.content
        assert "未覆盖" in msg.content

    def test_all_p0_covered_allows_auto_approve(self, monkeypatch):
        """所有 P0 已覆盖 + 评分达标 → 正常自动审批"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware._get_auto_approve_threshold",
            lambda runtime, messages: 80.0,
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state(
            """
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl。

| FP-001 | 配气模板 | P0 | ✅ 已覆盖 | TC-001 |
| FP-002 | 任务管理 | P0 | ✅ 已覆盖 | TC-002 |

综合评分：85 分
""",
            human_msgs=[
                HumanMessage(
                    content="[阶段评审：test-case-generation] 用户反馈：已确认",
                    additional_kwargs={
                        "_review_round": {"phase": "test-case-generation", "round": 1, "decision": "approve"}
                    },
                ),
            ],
        )
        result = middleware.after_model(state, None)

        assert result is not None
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "报告已确认" in msg.content
        assert "系统自动通过" in msg.content


class TestEmptySuggestionTable:
    """测试 _has_empty_suggestion_table 空表头检测。"""

    def test_empty_table_skeleton_detected(self):
        """表头 + 分隔行 + 0 数据行 → 检出（用户上报的失败形态）"""
        content = """
## 📊 测试用例质量评审报告

### 补充建议

#### 建议新增的测试用例
| 建议类型 | 描述 | 优先级 |
|---------|------|--------|

#### 测试风险提示
- ⚠️ 无
"""
        assert _has_empty_suggestion_table(content) is True

    def test_table_with_data_rows_passes(self):
        """表头后有数据行 → 通过"""
        content = """
### 补充建议

#### 建议新增的测试用例
| 建议类型 | 描述 | 优先级 |
|---------|------|--------|
| 覆盖补全 | FP-012 部分退款未覆盖，建议补充混合支付场景 | P0 |
| 安全测试 | TC-AUTH-003 缺少 SQL 注入变体 | P1 |
"""
        assert _has_empty_suggestion_table(content) is False

    def test_table_with_wu_row_passes(self):
        """数据行写「无」→ 通过（合法空态写法）"""
        content = """
### 补充建议

#### 建议新增的测试用例
| 建议类型 | 描述 | 优先级 |
|---------|------|--------|
| 无 | 本次评审未发现需要新增的用例方向 | - |
"""
        assert _has_empty_suggestion_table(content) is False

    def test_empty_table_with_trailing_wu_note_passes(self):
        """空表但紧随其后声明"无新增建议"→ 放行"""
        content = """
### 补充建议

#### 建议新增的测试用例
| 建议类型 | 描述 | 优先级 |
|---------|------|--------|

（本次评审无新增建议）
"""
        assert _has_empty_suggestion_table(content) is False

    def test_no_suggestion_table_passes(self):
        """报告删除了整个补充建议小节 → 通过（合法空态写法之一）"""
        content = """
## 📊 测试用例质量评审报告

综合评分：90 分

### 覆盖度分析
已读取 feature_matrix.jsonl。
"""
        assert _has_empty_suggestion_table(content) is False

    def test_prose_mention_not_table_passes(self):
        """正文提及"建议类型/优先级"但不是表格结构 → 不误判"""
        content = """
### 补充建议

| 建议类型 | 描述 | 优先级 | 说明：以下为文字描述而非表格——
建议类型包括安全测试与边界测试，优先级按 P0-P3 分配，本次均无新增。
"""
        assert _has_empty_suggestion_table(content) is False

    def test_all_empty_cells_row_not_counted(self):
        """全空单元格行（| | | |）不算数据行 → 仍检出空表"""
        content = """
#### 建议新增的测试用例
| 建议类型 | 描述 | 优先级 |
|---------|------|--------|
| | | |
"""
        assert _has_empty_suggestion_table(content) is True


class TestPhase4EmptySuggestionGate:
    """测试 Phase 4 补充建议空表头的兜底拦截。"""

    def _make_state(self, ai_content: str):
        return {"messages": [AIMessage(content=ai_content)]}

    def test_empty_suggestion_table_returns_request_changes(self):
        """空表头 → 拦截并给出填充指引"""
        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl，共 15 个功能点，全部已覆盖。

综合评分：92 分

### 补充建议

#### 建议新增的测试用例
| 建议类型 | 描述 | 优先级 |
|---------|------|--------|
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert result.get("jump_to") == "model"
        msg = result["messages"][0]
        assert isinstance(msg, HumanMessage)
        assert "只有表头" in msg.content
        assert "compute_coverage_report" in msg.content

    def test_filled_suggestion_table_passes_gate(self, monkeypatch):
        """有数据行 → 不被空表门禁拦截，进入正常 interrupt"""
        monkeypatch.setattr(
            "app.agents.testcase.phase_review_middleware.interrupt",
            lambda request: {"decision": "approve", "message": "", "checklist": {}},
        )

        middleware = PhaseReviewMiddleware()
        state = self._make_state("""
## 📊 测试用例质量评审报告

已读取 feature_matrix.jsonl，共 15 个功能点，14 个已覆盖。

综合评分：88 分

### 补充建议

#### 建议新增的测试用例
| 建议类型 | 描述 | 优先级 |
|---------|------|--------|
| 覆盖补全 | FP-012 部分退款未覆盖，建议补充混合支付场景 | P0 |
""")
        result = middleware.after_model(state, None)

        assert result is not None
        assert not any(
            isinstance(m, HumanMessage) and "只有表头" in m.content
            for m in result.get("messages", [])
        )

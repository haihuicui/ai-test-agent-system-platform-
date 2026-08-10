"""DeepSeek 裁判模型封装（DeepEval G-Eval 用）。

把平台统一的 text_model 工厂包装成 DeepEval 的 DeepEvalBaseLLM 协议：
- 低温（0.0）：裁判要确定性，不要创造力
- 独立实例：不污染主 Agent 的模型状态
- generate 不接 schema：DeepSeek 为 OpenAI 兼容接口，结构化输出由
  DeepEval 的 generate_with_schema 自动降级为 prompt-only 路径

裁判校准注意：裁判与被测 Agent 同源（都是 deepseek-v4-flash），
正式启用门禁前需抽 20-50 条人工标注算一致率（见 README「校准」）。
"""
from __future__ import annotations

import re

from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_core.messages import HumanMessage

from app.core.llms import get_text_model_with_temperature

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """对裁判输出做 JSON 净化：去 markdown 围栏、剥离前后散文。

    DeepSeek 对复杂评估 prompt 会给 JSON 包 ```json 围栏或附带解释性文字，
    DeepEval 的 trimAndLoadJson 无法解析时直接判 invalid JSON。
    仅在内容含 JSON 对象时介入，纯文本响应原样返回。
    """
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    fence = _JSON_FENCE.search(text)
    if fence:
        return fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        return text[start:end + 1]
    return text


class DeepSeekJudge(DeepEvalBaseLLM):
    """以平台 DeepSeek 文本模型为裁判的 DeepEval 适配器。"""

    def __init__(self, max_tokens: int = 8192):
        # 评分理由可能较长（逐条用例点评），给足输出预算；
        # reasoning 与正文共享配额，8192 与主 Agent 历史事故水位一致
        self._model = get_text_model_with_temperature(
            temperature=0.0,
            max_tokens=max_tokens,
        )

    def load_model(self):
        return self._model

    def generate(self, prompt: str) -> str:
        resp = self._model.invoke([HumanMessage(content=prompt)])
        return _extract_json(resp.content)

    async def a_generate(self, prompt: str) -> str:
        resp = await self._model.ainvoke([HumanMessage(content=prompt)])
        return _extract_json(resp.content)

    def get_model_name(self) -> str:
        return "deepseek-judge"

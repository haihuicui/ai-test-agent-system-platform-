"""图片需求转录中间件（VLM 感知 / text_model 决策 分层）。

问题背景：dynamic_model_selection 按「最近窗口内是否有图片」切换模型——
图片发出后的前 5-8 轮（恰好是 RAG 检索、skill 激活等关键决策窗口）全部
落在 VLM（doubao-seed mini 级）上。VLM 指令遵循能力弱，实测会跳过
rag-query Skill 直接输出需求报告（read_file 参数名都能搞错），等图片
滚出窗口切回 text_model 时，RAG 时机已永久错过（thread 5f32d1b4 实证）。

本中间件把 VLM 降级为「感知层」：abefore_model 检测到含未转录图片块的
human 消息时，先调 image_model 把图片完整转录为文字，以「同 id 消息替换」
写回 state（add_messages 的更新语义）；主流程随后全程走 text_model，
RAG / skill / 阶段评审全部由 deepseek 承担。

转录结果持久化在 state 而非请求副本，避免每轮重复调 VLM；
转录失败时保留图片块并打失败标记，降级回 dynamic_model_selection 的
VLM 原路径（不阻塞主流程）。

附带收益：base64 图片块不再驻留消息历史，checkpoint / 历史加载体积
显著缩小（此前 42MB 级历史卡顿有图片块一份贡献）。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llms import image_model

logger = logging.getLogger(__name__)

# 转录完成 / 失败的幂等标记（存 additional_kwargs，随 state 持久化）
_TRANSCRIBED_TAG = "_image_transcribed"
_FAILED_TAG = "_image_transcribe_failed"

_TRANSCRIBE_SYSTEM_PROMPT = """你是需求文档图片的精确转录专家。用户上传的图片将作为软件测试需求分析的输入。

请完整、忠实地转录图片中的全部内容：
1. 逐字转录所有文字：标题、正文、字段名、注释、图注
2. 表格用 Markdown 表格还原，保持行列结构与表头
3. 界面截图：按区域描述页面结构、字段、按钮、交互元素及其文案
4. 流程图/架构图：按步骤先后顺序或节点关系描述
5. 禁止总结、省略、推测或评论——转录必须完整到仅凭文字即可还原原始需求

直接输出转录内容本身。"""

_TRANSCRIBE_USER_PROMPT = "请完整转录以下需求图片的内容："


def _iter_image_blocks(message: Any) -> list[dict]:
    """提取消息 content 中的图片块（兼容 image / image_url 两种格式）。"""
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return []
    blocks = []
    for block in content:
        btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        if btype in ("image", "image_url"):
            blocks.append(block)
    return blocks


def _to_openai_image_block(block: Any) -> dict | None:
    """把图片块规整为 OpenAI image_url 格式（ChatOpenAI 可直接接受）。"""
    if not isinstance(block, dict):
        block = {"type": getattr(block, "type", None), **getattr(block, "__dict__", {})}
    btype = block.get("type")
    if btype == "image_url" and isinstance(block.get("image_url"), dict):
        return block
    if btype == "image" and block.get("data"):
        mime = block.get("mimeType") or "image/png"
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{block['data']}"}}
    return None


def _text_blocks(message: Any) -> list[dict]:
    """提取消息 content 中的文本块。"""
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == "text"]


class ImageTranscribeMiddleware(AgentMiddleware):
    """把含图片的 human 消息预转录为纯文本，让主流程全程走 text_model。"""

    async def abefore_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages") or []

        # 收集需要转录的消息：human + 含图片块 + 未转录 + 未标记失败
        pending: list[tuple[Any, list[dict]]] = []
        for msg in messages:
            if getattr(msg, "type", None) != "human":
                continue
            ak = getattr(msg, "additional_kwargs", None) or {}
            if ak.get(_TRANSCRIBED_TAG) or ak.get(_FAILED_TAG):
                continue
            blocks = _iter_image_blocks(msg)
            if blocks:
                pending.append((msg, blocks))

        if not pending:
            return None

        updates: list[Any] = []
        for msg, blocks in pending:
            openai_blocks = [b for b in (_to_openai_image_block(b) for b in blocks) if b]
            if not openai_blocks:
                continue

            try:
                response = await image_model.ainvoke([
                    SystemMessage(content=_TRANSCRIBE_SYSTEM_PROMPT),
                    HumanMessage(content=[
                        {"type": "text", "text": _TRANSCRIBE_USER_PROMPT},
                        *openai_blocks,
                    ]),
                ])
                transcription = (
                    response.content if isinstance(response.content, str) else str(response.content)
                ).strip()
            except Exception as e:  # noqa: BLE001 - 降级优先，绝不阻塞主流程
                logger.error("图片转录失败，降级为 VLM 原路径: %s", e, exc_info=True)
                updates.append(msg.model_copy(update={
                    "additional_kwargs": {**(msg.additional_kwargs or {}), _FAILED_TAG: True},
                }))
                continue

            if not transcription:
                # 空转录视为失败：保留图片块走 VLM 原路径，避免需求内容静默丢失
                logger.warning("图片转录结果为空，降级为 VLM 原路径 (msg id=%s)", getattr(msg, "id", None))
                updates.append(msg.model_copy(update={
                    "additional_kwargs": {**(msg.additional_kwargs or {}), _FAILED_TAG: True},
                }))
                continue

            # 保留原文字块，图片块整体替换为转录文本；同 id 消息经 add_messages
            # reducer 以更新语义写回 state。
            new_content = [
                *_text_blocks(msg),
                {"type": "text", "text": f"\n\n[需求图片转录内容]\n{transcription}"},
            ]
            updates.append(msg.model_copy(update={
                "content": new_content,
                "additional_kwargs": {**(msg.additional_kwargs or {}), _TRANSCRIBED_TAG: True},
            }))
            logger.info(
                "图片转录完成 (msg id=%s, %d 张图片, 转录 %d 字符)",
                getattr(msg, "id", None), len(openai_blocks), len(transcription),
            )

        return {"messages": updates} if updates else None

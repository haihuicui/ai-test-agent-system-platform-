"""Tests for ImageTranscribeMiddleware 的图片预转录逻辑。

覆盖：
- 含图片的 human 消息被转录为纯文本（同 id 替换语义，写回 state）
- 已转录 / 已失败标记的消息被跳过（幂等）
- VLM 异常或返回空时降级：保留图片块 + 失败标记（走 dynamic_model_selection 原路径）
- 无图片消息时不产生 state 更新
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.testcase.image_transcribe_middleware import (
    _FAILED_TAG,
    _TRANSCRIBED_TAG,
    ImageTranscribeMiddleware,
)

_IMAGE_BLOCK = {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}


def _image_msg(msg_id: str = "m1", text: str = "分析图片的需求") -> HumanMessage:
    return HumanMessage(
        id=msg_id,
        content=[{"type": "text", "text": text}, dict(_IMAGE_BLOCK)],
        additional_kwargs={"enable_rag": True},
    )


def _run(coro):
    return asyncio.run(coro)


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class TestImageTranscribe:
    def test_transcribes_image_message(self):
        """含图片消息被转录：图片块移除，转录文本入 content，打完成标记。"""
        mw = ImageTranscribeMiddleware()
        msg = _image_msg()
        with patch(
            "app.agents.testcase.image_transcribe_middleware.image_model"
        ) as mock_model:
            mock_model.ainvoke = AsyncMock(return_value=FakeResponse("## 地点管理需求\n功能点1：..."))
            result = _run(mw.abefore_model({"messages": [msg]}, None))

        assert result is not None
        updated = result["messages"][0]
        assert updated.id == "m1"  # 同 id 替换（add_messages 更新语义）
        assert updated.additional_kwargs[_TRANSCRIBED_TAG] is True
        block_types = [b["type"] for b in updated.content]
        assert "image_url" not in block_types  # 图片块已移除
        joined = "".join(b.get("text", "") for b in updated.content)
        assert "分析图片的需求" in joined  # 原文字保留
        assert "地点管理需求" in joined    # 转录内容注入
        # 转录请求确实带了图片
        vlm_messages = mock_model.ainvoke.call_args[0][0]
        assert any(
            isinstance(b, dict) and b.get("type") == "image_url"
            for b in vlm_messages[1].content
        )

    def test_skips_already_transcribed(self):
        """幂等：已转录消息不再重复调 VLM。"""
        mw = ImageTranscribeMiddleware()
        msg = _image_msg()
        msg.additional_kwargs[_TRANSCRIBED_TAG] = True
        with patch(
            "app.agents.testcase.image_transcribe_middleware.image_model"
        ) as mock_model:
            mock_model.ainvoke = AsyncMock(side_effect=AssertionError("不应被调用"))
            result = _run(mw.abefore_model({"messages": [msg]}, None))
        assert result is None

    def test_failure_keeps_image_and_marks_failed(self):
        """VLM 异常时降级：图片块保留（走 VLM 原路径），打失败标记不再重试。"""
        mw = ImageTranscribeMiddleware()
        msg = _image_msg()
        with patch(
            "app.agents.testcase.image_transcribe_middleware.image_model"
        ) as mock_model:
            mock_model.ainvoke = AsyncMock(side_effect=RuntimeError("VLM down"))
            result = _run(mw.abefore_model({"messages": [msg]}, None))

        updated = result["messages"][0]
        assert updated.additional_kwargs[_FAILED_TAG] is True
        assert _TRANSCRIBED_TAG not in updated.additional_kwargs
        block_types = [b["type"] for b in updated.content]
        assert "image_url" in block_types  # 图片块保留 → dynamic_model_selection 原路径

    def test_empty_transcription_treated_as_failure(self):
        """空转录视为失败：避免需求内容静默丢失。"""
        mw = ImageTranscribeMiddleware()
        msg = _image_msg()
        with patch(
            "app.agents.testcase.image_transcribe_middleware.image_model"
        ) as mock_model:
            mock_model.ainvoke = AsyncMock(return_value=FakeResponse("   "))
            result = _run(mw.abefore_model({"messages": [msg]}, None))

        updated = result["messages"][0]
        assert updated.additional_kwargs[_FAILED_TAG] is True
        assert any(b.get("type") == "image_url" for b in updated.content)

    def test_no_image_returns_none(self):
        """纯文本消息不产生 state 更新。"""
        mw = ImageTranscribeMiddleware()
        messages = [HumanMessage(content="纯文本需求"), AIMessage(content="好的")]
        assert _run(mw.abefore_model({"messages": messages}, None)) is None

    def test_multi_image_blocks_all_sent(self):
        """多图片块全部送入 VLM 一次转录。"""
        mw = ImageTranscribeMiddleware()
        msg = HumanMessage(
            id="m9",
            content=[
                {"type": "text", "text": "对比两张图"},
                dict(_IMAGE_BLOCK),
                dict(_IMAGE_BLOCK),
            ],
        )
        with patch(
            "app.agents.testcase.image_transcribe_middleware.image_model"
        ) as mock_model:
            mock_model.ainvoke = AsyncMock(return_value=FakeResponse("两图内容..."))
            result = _run(mw.abefore_model({"messages": [msg]}, None))

        vlm_messages = mock_model.ainvoke.call_args[0][0]
        image_count = sum(
            1 for b in vlm_messages[1].content
            if isinstance(b, dict) and b.get("type") == "image_url"
        )
        assert image_count == 2
        assert result["messages"][0].additional_kwargs[_TRANSCRIBED_TAG] is True

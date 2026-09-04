"""Regression tests for empty-content diagnostics.

When a reasoning model burns its whole completion budget on thinking (or a
provider silently filters the response), ``message.content`` comes back empty
and the adapter raises InvalidResponseError.  The error log must carry the
``finish_reason`` plus reasoning/usage sizes so operators can distinguish
token-budget exhaustion from provider-side content filtering without
reproducing the call by hand (observed in production: deepseek-v4-flash
extraction calls returning empty content).
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lightrag.llm.openai import InvalidResponseError, openai_complete_if_cache


def _make_empty_content_client(
    *, finish_reason="length", reasoning_content="x" * 500, completion_tokens=8192
) -> SimpleNamespace:
    message = SimpleNamespace(content=None, reasoning_content=reasoning_content)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(
        prompt_tokens=1000,
        completion_tokens=completion_tokens,
        total_tokens=1000 + (completion_tokens or 0),
    )
    response = SimpleNamespace(choices=[choice], usage=usage)
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=response))
        ),
        close=AsyncMock(),
    )


@pytest.mark.offline
@pytest.mark.asyncio
async def test_empty_content_logs_finish_reason_and_sizes(caplog):
    fake_client = _make_empty_content_client()
    with patch(
        "lightrag.llm.openai.create_openai_async_client", return_value=fake_client
    ):
        with caplog.at_level(logging.ERROR, logger="lightrag"):
            with pytest.raises(InvalidResponseError, match="empty content"):
                await openai_complete_if_cache.__wrapped__(
                    model="deepseek-v4-flash", prompt="extract entities"
                )

    assert "finish_reason=length" in caplog.text
    assert "reasoning_chars=500" in caplog.text
    assert "completion_tokens=8192" in caplog.text
    fake_client.close.assert_awaited()


@pytest.mark.offline
@pytest.mark.asyncio
async def test_empty_content_tolerates_missing_reasoning_and_usage(caplog):
    # Content-filter style responses may carry neither reasoning_content nor
    # usage; the diagnostic log must not itself blow up.
    fake_client = _make_empty_content_client(
        finish_reason="content_filter", reasoning_content=None, completion_tokens=None
    )
    fake_client.chat.completions.create.return_value.choices[0].message = (
        SimpleNamespace(content="", reasoning_content=None)
    )
    fake_client.chat.completions.create.return_value.usage = None
    with patch(
        "lightrag.llm.openai.create_openai_async_client", return_value=fake_client
    ):
        with caplog.at_level(logging.ERROR, logger="lightrag"):
            with pytest.raises(InvalidResponseError, match="empty content"):
                await openai_complete_if_cache.__wrapped__(
                    model="deepseek-v4-flash", prompt="extract entities"
                )

    assert "finish_reason=content_filter" in caplog.text
    assert "reasoning_chars=0" in caplog.text
    fake_client.close.assert_awaited()

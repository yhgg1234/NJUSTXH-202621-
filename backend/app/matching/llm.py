"""Spark Lite HTTP 客户端。

3.3 的核心匹配分数由规则和图谱数据计算；LLM 只负责生成报告摘要、
改进建议和学习路径文本。未配置密钥或调用失败时，业务服务会降级到
模板化建议，保证演示和测试不依赖外部网络。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger

from app.config import settings


class SparkLiteClient:
    """调用科大讯飞 Spark Lite HTTP chat completions 接口。"""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_url = api_url if api_url is not None else settings.LLM_API_URL
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.model = model if model is not None else settings.LLM_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.api_url and self.api_key)

    async def chat_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        *,
        temperature: float = 0.3,
    ) -> dict[str, Any] | None:
        """请求 Spark Lite 返回 JSON；失败时返回 None。"""
        content = await self.chat_text(
            system_prompt,
            json.dumps(user_payload, ensure_ascii=False),
            temperature=temperature,
        )
        if not content:
            return None
        try:
            return json.loads(_strip_json_fence(content))
        except json.JSONDecodeError:
            logger.warning("Spark Lite response is not valid JSON: {}", content[:300])
            return None

    async def chat_text(
        self,
        system_prompt: str,
        user_content: str,
        *,
        temperature: float = 0.3,
    ) -> str | None:
        """请求 Spark Lite 返回文本；未配置或失败时返回 None。"""
        if not self.enabled:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001 - 外部模型失败需业务降级
            logger.warning("Spark Lite request failed: {}", exc)
            return None

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            logger.warning("Unexpected Spark Lite response shape: {}", data)
            return None


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    return text

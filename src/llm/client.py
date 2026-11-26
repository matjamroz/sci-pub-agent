from __future__ import annotations

from typing import Optional

from openai import OpenAI

from src.config import get_settings


class LLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        settings = get_settings()
        self.model = model or settings.llm_model
        self.temperature = (
            settings.llm_temperature if temperature is None else temperature
        )
        self.num_ctx = settings.llm_num_ctx
        self.keep_alive = settings.llm_keep_alive
        self.client = OpenAI(
            base_url=base_url or settings.llm_base_url,
            api_key=api_key or settings.llm_api_key,
            timeout=90.0,
        )

    def _extra_body(self) -> dict:
        return {
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": self.num_ctx,
                "num_predict": 160,
            },
        }

    def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        extra = self._extra_body()
        if max_tokens is not None:
            extra["options"]["num_predict"] = max_tokens
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=max_tokens,
            extra_body=extra,
        )
        return (resp.choices[0].message.content or "").strip()

    def chat_stream(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        extra = self._extra_body()
        if max_tokens is not None:
            extra["options"]["num_predict"] = max_tokens
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=max_tokens,
            stream=True,
            extra_body=extra,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    def available(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

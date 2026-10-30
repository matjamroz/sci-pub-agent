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
        self.client = OpenAI(
            base_url=base_url or settings.llm_base_url,
            api_key=api_key or settings.llm_api_key,
            timeout=30.0,
        )

    def chat(self, messages: list[dict], temperature: Optional[float] = None) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
        )
        return (resp.choices[0].message.content or "").strip()

    def available(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

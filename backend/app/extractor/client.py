"""LLM clients: live Gemini and recorded fixtures. Client() is built in __init__, not at import."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple, Protocol

from app.config import Settings
from app.extractor.prompt import SYSTEM_PROMPT_TR, interaction_input
from app.extractor.schema import Extraction, gemini_json_schema


class Usage(NamedTuple):
    input_tokens: int
    output_tokens: int
    thought_tokens: int


class LLMClient(Protocol):
    async def extract_chunk(self, pdf_b64: str, chunk_index: int) -> tuple[Extraction, Usage]: ...


class GeminiClient:
    def __init__(self, settings: Settings):
        from google import genai
        from google.genai import types

        self._settings = settings
        self.retry_options = types.HttpRetryOptions(attempts=4)
        kwargs: dict = {
            "http_options": types.HttpOptions(retry_options=self.retry_options),
        }
        if settings.gemini_api_key:
            kwargs["api_key"] = settings.gemini_api_key
        self._client = genai.Client(**kwargs)
        self.calls: list[list[dict[str, str]]] = []
        self.recordings: list[dict] = []

    async def extract_chunk(self, pdf_b64: str, chunk_index: int) -> tuple[Extraction, Usage]:
        payload = interaction_input(pdf_b64, chunk_index)
        self.calls.append(payload)
        interaction = await self._client.aio.interactions.create(
            model=self._settings.gemini_model,
            system_instruction=SYSTEM_PROMPT_TR,
            input=payload,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": gemini_json_schema(Extraction),
            },
            generation_config={"thinking_level": "low"},
        )
        raw = interaction.output_text
        usage = interaction.usage
        inp = int(getattr(usage, "total_input_tokens", 0) or 0)
        out = int(getattr(usage, "total_output_tokens", 0) or 0)
        thought = int(getattr(usage, "total_thought_tokens", 0) or 0)
        self.recordings.append(
            {
                "output_text": raw,
                "usage": {
                    "total_input_tokens": inp,
                    "total_output_tokens": out,
                    "total_thought_tokens": thought,
                },
            }
        )
        result = Extraction.model_validate_json(raw)
        return result, Usage(inp, out, thought)


class RecordedClient:
    def __init__(self, path: Path):
        self.path = path
        data = json.loads(path.read_text(encoding="utf-8"))
        self._chunks: list[dict] | None = data.get("chunks")
        self._single = data if "output_text" in data else None
        self.calls: list[list[dict[str, str]]] = []
        self.recordings: list[dict] = []

    def _entry(self, chunk_index: int) -> dict:
        if self._chunks is not None:
            if chunk_index >= len(self._chunks):
                return self._chunks[-1]
            return self._chunks[chunk_index]
        if self._single is None:
            raise ValueError("recorded fixture missing output_text")
        return self._single

    async def extract_chunk(self, pdf_b64: str, chunk_index: int) -> tuple[Extraction, Usage]:
        payload = interaction_input(pdf_b64, chunk_index)
        self.calls.append(payload)
        entry = self._entry(chunk_index)
        raw = entry["output_text"]
        usage = entry.get("usage") or {}
        rec = {
            "output_text": raw,
            "usage": {
                "total_input_tokens": int(usage.get("total_input_tokens", 0)),
                "total_output_tokens": int(usage.get("total_output_tokens", 0)),
                "total_thought_tokens": int(usage.get("total_thought_tokens", 0)),
            },
        }
        self.recordings.append(rec)
        result = Extraction.model_validate_json(raw)
        u = rec["usage"]
        return result, Usage(u["total_input_tokens"], u["total_output_tokens"], u["total_thought_tokens"])

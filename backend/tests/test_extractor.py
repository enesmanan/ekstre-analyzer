from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.extractor.client import GeminiClient, RecordedClient
from app.extractor.schema import Extraction

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gemini" / "synthetic.json"


@pytest.mark.asyncio
async def test_recorded_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = RecordedClient(FIXTURE)
    extraction, usage = await client.extract_chunk("Zg==", 0)
    assert isinstance(extraction, Extraction)
    assert usage.input_tokens == 1200
    blob = str(client.calls)
    assert "dev@local" not in blob
    assert "user_id" not in blob
    assert "password" not in blob.lower()


def test_gemini_client_retry_attempts() -> None:
    client = GeminiClient(Settings(gemini_api_key="dummy"))
    assert client.retry_options.attempts == 4
    assert client._client is not None

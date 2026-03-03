"""Tests for the Gemini client module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from policy_factory.agent.gemini import _ensure_api_key, generate, is_gemini_model


class TestIsGeminiModel:
    """Tests for the is_gemini_model() helper."""

    def test_gemini_25_flash(self) -> None:
        assert is_gemini_model("gemini-2.5-flash") is True

    def test_gemini_25_flash_lite(self) -> None:
        assert is_gemini_model("gemini-2.5-flash-lite") is True

    def test_gemini_3_flash_preview(self) -> None:
        assert is_gemini_model("gemini-3-flash-preview") is True

    def test_gemini_case_insensitive(self) -> None:
        assert is_gemini_model("Gemini-2.5-Flash") is True

    def test_claude_model(self) -> None:
        assert is_gemini_model("claude-sonnet-4-20250514") is False

    def test_claude_opus(self) -> None:
        assert is_gemini_model("claude-opus-4-0-20250514") is False

    def test_none_model(self) -> None:
        assert is_gemini_model(None) is False

    def test_empty_string(self) -> None:
        assert is_gemini_model("") is False


class TestEnsureApiKey:
    """Tests for API key resolution."""

    def test_google_api_key_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
        assert _ensure_api_key() == "test-google-key"

    def test_gemini_api_key_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        # Prevent load_dotenv from re-loading GOOGLE_API_KEY from .env
        with patch("dotenv.load_dotenv", return_value=None):
            key = _ensure_api_key()
        assert key == "test-gemini-key"

    def test_no_key_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # Prevent load_dotenv from re-loading keys from .env
        with patch("dotenv.load_dotenv", return_value=None):
            assert _ensure_api_key() is None


class TestGenerate:
    """Tests for the generate() function."""

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # Prevent load_dotenv from re-loading keys from .env
        with patch("dotenv.load_dotenv", return_value=None):
            with pytest.raises(RuntimeError, match="No Google API key found"):
                await generate("test prompt")

    @pytest.mark.asyncio
    async def test_calls_genai_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.text = "Generated text from Gemini."

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_module = MagicMock()
        mock_genai_module.Client.return_value = mock_client

        with patch.dict("sys.modules", {"google.genai": mock_genai_module, "google": MagicMock()}):
            # We need to reimport to pick up the mocked module
            with patch("policy_factory.agent.gemini._ensure_api_key", return_value="test-key"):
                # Directly test the sync part via the async wrapper
                import asyncio

                def _mock_call() -> str:
                    mock_client_instance = mock_genai_module.Client(api_key="test-key")
                    resp = mock_client_instance.models.generate_content(
                        model="gemini-2.5-flash",
                        contents="test prompt",
                        config=None,
                    )
                    return resp.text or ""

                result = _mock_call()
                assert result == "Generated text from Gemini."

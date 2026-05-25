"""Tests for model_providers health check functions."""
import sys
import os
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.backend.services.model_providers import (
    check_ollama,
    check_nvidia,
    check_openai,
    check_all_providers,
)


def run_async(coro):
    """Helper to run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MockResponse:
    """Mock aiohttp response object."""
    def __init__(self, status, json_data=None):
        self.status = status
        self._json_data = json_data or {}

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSession:
    """Mock aiohttp ClientSession."""
    def __init__(self, mock_response):
        self._response = mock_response

    def get(self, *args, **kwargs):
        return MockContextManager(self._response)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockContextManager:
    """Mock async context manager for session.get()."""
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *args):
        pass


class TestCheckOllama:
    """Tests for check_ollama function."""

    @patch("dashboard.backend.services.model_providers._http_get")
    def test_ollama_healthy(self, mock_http_get):
        """Test Ollama check returns healthy when version endpoint responds."""
        async def mock_get(url, timeout=5):
            if "version" in url:
                return {"version": "1.0.0"}
            elif "tags" in url:
                return {
                    "models": [
                        {"name": "llama2"},
                        {"name": "codellama"},
                    ]
                }
            return None

        mock_http_get.side_effect = mock_get

        result = run_async(check_ollama())

        assert result["provider"] == "ollama"
        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        assert result["models"] == ["llama2", "codellama"]

    @patch("dashboard.backend.services.model_providers._http_get")
    def test_ollama_unreachable(self, mock_http_get):
        """Test Ollama check returns unreachable when version endpoint fails."""
        mock_http_get.return_value = None

        result = run_async(check_ollama())

        assert result["provider"] == "ollama"
        assert result["status"] == "unreachable"

    @patch("dashboard.backend.services.model_providers._http_get")
    def test_ollama_with_empty_models(self, mock_http_get):
        """Test Ollama check handles empty models list."""
        async def mock_get(url, timeout=5):
            if "version" in url:
                return {"version": "1.0.0"}
            elif "tags" in url:
                return {"models": []}
            return None

        mock_http_get.side_effect = mock_get

        result = run_async(check_ollama())

        assert result["status"] == "healthy"
        assert result["models"] == []


class TestCheckNvidia:
    """Tests for check_nvidia function."""

    def test_nvidia_healthy(self):
        """Test NVIDIA check returns healthy when nvidia-smi succeeds."""
        import subprocess as sp
        with patch.object(sp, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="75.0, 4096.0, 8192.0\n",
                stderr=""
            )

            result = check_nvidia()

            assert result["provider"] == "nvidia"
            assert result["status"] == "healthy"
            assert result["gpu_util"] == 75.0
            assert result["memory_used_mb"] == 4096.0
            assert result["memory_total_mb"] == 8192.0

    def test_nvidia_not_found(self):
        """Test NVIDIA check returns not_found when nvidia-smi not available."""
        import subprocess as sp
        with patch.object(sp, "run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = check_nvidia()

            assert result["provider"] == "nvidia"
            assert result["status"] == "not_found"

    def test_nvidia_error(self):
        """Test NVIDIA check returns error on subprocess failure."""
        import subprocess as sp
        with patch.object(sp, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error message"
            )

            result = check_nvidia()

            assert result["provider"] == "nvidia"
            assert result["status"] == "error"


class TestCheckOpenAI:
    """Tests for check_openai function."""

    def test_openai_healthy(self):
        """Test OpenAI check returns healthy when API key is valid."""
        mock_response = MockResponse(200, {
            "data": [
                {"id": "gpt-4"},
                {"id": "gpt-3.5-turbo"},
                {"id": "dall-e-3"},
            ]
        })

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.return_value = MockSession(mock_response)

            # Set API key in the module
            from dashboard.backend.services import model_providers
            model_providers.OPENAI_API_KEY = "test-key-123"

            result = run_async(check_openai())

            assert result["provider"] == "openai"
            assert result["status"] == "healthy"
            assert result["model_count"] == 3
            assert "gpt-4" in result["available_models"]

    def test_openai_not_configured(self):
        """Test OpenAI check returns not_configured when API key missing."""
        from dashboard.backend.services import model_providers
        original_key = model_providers.OPENAI_API_KEY
        model_providers.OPENAI_API_KEY = ""

        result = run_async(check_openai())

        assert result["provider"] == "openai"
        assert result["status"] == "not_configured"

        model_providers.OPENAI_API_KEY = original_key

    def test_openai_auth_error(self):
        """Test OpenAI check returns auth_error for invalid API key."""
        mock_response = MockResponse(401)

        from dashboard.backend.services import model_providers
        original_key = model_providers.OPENAI_API_KEY

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.return_value = MockSession(mock_response)

            model_providers.OPENAI_API_KEY = "invalid-key"

            result = run_async(check_openai())

            assert result["provider"] == "openai"
            assert result["status"] == "auth_error"

        model_providers.OPENAI_API_KEY = original_key


class TestCheckAllProviders:
    """Tests for check_all_providers function."""

    def test_check_all_providers_returns_all_three(self):
        """Test check_all_providers returns results for all providers."""
        mock_ollama_result = {"provider": "ollama", "status": "healthy"}
        mock_nvidia_result = {"provider": "nvidia", "status": "healthy"}
        mock_openai_result = {"provider": "openai", "status": "healthy"}

        async def mock_check_ollama():
            return mock_ollama_result

        async def mock_check_openai():
            return mock_openai_result

        with patch("dashboard.backend.services.model_providers.check_ollama", mock_check_ollama), \
             patch("dashboard.backend.services.model_providers.check_nvidia", return_value=mock_nvidia_result), \
             patch("dashboard.backend.services.model_providers.check_openai", mock_check_openai):

            result = run_async(check_all_providers())

            assert len(result) == 3
            providers = {r["provider"] for r in result}
            assert providers == {"ollama", "nvidia", "openai"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
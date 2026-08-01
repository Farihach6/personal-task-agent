"""Tests for GroqClient. The Groq SDK is always mocked — no real API calls."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from groq import APIConnectionError

from app.core.exceptions import ExternalServiceError
from app.llm.groq_client import GroqClient


def _make_mock_completion(text: str) -> MagicMock:
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


@patch("app.llm.groq_client.Groq")
def test_generate_returns_stripped_content(mock_groq_cls):
    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = _make_mock_completion("  Hello there!  ")
    mock_groq_cls.return_value = mock_instance

    client = GroqClient()
    result = client.generate("Hi")

    assert result == "Hello there!"
    mock_instance.chat.completions.create.assert_called_once()


@patch("app.llm.groq_client.Groq")
def test_generate_passes_prompt_as_user_message(mock_groq_cls):
    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = _make_mock_completion("ok")
    mock_groq_cls.return_value = mock_instance

    client = GroqClient()
    client.generate("What is 2+2?")

    _, kwargs = mock_instance.chat.completions.create.call_args
    assert kwargs["messages"] == [{"role": "user", "content": "What is 2+2?"}]


@patch("app.llm.groq_client.Groq")
def test_generate_returns_empty_string_when_content_is_none(mock_groq_cls):
    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = _make_mock_completion(None)
    mock_groq_cls.return_value = mock_instance

    client = GroqClient()
    assert client.generate("Hi") == ""


@patch("app.llm.groq_client.Groq")
def test_generate_raises_external_service_error_on_api_error(mock_groq_cls):
    mock_instance = MagicMock()
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_instance.chat.completions.create.side_effect = APIConnectionError(request=request)
    mock_groq_cls.return_value = mock_instance

    client = GroqClient()
    with pytest.raises(ExternalServiceError):
        client.generate("Hi")


@patch("app.llm.groq_client.Groq")
def test_generate_raises_external_service_error_on_unexpected_exception(mock_groq_cls):
    mock_instance = MagicMock()
    mock_instance.chat.completions.create.side_effect = RuntimeError("network blew up")
    mock_groq_cls.return_value = mock_instance

    client = GroqClient()
    with pytest.raises(ExternalServiceError):
        client.generate("Hi")
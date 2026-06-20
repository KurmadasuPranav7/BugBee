"""
LLM provider for BugBee.

Currently BugBee uses DeepSeek-R1 through the Hugging Face Inference API.

Future versions can add OpenAI, Anthropic, Gemini, Ollama, etc.
"""

from __future__ import annotations

from functools import lru_cache

from bugbee.config.settings import settings
from bugbee.lazy import lazy_import

# Lazy imports (only loaded when the provider is created)
ChatHuggingFace = lazy_import("langchain_huggingface").ChatHuggingFace
HuggingFaceEndpoint = lazy_import("langchain_huggingface").HuggingFaceEndpoint
HumanMessage = lazy_import("langchain_core.messages").HumanMessage


class DeepSeekProvider:
    """DeepSeek provider backed by Hugging Face Inference API."""

    def __init__(self) -> None:

        self.endpoint = HuggingFaceEndpoint(
            repo_id="deepseek-ai/DeepSeek-R1",
            task="text-generation",
            huggingfacehub_api_token=settings.huggingface_api_key,
            temperature=settings.temperature,
        )

        self.model = ChatHuggingFace(
            llm=self.endpoint,
        )

    def generate(self, prompt: str) -> str:
        """Generate a response from DeepSeek."""

        response = self.model.invoke(
            [
                HumanMessage(
                    content=prompt
                )
            ]
        )

        return response.content


@lru_cache(maxsize=1)
def default_provider() -> DeepSeekProvider:
    """
    Singleton provider.

    Prevents recreating the model every request.
    """
    return DeepSeekProvider()
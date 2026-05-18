"""
LangChain-based LLM service.
"""
from dataclasses import dataclass
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM response with metadata."""

    answer: str
    model: str
    tokens_used: int
    finish_reason: str


class LLMService:
    """LLM service with env-driven provider selection."""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = self._build_chat_model()

    def _build_chat_model(self):
        """Create the configured LangChain chat model."""
        provider = self.provider.lower()

        if provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )

        if provider == "openai_compatible":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=settings.OPENAI_COMPATIBLE_API_KEY or settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
            )

        if provider == "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=self.model,
                temperature=self.temperature,
                num_predict=self.max_tokens,
                base_url=settings.OLLAMA_BASE_URL,
            )

        if provider == "nvidia":
            from langchain_nvidia_ai_endpoints import ChatNVIDIA

            return ChatNVIDIA(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=settings.NVIDIA_API_KEY,
            )

        raise ValueError(
            "Unsupported LLM_PROVIDER. Use one of: "
            "openai, openai_compatible, anthropic, ollama, nvidia."
        )

    def generate_answer(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate an answer with the configured model."""
        messages = [
            SystemMessage(content=system_prompt or self._get_default_system_prompt()),
            HumanMessage(content=self._format_user_message(query, context)),
        ]

        response = self.client.invoke(messages)
        usage = getattr(response, "usage_metadata", {}) or {}
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))
        response_metadata = getattr(response, "response_metadata", {}) or {}

        return LLMResponse(
            answer=response.content if isinstance(response.content, str) else str(response.content),
            model=response_metadata.get("model_name", self.model),
            tokens_used=total_tokens,
            finish_reason=response_metadata.get("finish_reason", "completed"),
        )

    def _get_default_system_prompt(self) -> str:
        """Default system prompt for grounded answering."""
        return (
            "You are a grounded retrieval assistant.\n"
            "Answer using only the provided context.\n"
            "If the answer is not supported by the context, say that clearly.\n"
            "Prefer precise, source-backed answers and preserve citation markers."
        )

    def _format_user_message(self, query: str, context: str) -> str:
        """Build the user prompt payload."""
        return (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer the question using the context above. "
            "Use citation numbers like [0], [1] when referring to specific evidence."
        )


class PromptTemplates:
    """Collection of prompt templates for RAG scenarios."""

    @staticmethod
    def citation_aware_prompt() -> str:
        """Prompt emphasizing grounded, cited answers."""
        return (
            "You are a helpful assistant that answers only from retrieved context.\n"
            "Do not invent facts.\n"
            "Keep answers concise but complete.\n"
            "Use the citation identifiers already present in the context."
        )

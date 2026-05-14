"""
app/core/nl2sql/llm_client.py
──────────────────────────────────────────────────────────────────────────────
Thin wrapper around the OpenAI ChatCompletion API.

Features:
  • Tracks input/output tokens on every call
  • Supports JSON mode (force valid JSON output)
  • SQL extraction via regex with graceful fallback
  • Raises structured exceptions so callers can distinguish LLM errors
    from application errors
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI, OpenAIError

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int


class LLMClient:
    """
    Synchronous OpenAI wrapper.

    Usage:
        client = LLMClient()
        resp = client.chat(system="...", user="...", json_mode=True)
        sql   = client.extract_sql(resp.content)
    """

    def __init__(self):
        self._client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    # ─────────────────────────────────────────────────────────────────────────
    #  Core chat call
    # ─────────────────────────────────────────────────────────────────────────

    def chat(
        self,
        user: str,
        system: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Single-turn chat call.

        Args:
            user: The human message / question.
            system: System prompt (optional).
            json_mode: If True, forces OpenAI to return valid JSON.
            temperature: 0.0 for deterministic SQL, higher for natural language.
            model: Override the default model for this call.

        Returns:
            LLMResponse with content + token usage.

        Raises:
            RuntimeError on API failure.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.monotonic()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except OpenAIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise RuntimeError(f"LLM call failed: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        usage = resp.usage

        return LLMResponse(
            content=resp.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            latency_ms=latency_ms,
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def extract_sql(content: str) -> Optional[str]:
        """
        Pull a SELECT / WITH statement out of LLM response text.

        Handles:
          • Raw SQL with no wrapper
          • SQL inside ```sql ... ``` fences
          • SQL after "Answer:" or "Query:" prefixes
          • CTEs (WITH ... SELECT ...)
        """
        if not content:
            return None

        # Strip markdown code fences
        content = re.sub(r"```(?:sql)?", "", content, flags=re.IGNORECASE).strip()
        content = content.replace("```", "").strip()

        # Strip common LLM preamble labels
        content = re.sub(r"^\s*(answer|query|sql|response)\s*:\s*", "", content, flags=re.IGNORECASE)

        # Match WITH ... (CTE) or SELECT ...
        pattern = r"(WITH\s+.+?;|WITH\s+.+|SELECT\s+.+?;|SELECT\s+.+)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1).strip()
            # Ensure it ends with semicolon
            if not sql.rstrip().endswith(";"):
                sql = sql.rstrip() + ";"
            return sql

        return None

    @staticmethod
    def extract_sql_from_json(content: str) -> Optional[str]:
        """Extract SQL from a JSON response shaped like {"sql": "..."}."""
        payload = LLMClient.parse_json(content)
        if not isinstance(payload, dict):
            return None

        sql = payload.get("sql")
        if not isinstance(sql, str):
            return None

        return LLMClient.extract_sql(sql)

    @staticmethod
    def parse_json(content: str) -> Optional[dict]:
        """
        Parse JSON from LLM response. Handles responses with markdown fences
        and minor formatting issues.
        """
        if not content:
            return None

        # Strip markdown code fences
        content = re.sub(r"```(?:json)?", "", content, flags=re.IGNORECASE)
        content = content.replace("```", "").strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try json-repair for minor issues (trailing commas, single quotes)
            try:
                import json_repair
                return json_repair.loads(content)
            except Exception:
                logger.warning("Failed to parse JSON from LLM response: %.200s", content)
                return None


class EmbeddingClient:
    """
    OpenAI embedding wrapper.

    Usage:
        client = EmbeddingClient()
        vector = client.embed("show me all vip customers")
    """

    def __init__(self):
        self._client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model

    def embed(self, text: str) -> list[float]:
        """Return 1536-dim embedding vector for the given text."""
        text = text.replace("\n", " ").strip()
        try:
            resp = self._client.embeddings.create(input=[text], model=self.model)
            return resp.data[0].embedding
        except OpenAIError as exc:
            logger.error("Embedding API error: %s", exc)
            raise RuntimeError(f"Embedding call failed: {exc}") from exc

"""
LLM Service for Answer Generation
Supports OpenAI, Anthropic, and other providers via LiteLLM
"""
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM response with metadata"""
    answer: str
    model: str
    tokens_used: int
    finish_reason: str


class LLMService:
    """LLM service for answer generation"""
    
    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4",
        temperature: float = 0.1,
        max_tokens: int = 2000
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize based on provider
        if provider == "openai":
            self._init_openai()
        elif provider == "anthropic":
            self._init_anthropic()
        else:
            self._init_litellm()
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            raise
    
    def _init_anthropic(self):
        """Initialize Anthropic client"""
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            logger.info("Anthropic client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic: {e}")
            raise
    
    def _init_litellm(self):
        """Initialize LiteLLM for other providers"""
        try:
            import litellm
            self.client = litellm
            logger.info("LiteLLM initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LiteLLM: {e}")
            raise
    
    def generate_answer(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """Generate answer using LLM"""
        if self.provider == "openai":
            return self._generate_openai(query, context, system_prompt)
        elif self.provider == "anthropic":
            return self._generate_anthropic(query, context, system_prompt)
        else:
            return self._generate_litellm(query, context, system_prompt)
    
    def _generate_openai(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str]
    ) -> LLMResponse:
        """Generate answer using OpenAI"""
        messages = []
        
        # System prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": self._get_default_system_prompt()
            })
        
        # User message with context
        user_message = self._format_user_message(query, context)
        messages.append({"role": "user", "content": user_message})
        
        # Generate
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        return LLMResponse(
            answer=response.choices[0].message.content,
            model=response.model,
            tokens_used=response.usage.total_tokens,
            finish_reason=response.choices[0].finish_reason
        )
    
    def _generate_anthropic(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str]
    ) -> LLMResponse:
        """Generate answer using Anthropic"""
        # Format message
        user_message = self._format_user_message(query, context)
        
        # Generate
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt or self._get_default_system_prompt(),
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        return LLMResponse(
            answer=response.content[0].text,
            model=response.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason
        )
    
    def _generate_litellm(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str]
    ) -> LLMResponse:
        """Generate answer using LiteLLM"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": self._get_default_system_prompt()
            })
        
        user_message = self._format_user_message(query, context)
        messages.append({"role": "user", "content": user_message})
        
        response = self.client.completion(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        return LLMResponse(
            answer=response.choices[0].message.content,
            model=response.model,
            tokens_used=response.usage.total_tokens,
            finish_reason=response.choices[0].finish_reason
        )
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for RAG"""
        return """You are a helpful AI assistant that answers questions based on provided context.

Instructions:
1. Answer the question using ONLY the information from the provided context
2. Be accurate and cite specific information when possible
3. If the context doesn't contain enough information to answer, say so clearly
4. Keep answers concise but comprehensive
5. Reference the citation numbers [0], [1], etc. when using specific information from the context
6. Do not make up information that's not in the context

Format your response clearly and professionally."""
    
    def _format_user_message(self, query: str, context: str) -> str:
        """Format user message with query and context"""
        return f"""Context:
{context}

Question: {query}

Please provide a detailed answer based on the context above. Use citation numbers [0], [1], etc. to reference specific information from the context."""


class PromptTemplates:
    """Collection of prompt templates for different scenarios"""
    
    @staticmethod
    def qa_prompt(query: str, context: str) -> str:
        """Question answering prompt"""
        return f"""Based on the following context, please answer the question.

Context:
{context}

Question: {query}

Answer:"""
    
    @staticmethod
    def summarization_prompt(text: str) -> str:
        """Summarization prompt"""
        return f"""Please provide a comprehensive summary of the following text:

{text}

Summary:"""
    
    @staticmethod
    def multihop_qa_prompt(query: str, context: str) -> str:
        """Multi-hop question answering prompt"""
        return f"""You are answering a complex question that may require combining information from multiple sources.

Context:
{context}

Question: {query}

Please provide a detailed answer that:
1. Combines relevant information from different sources
2. Shows the reasoning chain
3. Cites specific sources using [citation_id]

Answer:"""
    
    @staticmethod
    def citation_aware_prompt() -> str:
        """System prompt that emphasizes citations"""
        return """You are a helpful assistant that provides accurate answers with proper citations.

CRITICAL INSTRUCTIONS:
- Always cite your sources using [0], [1], [2] format
- Each factual claim should be followed by its citation
- If multiple sources support a claim, cite all relevant ones
- Only use information from the provided context
- If the context doesn't contain the answer, say "I don't have enough information"
- Be precise and accurate

Example:
"The company was founded in 2020 [0]. It operates in 15 countries [1,2] and has 500 employees [2]."
"""

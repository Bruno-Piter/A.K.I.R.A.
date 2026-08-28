"""LLM/embeddings adapter stubs. Provider selected via settings (openai | ollama)."""

from app.core.settings import settings


class LLMManager:
    def provider(self) -> str:
        return settings.llm_provider

    def embeddings_provider(self) -> str:
        return settings.embeddings_provider


llm_manager = LLMManager()

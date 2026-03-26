"""Abstract base for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class EmbeddingResponse:
    """Response from an embedding call."""

    embeddings: list[list[float]]
    model: str
    input_tokens: int


class BaseLLM(ABC):
    """Abstract LLM interface. Implementations wrap specific providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
    ) -> LLMResponse:
        """Generate a completion from a list of messages."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream a completion token by token."""
        ...


class BaseEmbedder(ABC):
    """Abstract embedding interface."""

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        input_type: str = "search_document",
    ) -> EmbeddingResponse:
        """Generate embeddings for a list of texts.

        Args:
            texts: Texts to embed.
            input_type: "search_document" for indexing, "search_query" for queries.
        """
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding vector dimensions."""
        ...

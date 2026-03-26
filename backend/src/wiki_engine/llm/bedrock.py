"""AWS Bedrock LLM and embedding providers."""

import json
import logging
from typing import AsyncIterator

import boto3

from wiki_engine.config import settings
from wiki_engine.llm.base import (
    BaseEmbedder,
    BaseLLM,
    EmbeddingResponse,
    LLMResponse,
)

logger = logging.getLogger(__name__)


def _get_bedrock_client(service: str = "bedrock-runtime"):
    """Create a Bedrock client using configured credentials."""
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_profile:
        session = boto3.Session(profile_name=settings.aws_profile)
        return session.client(service, **kwargs)
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service, **kwargs)


class BedrockLLM(BaseLLM):
    """Claude models via AWS Bedrock Converse API."""

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or settings.llm_analysis_model
        self._client = _get_bedrock_client()

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
    ) -> LLMResponse:
        """Generate via Bedrock Converse API (sync wrapper — Bedrock SDK is sync)."""
        bedrock_messages = _to_bedrock_messages(messages)
        system_prompt = _extract_system(messages)

        kwargs: dict = {
            "modelId": self.model_id,
            "messages": bedrock_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]
        if stop_sequences:
            kwargs["inferenceConfig"]["stopSequences"] = stop_sequences

        response = self._client.converse(**kwargs)

        content = response["output"]["message"]["content"][0]["text"]
        usage = response["usage"]

        return LLMResponse(
            content=content,
            model=self.model_id,
            input_tokens=usage["inputTokens"],
            output_tokens=usage["outputTokens"],
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream via Bedrock ConverseStream API."""
        bedrock_messages = _to_bedrock_messages(messages)
        system_prompt = _extract_system(messages)

        kwargs: dict = {
            "modelId": self.model_id,
            "messages": bedrock_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        response = self._client.converse_stream(**kwargs)

        for event in response["stream"]:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    yield delta["text"]


class BedrockEmbedder(BaseEmbedder):
    """Cohere Embed v4 (or Titan) via AWS Bedrock."""

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or settings.embedding_model
        self._client = _get_bedrock_client()
        self._dimensions = settings.embedding_dimensions

    async def embed(
        self,
        texts: list[str],
        *,
        input_type: str = "search_document",
    ) -> EmbeddingResponse:
        """Generate embeddings via Bedrock InvokeModel."""
        if "cohere" in self.model_id:
            return await self._embed_cohere(texts, input_type)
        return await self._embed_titan(texts)

    async def _embed_cohere(
        self, texts: list[str], input_type: str
    ) -> EmbeddingResponse:
        """Cohere Embed v3/v4 via Bedrock."""
        body = json.dumps({
            "texts": texts,
            "input_type": input_type,
            "truncate": "END",
        })
        response = self._client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return EmbeddingResponse(
            embeddings=result["embeddings"],
            model=self.model_id,
            input_tokens=result.get("meta", {}).get("billed_units", {}).get("input_tokens", 0),
        )

    async def _embed_titan(self, texts: list[str]) -> EmbeddingResponse:
        """Amazon Titan Text Embeddings V2 via Bedrock."""
        all_embeddings = []
        total_tokens = 0
        for text in texts:
            body = json.dumps({
                "inputText": text,
                "dimensions": self._dimensions,
            })
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            all_embeddings.append(result["embedding"])
            total_tokens += result.get("inputTextTokenCount", 0)
        return EmbeddingResponse(
            embeddings=all_embeddings,
            model=self.model_id,
            input_tokens=total_tokens,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions


class ModelRouter:
    """Routes tasks to appropriate model tier.

    - Heavy (Opus): Architecture synthesis, complex legacy code analysis
    - Analysis (Sonnet): Main workhorse — code research, page generation
    - Fast (Haiku): Classification, metadata extraction, summaries
    """

    def __init__(self):
        self.heavy = BedrockLLM(settings.llm_heavy_model)
        self.analysis = BedrockLLM(settings.llm_analysis_model)
        self.fast = BedrockLLM(settings.llm_fast_model)
        self.embedder = BedrockEmbedder()


# -- Helpers --

def _to_bedrock_messages(messages: list[dict[str, str]]) -> list[dict]:
    """Convert simple message dicts to Bedrock Converse format."""
    result = []
    for msg in messages:
        if msg["role"] == "system":
            continue  # Handled separately
        result.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}],
        })
    return result


def _extract_system(messages: list[dict[str, str]]) -> str | None:
    """Extract system message if present."""
    for msg in messages:
        if msg["role"] == "system":
            return msg["content"]
    return None

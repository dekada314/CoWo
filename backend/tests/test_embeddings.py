import asyncio
import json

import httpx

from src.core.settings import LLMSettings
from src.infrastructure.llm.embeddings import OpenAIEmbeddingClient


def test_qwen_embedding_uses_retrieval_instruction_only_for_queries():
    async def scenario():
        requests = []

        async def handle(request):
            body = json.loads(request.content)
            requests.append(body)
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": index, "embedding": [1.0, 0.0, 0.0]}
                        for index, _ in enumerate(body["input"])
                    ]
                },
            )

        config = LLMSettings(
            _env_file=None,
            model_embedding="qwen3-embedding:0.6b",
            embedding_dimensions=3,
        )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle)
        ) as client:
            embeddings = OpenAIEmbeddingClient(client, config, 3)
            await embeddings.embed_passages(["Документ"])
            await embeddings.embed_queries(["Вопрос"])

        assert requests[0]["input"] == ["Документ"]
        assert requests[1]["input"] == [
            "Instruct: Given a user question, retrieve the most relevant "
            "knowledge from the document collection.\nQuery: Вопрос"
        ]
        assert all(request["dimensions"] == 3 for request in requests)

    asyncio.run(scenario())

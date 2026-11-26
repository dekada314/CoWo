import asyncio
import json

import httpx
import pytest

from src.application.ingestion.contracts import IngestionError, KnowledgeCard
from src.core.settings import LLMSettings
from src.infrastructure.llm.analyst import AnalystAgent

CARD = {
    "summary": "Document summary",
    "key_points": ["Key point"],
    "community": {"name": "Computing", "description": "Computer science"},
    "domain": {"name": "RAG", "description": "Retrieval augmented generation"},
    "concepts": [{"name": "Chunking", "description": "Splitting source text"}],
}


def test_analyst_maps_all_fragments_and_bounds_concurrency():
    async def scenario():
        active, peak = 0, 0
        seen = []

        async def handle(request):
            nonlocal active, peak
            body = json.loads(request.content)
            seen.append(body)
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            mapped = "Summarize the evidence" in body["messages"][0]["content"]
            result = {"summary": "Facts", "concepts": ["Chunking"]} if mapped else CARD
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": json.dumps(result)},
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            config = LLMSettings(
                _env_file=None,
                model_analyst="local-test",
                input_chars=6000,
                max_concurrency=2,
            )
            card = await AnalystAgent(client, config).analyze(
                [f"part-{i}:" + "x" * 3990 for i in range(5)]
            )
        assert card == KnowledgeCard.model_validate(CARD)
        assert len(seen) == 6
        assert peak == 2
        for i in range(5):
            assert any(f"part-{i}:" in r["messages"][1]["content"] for r in seen)
        assert all(r["model"] == "local-test" for r in seen)
        assert "source_content" in seen[0]["messages"][1]["content"]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("status", "retryable"), [(429, True), (503, True), (401, False)]
)
def test_provider_errors_are_classified_without_leaking_body(status, retryable):
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(status, text="sensitive provider body")
            )
        ) as client:
            agent = AnalystAgent(
                client, LLMSettings(_env_file=None, model_analyst="test")
            )
            with pytest.raises(IngestionError) as error:
                await agent.analyze(["text"])
        assert error.value.retryable is retryable
        assert str(error.value) == f"llm_http_{status}"

    asyncio.run(scenario())


def test_invalid_card_is_rejected():
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": '{"summary": "incomplete"}'}}
                        ]
                    },
                )
            )
        ) as client:
            agent = AnalystAgent(
                client, LLMSettings(_env_file=None, model_analyst="test")
            )
            with pytest.raises(IngestionError, match="llm_invalid_structured_output"):
                await agent.analyze(["text"])

    asyncio.run(scenario())


def test_analysis_budget_rejects_oversized_document_before_llm_calls():
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: pytest.fail("LLM must not be called")
            )
        ) as client:
            agent = AnalystAgent(
                client,
                LLMSettings(
                    _env_file=None,
                    model_analyst="test",
                    input_chars=6000,
                    max_calls_per_document=2,
                ),
            )
            with pytest.raises(IngestionError, match="budget_exceeded"):
                await agent.analyze(["x" * 4000] * 3)

    asyncio.run(scenario())

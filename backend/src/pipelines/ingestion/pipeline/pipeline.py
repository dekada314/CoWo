from collections.abc import Awaitable, Callable
from typing import Protocol

from langgraph.graph import END, START, StateGraph

from src.application.ingestion.contracts import KnowledgeCard
from src.domain.enums import ProcessingStage
from src.pipelines.ingestion.pipeline.state import IngestionState


class AsyncParser(Protocol):
    async def parse(self, content: bytes, filename: str) -> list[str]: ...


class Analyst(Protocol):
    async def analyze(self, fragments: list[str]) -> KnowledgeCard: ...


class IngestionPipeline:
    def __init__(self, parser: AsyncParser, analyst: Analyst):
        self.parser = parser
        self.analyst = analyst

    async def run(
        self,
        content: bytes,
        filename: str,
        progress: Callable[[ProcessingStage], Awaitable[None]],
    ) -> KnowledgeCard:
        async def extract(state: IngestionState):
            await progress(ProcessingStage.EXTRACTION)
            fragments = await self.parser.parse(state["content"], state["filename"])
            return {"fragments": fragments, "content": b""}

        async def analyze(state: IngestionState):
            await progress(ProcessingStage.GRAPH_EXTRACTION)
            return {"card": await self.analyst.analyze(state["fragments"])}

        graph = StateGraph(IngestionState)
        graph.add_node("extract", extract)
        graph.add_node("analyst", analyze)
        graph.add_edge(START, "extract")
        graph.add_edge("extract", "analyst")
        graph.add_edge("analyst", END)
        result = await graph.compile().ainvoke(
            {"content": content, "filename": filename}
        )
        return result["card"]

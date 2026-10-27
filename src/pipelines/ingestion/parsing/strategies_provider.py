from dishka import Provider, Scope, provide

from src.core.settings import Settings
from src.pipelines.ingestion.chunkers.chunker import ChonkieChunker
from src.pipelines.ingestion.parsing.parser_context import RAGDocumentParser
from src.pipelines.ingestion.parsing.pdf_router import PdfRouter
from src.pipelines.ingestion.parsing.strategies.docling_strategy import (
    DoclingStrategy,
)
from src.pipelines.ingestion.parsing.strategies.docx_strategy import (
    DocxStrategy,
)
from src.pipelines.ingestion.parsing.strategies.pdf_parser import PdfStrategy
from src.pipelines.ingestion.parsing.strategies.plain_text_strategy import (
    PlainTextStrategy,
)


class ParsingProvider(Provider):
    def __init__(
        self, config: Settings, scope=Scope.APP, component=None, when=None
    ):
        super().__init__(scope, component, when)
        self._config = config

    def docling_strategy(self) -> DoclingStrategy:
        return DoclingStrategy(
            embedding_model_id=self._config.llm.model_embedding,
            max_tokens=self._config.parsing.max_chunk_tokens,
        )

    def docx_strategy(self) -> DocxStrategy:
        return DocxStrategy()

    def pymupdf_strategy(self, chunker: ChonkieChunker) -> PdfStrategy:
        return PdfStrategy(chunker=chunker)

    def plain_text_strategy(self, chunker: ChonkieChunker) -> PlainTextStrategy:
        return PlainTextStrategy(chunker=chunker)

    def pdf_router(
        self,
        docling: DoclingStrategy,
        pymupdf: PdfStrategy,
    ) -> PdfRouter:
        return PdfRouter(
            docling,
            pymupdf,
            docling_enabled=self._config.parsing.docling_enabled,
        )

    def document_loader(
        self,
        pdf_router: PdfRouter,
        plain_strategy: PlainTextStrategy,
        docx_strategy: DocxStrategy,
    ) -> RAGDocumentParser:
        loader = RAGDocumentParser()
        loader.register_strategy("pdf", pdf_router)
        loader.register_strategy("docx", docx_strategy)
        loader.register_strategy("txt", plain_strategy)
        loader.register_strategy("md", plain_strategy)
        return loader

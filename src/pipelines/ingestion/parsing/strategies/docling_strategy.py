import io

from docling.chunking import HybridChunker
from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)
from transformers import AutoTokenizer

from pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
)


class DoclingStrategy:
    def __init__(self, embedding_model_id: str, max_tokens: int = 512):
        self._converter = DocumentConverter()
        tokenizer = AutoTokenizer.from_pretrained(embedding_model_id)
        self._chunker = HybridChunker(
            tokenizer=HuggingFaceTokenizer(
                tokenizer=tokenizer, max_tokens=max_tokens
            ),
            merge_peers=True,
        )

    async def parse(
        self, content: bytes, filename: str = "document.pdf"
    ) -> list[ParsedChunk]:
        stream = DocumentStream(name=filename, stream=io.BytesIO(content))
        result = self._converter.convert(stream)

        chunks: list[ParsedChunk] = []
        for i, chunk in enumerate(self._chunker.chunk(dl_doc=result.document)):
            chunks.append(
                ParsedChunk(
                    text=self._chunker.contextualize(chunk=chunk),
                    raw_text=chunk.text,
                    index=i,
                    metadata={
                        "headings": getattr(chunk.meta, "headings", []),
                        "page": getattr(chunk.meta, "page", None),
                    },
                )
            )
        return chunks

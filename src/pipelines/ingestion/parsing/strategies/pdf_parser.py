import fitz

from pipelines.ingestion.parsing.strategies.parser_strategy import ParsedChunk


class PdfStrategy:
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def parse(
        self, content: bytes, filename: str = "unknown.pdf"
    ) -> list[ParsedChunk]:
        doc = fitz.open(stream=content, filetype="pdf")
        chunks: list[ParsedChunk] = []
        index = 0
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            step = self._chunk_size - self._overlap
            for start in range(0, len(text), step):
                piece = text[start : start + self._chunk_size]
                if not piece.strip():
                    continue
                chunks.append(
                    ParsedChunk(
                        text=piece,
                        raw_text=piece,
                        index=index,
                        metadata={"page": page_num},
                    )
                )
                index += 1
        doc.close()
        return chunks

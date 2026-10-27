import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Sequence

from chonkie import RecursiveChunker
from transformers import AutoTokenizer, PreTrainedTokenizerFast

from src.pipelines.ingestion.chunkers.base_chunker import BaseChunker
from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
    ParsedPage,
)


@dataclass(frozen=True, slots=True)
class _PageSpan:
    start_char: int
    end_char: int
    page_number: int
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ChunkSpan:
    start_char: int
    end_char: int
    token_count: int


@lru_cache(maxsize=4)
def _load_tokenizer(model_name: str) -> PreTrainedTokenizerFast:
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if not isinstance(tokenizer, PreTrainedTokenizerFast):
        raise TypeError(
            f"Tokenizer {model_name!r} must be a fast Hugging Face tokenizer "
            "because offset_mapping is required."
        )
    return tokenizer


class ChonkieChunker(BaseChunker):
    _DOCUMENT_SEPARATOR = "\n"

    def __init__(
        self,
        chunk_size_tokens: int = 512,
        chunk_overlap_tokens: int = 64,
        min_chunk_size_tokens: int = 128,
        tokenizer_name: str = "intfloat/multilingual-e5-small",
    ) -> None:
        self._validate_config(
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            min_chunk_size_tokens=min_chunk_size_tokens,
        )

        self.chunk_size_tokens = chunk_size_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.min_chunk_size_tokens = min_chunk_size_tokens
        self.tokenizer_name = tokenizer_name

        self._tokenizer = _load_tokenizer(tokenizer_name)
        self._content_budget_tokens = chunk_size_tokens - chunk_overlap_tokens

        self._chunker = RecursiveChunker(
            tokenizer=self._tokenizer,
            chunk_size=self._content_budget_tokens,
            min_characters_per_chunk=1,
        )

    def get_chunks(self, pages: list[ParsedPage]) -> list[ParsedChunk]:
        if not pages:
            return []

        chunks: list[ParsedChunk] = []
        order = 0

        for document_pages in self._group_pages_by_document(pages):
            document_chunks = self._chunk_document(
                pages=document_pages,
                initial_order=order,
            )
            chunks.extend(document_chunks)
            order += len(document_chunks)

        return chunks

    def _chunk_document(
        self,
        pages: Sequence[ParsedPage],
        initial_order: int,
    ) -> list[ParsedChunk]:
        text, page_spans = self._build_document_text(pages)
        if not text or not page_spans:
            return []

        token_offsets = self._get_token_offsets(text)
        if not token_offsets:
            return []

        recursive_chunks = self._chunker.chunk(text)
        base_spans = self._extract_chunk_spans(text, recursive_chunks)
        if not base_spans:
            return []

        base_spans = self._merge_small_spans(text, base_spans)
        final_spans = self._apply_overlap(text, base_spans, token_offsets)

        result: list[ParsedChunk] = []

        for index, span in enumerate(final_spans):
            page_start, source_pages = self._pages_for_span(
                start_char=span.start_char,
                end_char=span.end_char,
                page_spans=page_spans,
            )

            raw_text = text[span.start_char : span.end_char]
            metadata = self._build_metadata(
                page_spans=page_spans,
                source_pages=source_pages,
            )

            result.append(
                ParsedChunk(
                    text=raw_text,
                    raw_text=raw_text,
                    index=initial_order + index,
                    metadata=metadata,
                )
            )

        return result

    def _build_document_text(
        self,
        pages: Sequence[ParsedPage],
    ) -> tuple[str, list[_PageSpan]]:
        parts: list[str] = []
        page_spans: list[_PageSpan] = []
        offset = 0
        sep_len = len(self._DOCUMENT_SEPARATOR)

        for page in pages:
            normalized = self.normalize_text(page.text)
            if not normalized:
                continue

            if parts:
                parts.append(self._DOCUMENT_SEPARATOR)
                offset += sep_len

            start = offset
            parts.append(normalized)
            offset += len(normalized)

            page_spans.append(
                _PageSpan(
                    start_char=start,
                    end_char=offset,
                    page_number=page.page_number,
                    metadata=dict(page.metadata or {}),
                )
            )

        return "".join(parts), page_spans

    def _extract_chunk_spans(
        self,
        text: str,
        recursive_chunks: Iterable[Any],
    ) -> list[_ChunkSpan]:
        spans: list[_ChunkSpan] = []

        for item in recursive_chunks:
            start = getattr(item, "start_index", None)
            end = getattr(item, "end_index", None)

            if not isinstance(start, int) or not isinstance(end, int):
                raise TypeError(
                    "Chonkie chunk must expose integer start_index "
                    "and end_index attributes."
                )

            start, end = self._trim_span(text, start, end)
            if start >= end:
                continue

            token_count = self._count_tokens(text[start:end])
            if token_count == 0:
                continue

            spans.append(
                _ChunkSpan(
                    start_char=start,
                    end_char=end,
                    token_count=token_count,
                )
            )

        return spans

    def _merge_small_spans(
        self,
        text: str,
        spans: list[_ChunkSpan],
    ) -> list[_ChunkSpan]:
        if len(spans) < 2:
            return spans

        merged: list[_ChunkSpan] = []
        min_tokens = self.min_chunk_size_tokens
        budget = self._content_budget_tokens

        for current in spans:
            if not merged:
                merged.append(current)
                continue

            previous = merged[-1]
            if (
                previous.token_count >= min_tokens
                and current.token_count >= min_tokens
            ):
                merged.append(current)
                continue

            combined_start = previous.start_char
            combined_end = current.end_char
            combined_tokens = self._count_tokens(
                text[combined_start:combined_end]
            )

            if combined_tokens <= budget:
                merged[-1] = _ChunkSpan(
                    start_char=combined_start,
                    end_char=combined_end,
                    token_count=combined_tokens,
                )
            else:
                merged.append(current)

        return merged

    def _apply_overlap(
        self,
        text: str,
        spans: list[_ChunkSpan],
        token_offsets: list[tuple[int, int]],
    ) -> list[_ChunkSpan]:
        overlap = self.chunk_overlap_tokens
        if overlap == 0 or len(spans) < 2:
            return spans

        token_starts = [start for start, _ in token_offsets]
        token_ends = [end for _, end in token_offsets]
        hard_limit = self.chunk_size_tokens

        result: list[_ChunkSpan] = [spans[0]]

        for span in spans[1:]:
            body_token_index = bisect_right(token_ends, span.start_char)
            overlap_token_index = max(0, body_token_index - overlap)

            overlap_start = token_starts[overlap_token_index]
            overlap_start, overlap_end = self._trim_span(
                text, overlap_start, span.end_char
            )

            if overlap_start >= overlap_end:
                result.append(span)
                continue

            token_count = self._count_tokens(text[overlap_start:overlap_end])

            while (
                token_count > hard_limit
                and overlap_token_index < body_token_index
            ):
                overlap_token_index += 1
                overlap_start = token_starts[overlap_token_index]
                overlap_start, overlap_end = self._trim_span(
                    text, overlap_start, span.end_char
                )
                token_count = self._count_tokens(
                    text[overlap_start:overlap_end]
                )

            result.append(
                _ChunkSpan(
                    start_char=overlap_start,
                    end_char=overlap_end,
                    token_count=token_count,
                )
            )

        return result

    def _get_token_offsets(self, text: str) -> list[tuple[int, int]]:
        encoding = self._tokenizer(
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
        )

        offsets = encoding.get("offset_mapping")
        if offsets is None:
            raise RuntimeError(
                f"Tokenizer {self.tokenizer_name!r} did not return "
                "offset_mapping."
            )

        return [
            (int(start), int(end))
            for start, end in offsets
            if int(end) > int(start)
        ]

    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0

        return len(
            self._tokenizer.encode(
                text,
                add_special_tokens=False,
                truncation=False,
            )
        )

    @staticmethod
    def _pages_for_span(
        start_char: int,
        end_char: int,
        page_spans: Sequence[_PageSpan],
    ) -> tuple[int, list[int]]:
        intersecting = [
            page.page_number
            for page in page_spans
            if page.start_char < end_char and page.end_char > start_char
        ]

        if not intersecting:
            page_starts = [page.start_char for page in page_spans]
            index = max(0, bisect_right(page_starts, start_char) - 1)
            page_number = page_spans[index].page_number
            return page_number, [page_number]

        source_pages = list(dict.fromkeys(intersecting))
        return source_pages[0], source_pages

    @staticmethod
    def _build_metadata(
        page_spans: Sequence[_PageSpan],
        source_pages: Sequence[int],
    ) -> dict[str, Any]:
        source_page_set = set(source_pages)

        first_page = next(
            (
                page
                for page in page_spans
                if page.page_number in source_page_set
            ),
            None,
        )

        metadata = dict(first_page.metadata) if first_page else {}
        metadata["source_page_number"] = source_pages[0]
        metadata["source_page_numbers"] = list(source_pages)
        return metadata

    @staticmethod
    def _trim_span(
        text: str,
        start_char: int,
        end_char: int,
    ) -> tuple[int, int]:
        start_char = max(0, start_char)
        end_char = min(len(text), end_char)

        while start_char < end_char and text[start_char].isspace():
            start_char += 1

        while end_char > start_char and text[end_char - 1].isspace():
            end_char -= 1

        return start_char, end_char

    @staticmethod
    def _group_pages_by_document(
        pages: Sequence[ParsedPage],
    ) -> list[list[ParsedPage]]:
        grouped: dict[str, list[ParsedPage]] = {}
        for page in pages:
            grouped.setdefault(page.document_id, []).append(page)
        return list(grouped.values())

    @staticmethod
    def _validate_config(
        chunk_size_tokens: int,
        chunk_overlap_tokens: int,
        min_chunk_size_tokens: int,
    ) -> None:
        if chunk_size_tokens <= 0:
            raise ValueError("chunk_size_tokens must be greater than 0")

        if chunk_overlap_tokens < 0:
            raise ValueError(
                "chunk_overlap_tokens must be greater than or equal to 0"
            )

        if chunk_overlap_tokens >= chunk_size_tokens:
            raise ValueError(
                "chunk_overlap_tokens must be smaller than chunk_size_tokens"
            )

        if min_chunk_size_tokens <= 0:
            raise ValueError("min_chunk_size_tokens must be greater than 0")

        if min_chunk_size_tokens > chunk_size_tokens - chunk_overlap_tokens:
            raise ValueError(
                "min_chunk_size_tokens must not exceed "
                "chunk_size_tokens - chunk_overlap_tokens"
            )

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""

        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

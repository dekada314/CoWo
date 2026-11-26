import asyncio
import io
from time import perf_counter

import pytest

from src.application.ingestion.contracts import IngestionError
from src.core.settings import get_settings
from src.pipelines.ingestion.parsing.async_parser import SubprocessParser
from src.pipelines.ingestion.parsing.process import parse_document


def _pdf_with_text(text: str) -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    contents = DecodedStreamObject()
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    contents.set_data(f"BT /F1 12 Tf 50 790 Td ({safe_text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(contents)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_txt_subprocess_and_unicode():
    text = "Текст документа\n" * 100
    fragments = asyncio.run(
        SubprocessParser(get_settings()).parse(text.encode(), "file.txt")
    )
    assert "Текст документа" in fragments[0]
    assert sum(len(fragment) for fragment in fragments) <= len(text)


def test_docx_and_pdf_use_same_chunk_budget():
    from docx import Document

    docx = Document()
    docx.add_paragraph("Document text " * 100)
    stream = io.BytesIO()
    docx.save(stream)
    pdf_data = _pdf_with_text("Document text")
    for name, content in [("file.docx", stream.getvalue()), ("file.pdf", pdf_data)]:
        chunks = asyncio.run(parse_document(content, name, 100, 5000))
        assert chunks
        assert all(len(chunk.text) <= 100 for chunk in chunks)


def test_docx_preserves_headings_and_table_only_content():
    from docx import Document

    docx = Document()
    docx.add_heading("Заголовок раздела", level=1)
    table = docx.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Параметр"
    table.cell(0, 1).text = "Значение"
    table.cell(1, 0).text = "Протокол"
    table.cell(1, 1).text = "HTTPS"
    stream = io.BytesIO()
    docx.save(stream)

    chunks = asyncio.run(parse_document(stream.getvalue(), "table.docx", 1000, 5000))
    text = "\n".join(chunk.text for chunk in chunks)

    assert "Заголовок раздела" in text
    assert "Параметр | Значение" in text
    assert "Протокол | HTTPS" in text


def test_empty_and_corrupt_docx_return_specific_safe_errors():
    from docx import Document

    empty = Document()
    stream = io.BytesIO()
    empty.save(stream)
    parser = SubprocessParser(get_settings())

    with pytest.raises(IngestionError, match="document_has_no_text"):
        asyncio.run(parser.parse(stream.getvalue(), "empty.docx"))
    with pytest.raises(IngestionError, match="document_parse_failed"):
        asyncio.run(parser.parse(b"not a zip package", "broken.docx"))


def test_image_only_pdf_fails_fast_without_ocr_dependencies():
    from pypdf import PdfWriter

    pdf = PdfWriter()
    pdf.add_blank_page(width=595, height=842)
    stream = io.BytesIO()
    pdf.write(stream)
    content = stream.getvalue()
    started = perf_counter()

    with pytest.raises(IngestionError, match="document_has_no_text"):
        asyncio.run(SubprocessParser(get_settings()).parse(content, "scan.pdf"))

    assert perf_counter() - started < 10


def test_parse_rejects_excessive_extracted_text():
    with pytest.raises(ValueError, match="document_text_limit_exceeded"):
        asyncio.run(parse_document(b"text" * 1000, "file.txt", 100, 1000))

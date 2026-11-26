import asyncio
import json
import os
import sys
from pathlib import Path
from time import perf_counter

import structlog

from src.application.ingestion.contracts import IngestionError
from src.core.settings import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[4]
logger = structlog.get_logger(__name__)


class SubprocessParser:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def parse(self, content: bytes, filename: str) -> list[str]:
        extension = Path(filename).suffix.lower().lstrip(".")
        attributes = {
            "filename_extension": extension,
            "file_size_bytes": len(content),
        }
        started = perf_counter()
        logger.info("document_parse_started", **attributes)
        env = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "HOME",
                "LANG",
                "OMP_NUM_THREADS",
            }
        }
        env["OMP_NUM_THREADS"] = "1"
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "src.pipelines.ingestion.parsing.process",
            filename,
            str(self.settings.llm.input_chars // 2),
            str(self.settings.ingestion.max_text_chars),
            str(self.settings.app.max_upload_size_mb * 1024 * 1024),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=BACKEND_ROOT,
        )
        try:
            async with asyncio.timeout(self.settings.ingestion.parse_timeout_seconds):
                output, stderr = await process.communicate(content)
            payload = json.loads(output)
            if process.returncode:
                code = (
                    payload.get("error", "document_parse_failed")
                    if isinstance(payload, dict)
                    else "document_parse_failed"
                )
                logger.warning(
                    "document_parse_failed",
                    **attributes,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_code=code,
                    parser_error_type=(
                        payload.get("error_type") if isinstance(payload, dict) else None
                    ),
                    stderr_chars=len(stderr),
                )
                raise IngestionError(code)
            if not isinstance(payload, list):
                raise ValueError("parser output is not a list")
            texts = [chunk["text"] for chunk in payload]
            if sum(map(len, texts)) > self.settings.ingestion.max_text_chars:
                raise IngestionError("document_text_limit_exceeded")
            logger.info(
                "document_parse_completed",
                **attributes,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                fragment_count=len(texts),
                extracted_chars=sum(map(len, texts)),
            )
            return texts
        except TimeoutError as exc:
            logger.warning(
                "document_parse_failed",
                **attributes,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                error_code="document_parse_timeout",
            )
            raise IngestionError("document_parse_timeout") from exc
        except IngestionError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning(
                "document_parse_failed",
                **attributes,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                error_code="document_parse_failed",
                parser_error_type=type(exc).__name__,
            )
            raise IngestionError("document_parse_failed") from exc
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

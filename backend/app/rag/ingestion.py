from __future__ import annotations

import json
import logging
import os
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
from dataclasses import dataclass, field
from threading import Lock
from time import perf_counter
from typing import Any, Dict, List, Optional

from werkzeug.datastructures import FileStorage

from app.ai.agents.permissions import can_upload_document
from app.db.base import SessionLocal
from app.models.documents import PendingDocumentUpload
from app.rag.content_guardrails import check_untrusted_document_text
from app.rag.document_classifier import classify_document
from app.rag.document_guardrails import (
    check_classification,
    check_extracted_text,
)
from app.rag.document_image_detector import check_text_is_document
from app.rag.duplicate_detector import (
    calculate_sha256,
    calculate_text_hash,
    calculate_visual_hashes,
    find_exact_duplicate,
    find_text_duplicate,
    find_visual_near_duplicate,
    normalize_document_text,
)
from app.rag.file_validation import validate_file
from app.rag.text_extraction import extract_text
from app.storage.temp_storage import delete_temp_file, save_temp_upload


logger = logging.getLogger(__name__)


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

DEFAULT_MAX_INGESTION_WORKERS = 2
MAX_ALLOWED_INGESTION_WORKERS = 4

DEFAULT_EXTRACTION_TIMEOUT_SECONDS = 120.0
DEFAULT_ANALYSIS_TIMEOUT_SECONDS = 30.0
DEFAULT_DUPLICATE_TIMEOUT_SECONDS = 15.0
DEFAULT_VISUAL_TIMEOUT_SECONDS = 30.0
DEFAULT_SETTLE_TIMEOUT_SECONDS = 0.25
DEFAULT_MIN_DUPLICATE_TEXT_CHARS = 32


def _configured_worker_count() -> int:
    """
    Read the bounded shared-ingestion worker count from the environment.

    A process-wide executor prevents every Flask request from creating its own
    unbounded pool of worker threads.
    """

    raw_value = os.getenv(
        "DOCUMENT_INGESTION_WORKERS",
        str(DEFAULT_MAX_INGESTION_WORKERS),
    )

    try:
        worker_count = int(raw_value)
    except (TypeError, ValueError):
        worker_count = DEFAULT_MAX_INGESTION_WORKERS

    return max(
        1,
        min(worker_count, MAX_ALLOWED_INGESTION_WORKERS),
    )


def _configured_seconds(
    name: str,
    default: float,
) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = default
    return max(0.1, min(value, 600.0))


def _configured_min_duplicate_text_chars() -> int:
    raw_value = os.getenv(
        "DOCUMENT_MIN_DUPLICATE_TEXT_CHARS",
        str(DEFAULT_MIN_DUPLICATE_TEXT_CHARS),
    )
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = DEFAULT_MIN_DUPLICATE_TEXT_CHARS
    return max(8, min(value, 2000))


def _test_mode_enabled() -> bool:
    explicit = str(
        os.getenv("AI_HOME_MANAGER_TESTING", "")
    ).strip().lower()
    return (
        explicit in {"1", "true", "yes", "on"}
        or bool(os.getenv("PYTEST_CURRENT_TEST"))
    )


_SHARED_EXECUTOR = ThreadPoolExecutor(
    max_workers=_configured_worker_count(),
    thread_name_prefix="document-ingest",
)


@dataclass
class IngestionContext:
    uploaded_by: Optional[str] = None
    user_role: Optional[str] = None
    staged: Optional[Dict[str, Any]] = None
    temp_path: Optional[str] = None

    validation: Any = None
    extraction: Any = None
    image_check: Any = None
    classification: Any = None
    text_guardrail: Any = None
    content_guardrail: Any = None
    classification_guardrail: Any = None

    sha256_hash: Optional[str] = None
    text_hash: Optional[str] = None
    visual_hashes: List[str] = field(default_factory=list)

    exact_duplicate: Any = None
    text_duplicate: Any = None
    visual_duplicate: Any = None

    review_reasons: List[str] = field(default_factory=list)
    final_status: Optional[str] = None
    pending_id: Optional[str] = None
    allow_unauthenticated: bool = False

    file_futures: List[Future] = field(default_factory=list)
    cleanup_requested: bool = False
    cleanup_done: bool = False
    cleanup_lock: Any = field(
        default_factory=Lock,
        repr=False,
    )

    timings: Dict[str, float] = field(default_factory=dict)


class _PipelineRejected(Exception):
    """
    Internal control-flow exception used for deterministic rejections.
    """

    def __init__(
        self,
        reason: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.extra = extra or {}


class DocumentIngestionPipeline:
    """
    Request-scoped orchestration for document staging and validation.

    The public application still calls ``stage_uploaded_file(...)``. That
    compatibility function creates one pipeline instance per upload and calls
    ``run``.

    The class owns request state through ``IngestionContext`` while CPU/I/O
    independent checks are submitted to a bounded process-wide executor.

    Important boundaries:
    - this class stages and validates only;
    - it does not permanently archive the original;
    - it does not mutate Finance/Food/Tasks/Maintenance records;
    - it does not approve or execute a proposal.
    """

    def __init__(
        self,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self._executor = executor or _SHARED_EXECUTOR
        self._extraction_timeout = _configured_seconds(
            "DOCUMENT_EXTRACTION_TIMEOUT_SECONDS",
            DEFAULT_EXTRACTION_TIMEOUT_SECONDS,
        )
        self._analysis_timeout = _configured_seconds(
            "DOCUMENT_ANALYSIS_TIMEOUT_SECONDS",
            DEFAULT_ANALYSIS_TIMEOUT_SECONDS,
        )
        self._duplicate_timeout = _configured_seconds(
            "DOCUMENT_DUPLICATE_TIMEOUT_SECONDS",
            DEFAULT_DUPLICATE_TIMEOUT_SECONDS,
        )
        self._visual_timeout = _configured_seconds(
            "DOCUMENT_VISUAL_TIMEOUT_SECONDS",
            DEFAULT_VISUAL_TIMEOUT_SECONDS,
        )
        self._settle_timeout = _configured_seconds(
            "DOCUMENT_SETTLE_TIMEOUT_SECONDS",
            DEFAULT_SETTLE_TIMEOUT_SECONDS,
        )
        self._min_duplicate_text_chars = (
            _configured_min_duplicate_text_chars()
        )

    def run(
        self,
        uploaded_file: FileStorage,
        uploaded_by: Optional[str] = None,
        user_role: Optional[str] = None,
        allow_unauthenticated: bool = False,
    ) -> Dict[str, Any]:
        ctx = IngestionContext(
            uploaded_by=uploaded_by,
            user_role=user_role,
            allow_unauthenticated=allow_unauthenticated,
        )
        total_started = perf_counter()

        try:
            self._validate_access_context(ctx)
            self._stage(ctx, uploaded_file)
            self._validate(ctx)
            self._calculate_and_check_exact_hash(ctx)
            self._extract_and_prepare_visual_hash(ctx)
            self._run_parallel_analysis(ctx)
            self._run_parallel_duplicate_checks(ctx)
            self._aggregate_review(ctx)
            result = self._build_result(ctx)
            self._persist(ctx)

            result["pending_id"] = ctx.pending_id
            ctx.timings["total_ms"] = self._elapsed_ms(total_started)
            result["timings"] = dict(ctx.timings)

            return result

        except _PipelineRejected as exc:
            ctx.timings["total_ms"] = self._elapsed_ms(total_started)
            return self._reject_result(
                ctx=ctx,
                reason=exc.reason,
                extra=exc.extra,
            )

        except Exception:
            logger.exception(
                "Unexpected document-ingestion failure for upload %s",
                (
                    ctx.staged.get("upload_id")
                    if ctx.staged
                    else None
                ),
            )
            ctx.timings["total_ms"] = self._elapsed_ms(total_started)
            return self._reject_result(
                ctx=ctx,
                reason="Unable to process the uploaded document.",
            )

    def _validate_access_context(
        self,
        ctx: IngestionContext,
    ) -> None:
        """Require trusted identity/role; anonymous intake is test-only."""

        has_user = bool(str(ctx.uploaded_by or "").strip())
        has_role = bool(str(ctx.user_role or "").strip())

        if has_user and has_role:
            return

        if (
            ctx.allow_unauthenticated
            and _test_mode_enabled()
        ):
            return

        raise _PipelineRejected(
            "Document upload requires authenticated user and role context."
        )

    def _enforce_document_domain_access(
        self,
        ctx: IngestionContext,
    ) -> None:
        """
        Stop an authenticated document before persistence/interpretation when
        its classified domain is outside the current role's authorized scope.

        Classification is not authorization. This code-owned gate only decides
        whether the document may continue through intake; action-level RBAC is
        checked again later before execution.
        """

        domain = str(
            getattr(ctx.classification, "domain", "") or ""
        ).strip()

        if can_upload_document(
            str(ctx.user_role or ""),
            domain,
        ):
            return

        if domain in {"NeedsReview", "Unknown", ""}:
            reason = (
                "The document domain could not be established safely, "
                "so it cannot be accepted for this user."
            )
        else:
            reason = (
                "You do not have permission to upload documents "
                "in the {0} domain.".format(domain)
            )

        raise _PipelineRejected(
            reason,
            extra={
                "classification": self._classification_payload(ctx),
            },
        )

    # ------------------------------------------------------------------
    # Sequential cheap gates
    # ------------------------------------------------------------------

    def _stage(
        self,
        ctx: IngestionContext,
        uploaded_file: FileStorage,
    ) -> None:
        started = perf_counter()

        try:
            ctx.staged = save_temp_upload(uploaded_file)
            ctx.temp_path = ctx.staged["temp_path"]
        except Exception:
            logger.exception("Unable to stage uploaded document")
            raise _PipelineRejected(
                "Unable to save uploaded file."
            )
        finally:
            ctx.timings["stage_ms"] = self._elapsed_ms(started)

    def _validate(
        self,
        ctx: IngestionContext,
    ) -> None:
        started = perf_counter()

        try:
            ctx.validation = validate_file(
                self._require_temp_path(ctx)
            )

            if not ctx.validation.valid:
                raise _PipelineRejected(
                    ctx.validation.reason
                    or "The uploaded file failed validation."
                )
        finally:
            ctx.timings["validation_ms"] = self._elapsed_ms(started)

    def _calculate_and_check_exact_hash(
        self,
        ctx: IngestionContext,
    ) -> None:
        """
        Calculate the exact-file fingerprint.

        The database duplicate lookup is intentionally deferred until after
        classification and the document-domain authorization gate. This avoids
        leaking duplicate metadata for a document domain the current user is
        not authorized to upload.

        The existing timing key is preserved for compatibility even though the
        DB lookup now runs later in ``_run_parallel_duplicate_checks``.
        """

        started = perf_counter()

        try:
            ctx.sha256_hash = calculate_sha256(
                self._require_temp_path(ctx)
            )
        finally:
            ctx.timings[
                "sha256_exact_duplicate_ms"
            ] = self._elapsed_ms(started)

    # ------------------------------------------------------------------
    # Expensive reading + independent visual hashing
    # ------------------------------------------------------------------

    def _extract_and_prepare_visual_hash(
        self,
        ctx: IngestionContext,
    ) -> None:
        started = perf_counter()
        visual_future: Optional[Future] = None
        extraction_future: Optional[Future] = None

        try:
            if self._is_image(ctx):
                visual_future = self._executor.submit(
                    self._safe_calculate_visual_hashes,
                    self._require_temp_path(ctx),
                    self._upload_id(ctx),
                )
                ctx.file_futures.append(visual_future)

            extraction_future = self._executor.submit(
                extract_text,
                self._require_temp_path(ctx),
            )
            ctx.file_futures.append(extraction_future)

            ctx.extraction = self._future_result(
                extraction_future,
                self._extraction_timeout,
                "Document text extraction",
            )

            if not ctx.extraction.success:
                raise _PipelineRejected(
                    ctx.extraction.reason
                    or "No readable document content could be extracted."
                )

            if self._is_image(ctx):
                ctx.image_check = check_text_is_document(
                    ctx.extraction.text
                )
                if not ctx.image_check.is_document:
                    raise _PipelineRejected(
                        ctx.image_check.reason
                        or "The uploaded image does not appear to be a document.",
                        extra={
                            "document_check": {
                                "is_document": ctx.image_check.is_document,
                                "confidence": ctx.image_check.confidence,
                                "reason": ctx.image_check.reason,
                            },
                        },
                    )

            if visual_future is not None:
                ctx.visual_hashes = self._future_result(
                    visual_future,
                    self._visual_timeout,
                    "Document visual hashing",
                )

        finally:
            self._settle_future(
                extraction_future,
                timeout_seconds=self._settle_timeout,
            )
            self._settle_future(
                visual_future,
                timeout_seconds=self._settle_timeout,
            )
            ctx.timings["extraction_visual_ms"] = self._elapsed_ms(started)

    # ------------------------------------------------------------------
    # Text-dependent independent checks
    # ------------------------------------------------------------------

    def _run_parallel_analysis(
        self,
        ctx: IngestionContext,
    ) -> None:
        started = perf_counter()
        text = ctx.extraction.text

        normalized_text = normalize_document_text(text)
        useful_chars = len(normalized_text.replace(" ", ""))
        if useful_chars >= self._min_duplicate_text_chars:
            ctx.text_hash = calculate_text_hash(text)
        else:
            ctx.text_hash = None

        text_guardrail_future = self._executor.submit(
            check_extracted_text,
            text,
        )
        content_guardrail_future = self._executor.submit(
            check_untrusted_document_text,
            text,
        )
        classification_future = self._executor.submit(
            classify_document,
            text,
        )
        futures = [
            text_guardrail_future,
            content_guardrail_future,
            classification_future,
        ]

        try:
            ctx.text_guardrail = self._future_result(
                text_guardrail_future,
                self._analysis_timeout,
                "Extracted-text guardrail",
            )
            ctx.content_guardrail = self._future_result(
                content_guardrail_future,
                self._analysis_timeout,
                "Document-content guardrail",
            )
            ctx.classification = self._future_result(
                classification_future,
                self._analysis_timeout,
                "Document classification",
            )

            if (
                not ctx.text_guardrail.allowed
                and ctx.text_guardrail.status == "rejected"
            ):
                raise _PipelineRejected(
                    ctx.text_guardrail.reason
                    or "Extracted document text was rejected."
                )

            ctx.classification_guardrail = check_classification(
                domain=ctx.classification.domain,
                confidence=ctx.classification.confidence,
            )
            if (
                not ctx.classification_guardrail.allowed
                and ctx.classification_guardrail.status == "rejected"
            ):
                raise _PipelineRejected(
                    ctx.classification_guardrail.reason
                    or "Document classification was rejected.",
                    extra={
                        "classification": self._classification_payload(ctx),
                    },
                )

            self._enforce_document_domain_access(ctx)

        finally:
            for future in futures:
                if not future.done():
                    future.cancel()
            ctx.timings["parallel_analysis_ms"] = self._elapsed_ms(started)

    def _run_parallel_duplicate_checks(
        self,
        ctx: IngestionContext,
    ) -> None:
        """Run scoped duplicate checks after classification/authorization."""

        started = perf_counter()
        exact_future = self._executor.submit(
            self._find_exact_duplicate,
            ctx.sha256_hash,
            ctx.uploaded_by,
        )

        text_future: Optional[Future] = None
        if ctx.text_hash:
            text_future = self._executor.submit(
                self._find_text_duplicate,
                ctx.text_hash,
                ctx.uploaded_by,
            )

        visual_future: Optional[Future] = None
        if ctx.visual_hashes:
            visual_future = self._executor.submit(
                self._find_visual_duplicate,
                list(ctx.visual_hashes),
                ctx.uploaded_by,
            )

        futures = [
            future
            for future in (exact_future, text_future, visual_future)
            if future is not None
        ]

        try:
            ctx.exact_duplicate = self._future_result(
                exact_future,
                self._duplicate_timeout,
                "Exact duplicate lookup",
            )
            ctx.text_duplicate = (
                self._future_result(
                    text_future,
                    self._duplicate_timeout,
                    "Text duplicate lookup",
                )
                if text_future is not None
                else None
            )
            ctx.visual_duplicate = (
                self._future_result(
                    visual_future,
                    self._duplicate_timeout,
                    "Visual duplicate lookup",
                )
                if visual_future is not None
                else None
            )

            if ctx.exact_duplicate is not None:
                raise _PipelineRejected(
                    "Exact duplicate document detected."
                )

        finally:
            for future in futures:
                if not future.done():
                    future.cancel()
            ctx.timings["duplicate_checks_ms"] = self._elapsed_ms(started)

    # ------------------------------------------------------------------
    # Decision aggregation and persistence
    # ------------------------------------------------------------------

    def _aggregate_review(
        self,
        ctx: IngestionContext,
    ) -> None:
        review_reasons: List[str] = []

        text_needs_review = (
            ctx.text_guardrail.status == "needs_review"
        )
        security_needs_review = not ctx.content_guardrail.safe
        classification_needs_review = (
            ctx.classification_guardrail.status == "needs_review"
        )
        text_duplicate_needs_review = (
            ctx.text_duplicate is not None
        )
        visual_needs_review = ctx.visual_duplicate is not None

        if text_needs_review and ctx.text_guardrail.reason:
            self._append_unique(
                review_reasons,
                ctx.text_guardrail.reason,
            )

        if security_needs_review and ctx.content_guardrail.reason:
            self._append_unique(
                review_reasons,
                ctx.content_guardrail.reason,
            )

        if (
            classification_needs_review
            and ctx.classification_guardrail.reason
        ):
            self._append_unique(
                review_reasons,
                ctx.classification_guardrail.reason,
            )

        if text_duplicate_needs_review:
            self._append_unique(
                review_reasons,
                "A document with identical normalized text exists. "
                "This may be a legitimate repeat; review before confirming.",
            )

        if visual_needs_review:
            self._append_unique(
                review_reasons,
                "A visually similar document already exists. "
                "Review before confirming.",
            )

        ctx.review_reasons = review_reasons
        ctx.final_status = (
            "needs_review"
            if review_reasons
            else "staged"
        )

    def _persist(
        self,
        ctx: IngestionContext,
    ) -> None:
        started = perf_counter()
        session = SessionLocal()

        try:
            pending = PendingDocumentUpload(
                upload_id=ctx.staged["upload_id"],
                uploaded_by=ctx.uploaded_by,
                original_filename=ctx.staged["original_filename"],
                safe_filename=ctx.staged["safe_filename"],
                temp_path=self._require_temp_path(ctx),
                mime_type=ctx.validation.mime_type,
                extension=ctx.validation.extension,
                file_size=ctx.validation.file_size,
                sha256=ctx.sha256_hash,
                normalized_text_hash=ctx.text_hash,
                visual_hashes_json=json.dumps(ctx.visual_hashes),
                extracted_text=ctx.extraction.text,
                extraction_method=ctx.extraction.method,
                page_count=ctx.extraction.page_count,
                domain=ctx.classification.domain,
                classified_document_type=(
                    ctx.classification.document_type
                ),
                classification_confidence=(
                    ctx.classification.confidence
                ),
                classification_reason=(
                    ctx.classification.reason
                ),
                prompt_injection_detected=(
                    not ctx.content_guardrail.safe
                ),
                status=ctx.final_status,
                review_reasons_json=json.dumps(
                    ctx.review_reasons
                ),
            )

            session.add(pending)
            session.commit()
            session.refresh(pending)
            ctx.pending_id = pending.pending_id

        except Exception:
            session.rollback()
            logger.exception(
                "Unable to persist PendingDocumentUpload for upload %s",
                self._upload_id(ctx),
            )
            raise _PipelineRejected(
                "Unable to save pending document metadata."
            )

        finally:
            session.close()
            ctx.timings["persist_ms"] = self._elapsed_ms(started)

    def _build_result(
        self,
        ctx: IngestionContext,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": True,
            "status": ctx.final_status,
            "upload_id": ctx.staged["upload_id"],
            "original_filename": ctx.staged["original_filename"],
            "safe_filename": ctx.staged["safe_filename"],
            "temp_path": self._require_temp_path(ctx),
            "validation": {
                "extension": ctx.validation.extension,
                "mime_type": ctx.validation.mime_type,
                "file_size": ctx.validation.file_size,
            },
            "extraction": {
                "method": ctx.extraction.method,
                "page_count": ctx.extraction.page_count,
                "text": ctx.extraction.text,
            },
            "classification": self._classification_payload(ctx),
            "security": {
                "prompt_injection_detected": (
                    not ctx.content_guardrail.safe
                ),
                "matched_patterns": (
                    ctx.content_guardrail.matched_patterns
                    or []
                ),
            },
            "duplicate_fingerprints": {
                "sha256": ctx.sha256_hash,
                "normalized_text_hash": ctx.text_hash,
                "visual_hashes": ctx.visual_hashes,
            },
            "duplicate_check": {
                "exact_duplicate": bool(ctx.exact_duplicate),
                "text_possible_duplicate": bool(ctx.text_duplicate),
                "visual_near_duplicate": bool(ctx.visual_duplicate),
            },
        }

        if ctx.image_check is not None:
            result["document_check"] = {
                "is_document": ctx.image_check.is_document,
                "confidence": ctx.image_check.confidence,
                "reason": ctx.image_check.reason,
            }

        if ctx.review_reasons:
            result["review_reasons"] = list(
                ctx.review_reasons
            )

        return result

    # ------------------------------------------------------------------
    # Thread-safe DB helpers: one SQLAlchemy Session per worker
    # ------------------------------------------------------------------

    @staticmethod
    def _find_exact_duplicate(
        sha256_hash: str,
        uploaded_by: Optional[str],
    ) -> Any:
        session = SessionLocal()

        try:
            return find_exact_duplicate(
                session,
                sha256_hash,
                uploaded_by=uploaded_by,
            )
        finally:
            session.close()

    @staticmethod
    def _find_text_duplicate(
        text_hash: str,
        uploaded_by: Optional[str],
    ) -> Any:
        session = SessionLocal()

        try:
            return find_text_duplicate(
                session,
                text_hash,
                uploaded_by=uploaded_by,
            )
        finally:
            session.close()

    @staticmethod
    def _find_visual_duplicate(
        visual_hashes: List[str],
        uploaded_by: Optional[str],
    ) -> Any:
        session = SessionLocal()

        try:
            return find_visual_near_duplicate(
                session,
                visual_hashes,
                uploaded_by=uploaded_by,
            )
        finally:
            session.close()

    @staticmethod
    def _safe_calculate_visual_hashes(
        temp_path: str,
        upload_id: Optional[str],
    ) -> List[str]:
        try:
            return calculate_visual_hashes(temp_path)
        except Exception:
            logger.exception(
                "Visual hash generation failed for staged document %s",
                upload_id,
            )
            return []

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def _reject_result(
        self,
        ctx: IngestionContext,
        reason: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._request_temp_cleanup(ctx)

        result: Dict[str, Any] = {
            "success": False,
            "status": "rejected",
            "reason": reason,
            "timings": dict(ctx.timings),
        }

        if ctx.staged:
            original_filename = ctx.staged.get(
                "original_filename"
            )
            if original_filename:
                result["original_filename"] = original_filename

        if extra:
            result.update(extra)

        return result

    @staticmethod
    def _safe_delete_temp_file(
        temp_path: Optional[str],
    ) -> None:
        if not temp_path:
            return

        try:
            delete_temp_file(temp_path)
        except Exception:
            logger.exception(
                "Failed to delete staged upload at %s",
                temp_path,
            )

    @staticmethod
    def _future_result(
        future: Future,
        timeout_seconds: float,
        label: str,
    ) -> Any:
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise _PipelineRejected(
                "{0} timed out.".format(label)
            ) from exc

    @staticmethod
    def _settle_future(
        future: Optional[Future],
        timeout_seconds: float,
    ) -> bool:
        if future is None:
            return True
        if future.done():
            try:
                future.result()
            except Exception:
                pass
            return True
        if future.cancel():
            return True
        try:
            future.result(timeout=timeout_seconds)
            return True
        except FutureTimeoutError:
            return False
        except Exception:
            return True

    def _request_temp_cleanup(
        self,
        ctx: IngestionContext,
    ) -> None:
        with ctx.cleanup_lock:
            if ctx.cleanup_done:
                return
            ctx.cleanup_requested = True
            outstanding = [
                future
                for future in ctx.file_futures
                if not future.done()
            ]
            if outstanding:
                for future in outstanding:
                    future.add_done_callback(
                        lambda _future, context=ctx: (
                            self._complete_deferred_cleanup(context)
                        )
                    )
                return
            ctx.cleanup_done = True
            temp_path = ctx.temp_path
        self._safe_delete_temp_file(temp_path)

    def _complete_deferred_cleanup(
        self,
        ctx: IngestionContext,
    ) -> None:
        with ctx.cleanup_lock:
            if ctx.cleanup_done or not ctx.cleanup_requested:
                return
            if any(
                not future.done()
                for future in ctx.file_futures
            ):
                return
            ctx.cleanup_done = True
            temp_path = ctx.temp_path
        self._safe_delete_temp_file(temp_path)

    @staticmethod
    def _append_unique(
        values: List[str],
        value: str,
    ) -> None:
        if value and value not in values:
            values.append(value)

    @staticmethod
    def _classification_payload(
        ctx: IngestionContext,
    ) -> Dict[str, Any]:
        return {
            "domain": ctx.classification.domain,
            "document_type": ctx.classification.document_type,
            "confidence": ctx.classification.confidence,
            "reason": ctx.classification.reason,
        }

    @staticmethod
    def _elapsed_ms(
        started: float,
    ) -> float:
        return round(
            (perf_counter() - started) * 1000.0,
            2,
        )

    @staticmethod
    def _require_temp_path(
        ctx: IngestionContext,
    ) -> str:
        if not ctx.temp_path:
            raise RuntimeError(
                "Ingestion temporary path is unavailable."
            )
        return ctx.temp_path

    @staticmethod
    def _upload_id(
        ctx: IngestionContext,
    ) -> Optional[str]:
        if not ctx.staged:
            return None
        return ctx.staged.get("upload_id")

    @staticmethod
    def _is_image(
        ctx: IngestionContext,
    ) -> bool:
        return (
            ctx.validation is not None
            and ctx.validation.extension in IMAGE_EXTENSIONS
        )


def stage_uploaded_file(
    uploaded_file: FileStorage,
    uploaded_by: Optional[str] = None,
    user_role: Optional[str] = None,
    allow_unauthenticated: bool = False,
) -> Dict[str, Any]:
    """
    Backwards-compatible public ingestion entry point.

    Existing graph/service callers do not need to know that ingestion is now a
    class-based pipeline internally.
    """

    pipeline = DocumentIngestionPipeline()
    return pipeline.run(
        uploaded_file=uploaded_file,
        uploaded_by=uploaded_by,
        user_role=user_role,
        allow_unauthenticated=allow_unauthenticated,
    )

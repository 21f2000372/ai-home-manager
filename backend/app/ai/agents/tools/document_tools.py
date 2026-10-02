"""Read-only tools for retrieving approved household documents.

Document ingestion, verification, archival, and derived-action execution are
handled by the document workflow. These tools never create, update, or delete
document records and never accept caller identity from model arguments.

Compatibility target: Python 3.9+.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.tools import tool

from app.ai.agents.request_context import (
    AgentRequestContextError,
    get_agent_request_identity,
)
from app.rag.document_retrieval import (
    DocumentRetrievalError,
    get_document as retrieve_document,
    get_original_document as retrieve_original_document,
    search_documents as retrieve_document_matches,
)


def _retrieval_identity():
    """Return the authenticated request identity.

    Identity is taken only from request context. The LLM never supplies a
    user id or role as a tool argument.
    """

    try:
        return get_agent_request_identity()
    except AgentRequestContextError:
        raise DocumentRetrievalError(
            "Document retrieval is unavailable."
        ) from None


def _clean_display(value: Any, fallback: str) -> str:
    cleaned = " ".join(str(value or "").split())
    return cleaned or fallback


def _format_search_results(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No approved documents matched that request."

    lines = [
        "Found {0} approved document{1}:".format(
            len(rows),
            "" if len(rows) == 1 else "s",
        )
    ]

    for index, row in enumerate(rows, start=1):
        filename = _clean_display(
            row.get("filename"),
            "document",
        )
        document_type = _clean_display(
            row.get("classified_document_type")
            or row.get("document_type"),
            "Document",
        )
        domain = _clean_display(
            row.get("domain"),
            "Unclassified",
        )
        reference = _clean_display(
            row.get("reference"),
            "unavailable",
        )
        evidence = _clean_display(
            row.get("evidence"),
            "No extracted-text preview is available.",
        )

        page_number = row.get("page_number")
        page_note = (
            " Page {0}.".format(page_number)
            if isinstance(page_number, int) and page_number > 0
            else ""
        )

        lines.extend(
            [
                "{0}. {1} — {2} ({3}).".format(
                    index,
                    filename,
                    document_type,
                    domain,
                ),
                "   Internal reference: {0}.{1}".format(
                    reference,
                    page_note,
                ),
                "   Evidence: {0}".format(evidence),
            ]
        )

    return "\n".join(lines)


@tool
def search_documents(
    query: str = "",
    limit: int = 5,
) -> str:
    """Search approved documents visible to the current household role.

    Args:
        query: Natural-language text, filename, document type, domain, vendor,
            amount, product, or other fact to find. Use an empty string to list
            recent approved documents.
        limit: Maximum number of matches to return, from 1 through 10.

    Documents are household-wide. Uploader identity is provenance only.
    Staged, rejected, prompt-injection-flagged, and role-inaccessible documents
    are not returned.
    """

    try:
        identity = _retrieval_identity()

        rows = retrieve_document_matches(
            role=identity.role,
            query=query,
            limit=limit,
        )

        return _format_search_results(rows)

    except DocumentRetrievalError as exc:
        return str(exc)
    except Exception:
        return "Document search is temporarily unavailable."


@tool
def get_document(
    document_reference: str,
) -> str:
    """Read safe metadata and extracted text for one approved document.

    Args:
        document_reference: Exact internal reference returned by
            search_documents, or another supported exact reference such as an
            unambiguous filename.

    This does not expose the private storage key or download the original.
    """

    try:
        identity = _retrieval_identity()

        row = retrieve_document(
            role=identity.role,
            document_reference=document_reference,
        )

    except DocumentRetrievalError as exc:
        return str(exc)
    except Exception:
        return "Document details are temporarily unavailable."

    filename = _clean_display(
        row.get("filename"),
        "document",
    )

    document_type = _clean_display(
        row.get("classified_document_type")
        or row.get("document_type"),
        "Document",
    )

    domain = _clean_display(
        row.get("domain"),
        "Unclassified",
    )

    evidence = _clean_display(
        row.get("evidence"),
        "No extracted text is available.",
    )

    return "\n".join(
        [
            "Document: {0}".format(filename),
            "Type: {0}".format(document_type),
            "Domain: {0}".format(domain),
            "Pages: {0}".format(
                row.get("page_count") or "unknown"
            ),
            "Extracted content: {0}".format(evidence),
        ]
    )


@tool
def get_original_document(
    document_reference: str,
) -> str:
    """Return a signed link for one approved original document.

    Args:
        document_reference: Exact internal reference returned by
            search_documents, or another supported exact reference.

    The original is returned only after household role/document authorization.
    Guest download is denied by the authorization/retrieval policy.
    """

    try:
        identity = _retrieval_identity()

        row = retrieve_original_document(
            role=identity.role,
            document_reference=document_reference,
        )

    except DocumentRetrievalError as exc:
        return str(exc)
    except Exception:
        return "The original document is temporarily unavailable."

    return "\n".join(
        [
            "Original document: {0}".format(
                _clean_display(
                    row.get("filename"),
                    "document",
                )
            ),
            "Download link: {0}".format(
                _clean_display(
                    row.get("download_url"),
                    "unavailable",
                )
            ),
        ]
    )


# Single registration source for the specialist selector and executor.
# Keep every retrieval tool here.
TOOLS = [
    search_documents,
    get_document,
    get_original_document,
]


TOOLS_BY_NAME = {
    registered_tool.name: registered_tool
    for registered_tool in TOOLS
}

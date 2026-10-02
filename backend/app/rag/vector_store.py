"""Role-aware Chroma vector storage.

SQLite remains the system of record. Chroma stores embedded document and
conversation text for semantic retrieval.

Access model
------------
* Conversation chunks are private to their owner. Embeddings must contain both
  user_id and conversation_id, and queries must supply both values. This
  prevents role-only semantic searches from returning another user's
  conversation.
* Document chunks are household-wide. Visibility is controlled only by
  min_role (Guest < Child < Adult < Admin). The user_id stored on a document
  chunk is provenance (the uploader) and is never used as a read filter.

Compatible with Python 3.9.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import config
from app.models.enums import HouseholdRole


COLLECTION_NAME = "household_knowledge"

# Conversation text is private to its owner on both write and read.
# Document text requires user_id on neither: it is optional provenance.
_USER_ID_REQUIRED_ON_WRITE = {"conversation"}
_USER_ID_REQUIRED_ON_QUERY = {"conversation"}

_ROLE_RANK: Dict[str, int] = {
    HouseholdRole.GUEST.value: 0,
    HouseholdRole.CHILD.value: 1,
    HouseholdRole.ADULT.value: 2,
    HouseholdRole.ADMIN.value: 3,
}


def roles_visible_to(
    role: HouseholdRole,
) -> List[str]:
    """Return min_role values visible to the caller."""

    caller_rank = _ROLE_RANK[role.value]

    return [
        role_name
        for role_name, rank in _ROLE_RANK.items()
        if rank <= caller_rank
    ]


def _required_scope_value(
    value: Any,
    *,
    field: str,
    max_length: int,
) -> str:
    """Validate a required metadata scope value."""

    if value is None:
        raise ValueError(
            "{} is required.".format(field)
        )

    if not isinstance(value, str):
        raise ValueError(
            "{} must be a string.".format(field)
        )

    cleaned = value.strip()

    if not cleaned:
        raise ValueError(
            "{} is required.".format(field)
        )

    if cleaned != value:
        raise ValueError(
            "{} must not contain surrounding whitespace.".format(
                field
            )
        )

    if len(cleaned) > max_length:
        raise ValueError(
            "{} is too long.".format(field)
        )

    if any(
        character.isspace()
        or not character.isprintable()
        for character in cleaned
    ):
        raise ValueError(
            "{} contains invalid characters.".format(field)
        )

    return cleaned


def _optional_scope_value(
    value: Any,
    *,
    field: str,
    max_length: int,
) -> Optional[str]:
    """Validate optional metadata scope values."""

    if value is None:
        return None

    return _required_scope_value(
        value,
        field=field,
        max_length=max_length,
    )


class VectorStore:
    """Thin wrapper around one persistent Chroma collection."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_function: Any = None,
    ) -> None:
        import chromadb

        self._persist_dir = (
            persist_dir
            or config.CHROMA_PERSIST_DIR
        )

        self._client = chromadb.PersistentClient(
            path=self._persist_dir
        )

        self._embedding_function = (
            embedding_function
        )

        self._collection = (
            self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                },
                embedding_function=embedding_function,
            )
        )

    def _prepare_write(
        self,
        ids: Sequence[str],
        texts: Sequence[str],
        *,
        source_domain: str,
        min_role: HouseholdRole = HouseholdRole.ADULT,
        extra_metadata: Optional[
            Sequence[Dict[str, Any]]
        ] = None,
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """Validate a vector write and build code-owned metadata.

        Conversation entries require user_id and conversation_id in every
        metadata item. Document entries require document_id; user_id is
        optional provenance (the uploader) and is omitted when absent.

        Other source domains retain their existing behavior until their
        household ownership model is added.
        """

        if len(ids) != len(texts):
            raise ValueError(
                "ids and texts must have the same length."
            )

        if not texts:
            raise ValueError(
                "At least one text is required."
            )

        if (
            extra_metadata is not None
            and len(extra_metadata) != len(texts)
        ):
            raise ValueError(
                "extra_metadata and texts must have "
                "the same length."
            )

        normalized_source = str(
            source_domain or ""
        ).strip().casefold()

        if not normalized_source:
            raise ValueError(
                "source_domain is required."
            )

        clean_ids: List[str] = []
        clean_texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for index in range(len(texts)):
            item_id = ids[index]
            text = texts[index]

            if not isinstance(item_id, str):
                raise ValueError(
                    "Each id must be a string."
                )

            item_id = item_id.strip()
            if not item_id:
                raise ValueError(
                    "Each id is required."
                )
            if len(item_id) > 256:
                raise ValueError(
                    "Each id must be at most 256 characters."
                )

            if not isinstance(text, str):
                raise ValueError(
                    "Each text must be a string."
                )

            text = text.strip()
            if not text:
                raise ValueError(
                    "Each text is required."
                )

            metadata: Dict[str, Any] = {
                "source_domain": normalized_source,
                "min_role": min_role.value,
            }

            supplied_metadata: Dict[str, Any] = {}

            if extra_metadata is not None:
                candidate = extra_metadata[index]

                if not isinstance(candidate, dict):
                    raise ValueError(
                        "Each extra_metadata item must "
                        "be a dictionary."
                    )

                supplied_metadata = dict(candidate)

            # Access-control fields are controlled by this wrapper.
            # Callers cannot override the normalized domain or role.
            supplied_metadata.pop(
                "source_domain",
                None,
            )
            supplied_metadata.pop(
                "min_role",
                None,
            )

            metadata.update(supplied_metadata)

            if normalized_source == "conversation":
                metadata["user_id"] = (
                    _required_scope_value(
                        metadata.get("user_id"),
                        field="user_id",
                        max_length=36,
                    )
                )
                metadata["conversation_id"] = (
                    _required_scope_value(
                        metadata.get("conversation_id"),
                        field="conversation_id",
                        max_length=36,
                    )
                )

            elif normalized_source == "documents":
                # user_id is provenance only (the uploader). It can be NULL
                # because uploaded_by is ON DELETE SET NULL, and Chroma
                # rejects None metadata values, so drop the key when absent.
                uploader = _optional_scope_value(
                    metadata.get("user_id"),
                    field="user_id",
                    max_length=36,
                )
                if uploader is None:
                    metadata.pop("user_id", None)
                else:
                    metadata["user_id"] = uploader

                metadata["document_id"] = (
                    _required_scope_value(
                        metadata.get("document_id"),
                        field="document_id",
                        max_length=36,
                    )
                )

            clean_ids.append(item_id)
            clean_texts.append(text)
            metadatas.append(metadata)

        return clean_ids, clean_texts, metadatas

    def add_texts(
        self,
        ids: Sequence[str],
        texts: Sequence[str],
        *,
        source_domain: str,
        min_role: HouseholdRole = HouseholdRole.ADULT,
        extra_metadata: Optional[
            Sequence[Dict[str, Any]]
        ] = None,
    ) -> None:
        """Add new embedded text after validating its access metadata."""

        clean_ids, clean_texts, metadatas = self._prepare_write(
            ids,
            texts,
            source_domain=source_domain,
            min_role=min_role,
            extra_metadata=extra_metadata,
        )

        self._collection.add(
            ids=clean_ids,
            documents=clean_texts,
            metadatas=metadatas,
        )

    def upsert_texts(
        self,
        ids: Sequence[str],
        texts: Sequence[str],
        *,
        source_domain: str,
        min_role: HouseholdRole = HouseholdRole.ADULT,
        extra_metadata: Optional[
            Sequence[Dict[str, Any]]
        ] = None,
    ) -> None:
        """Idempotently embed and store text with access metadata."""

        clean_ids, clean_texts, metadatas = self._prepare_write(
            ids,
            texts,
            source_domain=source_domain,
            min_role=min_role,
            extra_metadata=extra_metadata,
        )

        self._collection.upsert(
            ids=clean_ids,
            documents=clean_texts,
            metadatas=metadatas,
        )

    def delete_document_embeddings(
        self,
        *,
        document_id: str,
    ) -> None:
        """Delete all chunks for one permanent document.

        document_id is unique, so no owner filter is needed. Callers are
        responsible for authorizing the deletion.
        """

        scoped_document_id = _required_scope_value(
            document_id,
            field="document_id",
            max_length=36,
        )

        self._collection.delete(
            where={
                "$and": [
                    {"source_domain": "documents"},
                    {"document_id": scoped_document_id},
                ]
            }
        )

    def update_document_min_role(
        self,
        *,
        document_id: str,
        min_role: HouseholdRole,
    ) -> int:
        """Change the visibility of an indexed document without re-embedding.

        Returns the number of chunks updated. Call this whenever a document's
        min_role changes in SQLite so Chroma does not drift.
        """

        scoped_document_id = _required_scope_value(
            document_id,
            field="document_id",
            max_length=36,
        )

        got = self._collection.get(
            where={
                "$and": [
                    {"source_domain": "documents"},
                    {"document_id": scoped_document_id},
                ]
            },
            include=["metadatas"],
        )

        ids = got["ids"]
        if not ids:
            return 0

        self._collection.update(
            ids=ids,
            metadatas=[
                {**metadata, "min_role": min_role.value}
                for metadata in got["metadatas"]
            ],
        )

        return len(ids)

    def query(
        self,
        query_text: str,
        *,
        role: HouseholdRole,
        n_results: int = 5,
        source_domain: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve chunks visible to the caller.

        Conversation retrieval fails closed unless user_id and
        conversation_id are both supplied. Document retrieval is
        household-wide and gated only by min_role; supplying user_id for it
        is rejected so a stale caller cannot assume it is scoped. Chroma
        applies all filters during retrieval, before any text is returned
        to application code.
        """

        if not isinstance(query_text, str):
            raise ValueError(
                "query_text must be a string."
            )

        query_text = query_text.strip()

        if not query_text:
            raise ValueError(
                "query_text is required."
            )

        if (
            not isinstance(n_results, int)
            or isinstance(n_results, bool)
            or n_results < 1
            or n_results > 20
        ):
            raise ValueError(
                "n_results must be an integer from 1 to 20."
            )

        normalized_source = (
            str(source_domain).strip().casefold()
            if source_domain is not None
            else None
        )

        if source_domain is not None and not normalized_source:
            raise ValueError(
                "source_domain must not be empty."
            )

        scoped_user_id = _optional_scope_value(
            user_id,
            field="user_id",
            max_length=36,
        )
        scoped_conversation_id = (
            _optional_scope_value(
                conversation_id,
                field="conversation_id",
                max_length=36,
            )
        )

        if (
            normalized_source in _USER_ID_REQUIRED_ON_QUERY
            and scoped_user_id is None
        ):
            raise ValueError(
                "Conversation retrieval requires "
                "user_id and conversation_id."
            )

        if (
            normalized_source == "conversation"
            and scoped_conversation_id is None
        ):
            raise ValueError(
                "Conversation retrieval requires "
                "user_id and conversation_id."
            )

        if normalized_source == "documents":
            if scoped_user_id is not None:
                raise ValueError(
                    "Document retrieval is household-wide; "
                    "do not supply user_id."
                )
            if scoped_conversation_id is not None:
                raise ValueError(
                    "Document retrieval does not accept conversation_id."
                )

        clauses: List[Dict[str, Any]] = [
            {
                "min_role": {
                    "$in": roles_visible_to(role)
                }
            }
        ]

        if normalized_source is not None:
            clauses.append(
                {
                    "source_domain": normalized_source
                }
            )
        elif scoped_conversation_id is None:
            # A query with no source_domain must never sweep up other
            # people's private conversation chunks.
            clauses.append(
                {
                    "source_domain": {"$ne": "conversation"}
                }
            )

        if scoped_user_id is not None:
            clauses.append(
                {
                    "user_id": scoped_user_id
                }
            )

        if scoped_conversation_id is not None:
            clauses.append(
                {
                    "conversation_id": (
                        scoped_conversation_id
                    )
                }
            )

        if len(clauses) == 1:
            where = clauses[0]
        else:
            where = {
                "$and": clauses
            }

        return self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )

    def count(self) -> int:
        """Return the collection item count."""

        return self._collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection."""

        self._client.delete_collection(
            COLLECTION_NAME
        )

        self._collection = (
            self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                },
                embedding_function=(
                    self._embedding_function
                ),
            )
        )


_default_store: Optional[VectorStore] = None


def get_default_store() -> VectorStore:
    """Return the process-wide lazy vector store."""

    global _default_store

    if _default_store is None:
        _default_store = VectorStore()

    return _default_store
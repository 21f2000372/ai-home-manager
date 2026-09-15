"""ChromaDB vector store scaffold for retrieval-augmented generation (RAG).

This is the retrieval layer that grounds LLM answers in the household's own
documents and past conversation. SQLite remains the system of record; this
store holds embedded text chunks plus metadata used for RBAC-aware retrieval.

Key design point for this project's "role-aware RAG" innovation:
every chunk is tagged with a ``min_role`` (the least-privileged role allowed
to see it). Retrieval MUST filter by the caller's role so a Child never
retrieves finance/document chunks meant for Adults/Admins.

The module imports ``chromadb`` lazily so the rest of the app (and the DB
scripts) work even before ``pip install -r requirements.txt`` has been run.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from app.config import config
from app.models.enums import HouseholdRole

COLLECTION_NAME = "household_knowledge"

# Role hierarchy: higher number = more privilege. A chunk with min_role=ADULT
# is visible to Adult and Admin, but not Child or Guest.
_ROLE_RANK: dict[str, int] = {
    HouseholdRole.GUEST.value: 0,
    HouseholdRole.CHILD.value: 1,
    HouseholdRole.ADULT.value: 2,
    HouseholdRole.ADMIN.value: 3,
}


def roles_visible_to(role: HouseholdRole) -> list[str]:
    """Return the set of ``min_role`` values a given role is allowed to read."""
    caller_rank = _ROLE_RANK[role.value]
    return [r for r, rank in _ROLE_RANK.items() if rank <= caller_rank]


class VectorStore:
    """Thin wrapper around a persistent Chroma collection.

    Embeddings: by default Chroma uses its built-in embedding function. To use
    OpenRouter/OpenAI embeddings later, pass an ``embedding_function`` when
    constructing, or wire one in ``get_default_store``.
    """

    def __init__(self, persist_dir: Optional[str] = None, embedding_function: Any = None) -> None:
        import chromadb  # lazy import

        self._persist_dir = persist_dir or config.CHROMA_PERSIST_DIR
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function,
        )

    # --- Write ---
    def add_texts(
        self,
        ids: Sequence[str],
        texts: Sequence[str],
        *,
        source_domain: str,
        min_role: HouseholdRole = HouseholdRole.ADULT,
        extra_metadata: Optional[Sequence[dict[str, Any]]] = None,
    ) -> None:
        """Embed and store text chunks with role-aware metadata.

        Every chunk records ``source_domain`` (e.g. "documents", "finance",
        "conversation") and ``min_role`` so retrieval can be filtered by the
        caller's permission level.
        """
        metadatas: list[dict[str, Any]] = []
        for i in range(len(texts)):
            md: dict[str, Any] = {
                "source_domain": source_domain,
                "min_role": min_role.value,
            }
            if extra_metadata is not None:
                md.update(extra_metadata[i])
            metadatas.append(md)
        self._collection.add(ids=list(ids), documents=list(texts), metadatas=metadatas)

    # --- Read (RBAC-filtered) ---
    def query(
        self,
        query_text: str,
        *,
        role: HouseholdRole,
        n_results: int = 5,
        source_domain: Optional[str] = None,
    ) -> dict[str, Any]:
        """Retrieve the most relevant chunks the caller's role may see.

        Applies a metadata ``where`` filter so only chunks with a ``min_role``
        at or below the caller's privilege are returned. This is the guardrail
        that keeps RAG answers role-appropriate.
        """
        allowed = roles_visible_to(role)
        where: dict[str, Any] = {"min_role": {"$in": allowed}}
        if source_domain is not None:
            where = {"$and": [where, {"source_domain": source_domain}]}
        return self._collection.query(
            query_texts=[query_text], n_results=n_results, where=where
        )

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection. Development helper."""
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )


_default_store: Optional[VectorStore] = None


def get_default_store() -> VectorStore:
    """Return a lazily-created shared VectorStore instance."""
    global _default_store
    if _default_store is None:
        _default_store = VectorStore()
    return _default_store

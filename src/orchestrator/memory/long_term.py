"""OmniCompanion — Long-Term Memory (Firestore)

Persistent memory storage using Google Cloud Firestore.
Supports exact key lookup, filtered queries, and semantic search
via Vertex AI Embeddings.
"""

from __future__ import annotations

import os
import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Firestore-backed persistent memory with semantic search.

    Collections:
    - sessions/{session_id}/tasks/{task_id}
    - user_preferences/{user_id}
    - knowledge_base/{doc_id}
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        database_id: Optional[str] = None,
    ) -> None:
        """Initialize Firestore client.

        Args:
            project_id: GCP project ID. Defaults to env var.
            database_id: Firestore database ID. Defaults to env var.
        """
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self.database_id = database_id or os.environ.get("FIRESTORE_DATABASE", "(default)")

        try:
            from google.auth.exceptions import DefaultCredentialsError
            self.db = firestore.Client(
                project=self.project_id,
                database=self.database_id,
            )
            logger.info(
                "LongTermMemory initialized",
                extra={"project_id": self.project_id, "database_id": self.database_id},
            )
        except Exception as e:
            logger.warning(
                "Could not initialize Firestore (missing GCP credentials) — "
                f"Long-term memory will operate in mock mode. Error: {e}"
            )
            self.db = None

    # ──────────────────────────────────────
    # Task Storage
    # ──────────────────────────────────────

    async def store_task(
        self,
        session_id: str,
        task_id: str,
        goal: str,
        steps: list[dict],
        status: str,
        outcome: str = "",
        duration_ms: int = 0,
    ) -> None:
        """Store a completed task in Firestore.

        Args:
            session_id: Session identifier.
            task_id: Task identifier.
            goal: Original user goal.
            steps: List of execution steps.
            status: Final status.
            outcome: Summary of what happened.
            duration_ms: Total execution time.
        """
        if not self.db:
            logger.debug("Mock mode: Skipping store_task")
            return
            
        doc_ref = (
            self.db.collection("sessions")
            .document(session_id)
            .collection("tasks")
            .document(task_id)
        )

        doc_ref.set({
            "goal": goal,
            "steps": steps,
            "status": status,
            "outcome": outcome,
            "duration_ms": duration_ms,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        logger.info(f"Task stored: session={session_id}, task={task_id}")

    async def get_task(self, session_id: str, task_id: str) -> Optional[dict]:
        """Retrieve a task by ID.

        Args:
            session_id: Session identifier.
            task_id: Task identifier.

        Returns:
            Task document or None.
        """
        if not self.db:
            return None
            
        doc_ref = (
            self.db.collection("sessions")
            .document(session_id)
            .collection("tasks")
            .document(task_id)
        )

        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def get_recent_tasks(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent tasks for a session.

        Args:
            session_id: Session identifier.
            limit: Max number of tasks.

        Returns:
            List of task documents.
        """
        if not self.db:
            return []
            
        tasks_ref = (
            self.db.collection("sessions")
            .document(session_id)
            .collection("tasks")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        return [doc.to_dict() for doc in tasks_ref.stream()]

    # ──────────────────────────────────────
    # User Preferences
    # ──────────────────────────────────────

    async def store_user_preferences(
        self,
        user_id: str,
        preferences: dict,
    ) -> None:
        """Store or update user preferences.

        Args:
            user_id: User identifier.
            preferences: Preference data to merge.
        """
        if not self.db:
            logger.debug("Mock mode: Skipping store_user_preferences")
            return
            
        doc_ref = self.db.collection("user_preferences").document(user_id)
        doc_ref.set(
            {**preferences, "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

    async def get_user_preferences(self, user_id: str) -> Optional[dict]:
        """Get user preferences.

        Args:
            user_id: User identifier.

        Returns:
            Preferences document or None.
        """
        if not self.db:
            return None
            
        doc_ref = self.db.collection("user_preferences").document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    # ──────────────────────────────────────
    # Knowledge Base
    # ──────────────────────────────────────

    async def store_knowledge(
        self,
        doc_id: str,
        content: str,
        embedding: list[float],
        source: str,
        category: str = "workflow",
    ) -> None:
        """Store a knowledge entry with its embedding.

        Args:
            doc_id: Document identifier.
            content: Knowledge content text.
            embedding: Vector embedding (768-dim).
            source: Source of the knowledge.
            category: Category tag.
        """
        if not self.db:
            logger.debug("Mock mode: Skipping store_knowledge")
            return
            
        doc_ref = self.db.collection("knowledge_base").document(doc_id)
        doc_ref.set({
            "content": content,
            "embedding": embedding,
            "source": source,
            "category": category,
            "created_at": firestore.SERVER_TIMESTAMP,
            "relevance_score": 1.0,
            "access_count": 0,
            "last_accessed": firestore.SERVER_TIMESTAMP,
        })

        logger.info(f"Knowledge stored: doc_id={doc_id}, category={category}")

    async def search_knowledge(
        self,
        query_embedding: list[float],
        category: Optional[str] = None,
        limit: int = 5,
        decay_rate: float = 0.05,
    ) -> list[dict]:
        """Semantic search in knowledge base.

        Uses cosine similarity + recency weighting.
        Score = 0.7 * semantic + 0.3 * recency.

        Args:
            query_embedding: Query vector (768-dim).
            category: Optional category filter.
            limit: Max results.
            decay_rate: Recency decay rate.

        Returns:
            List of scored knowledge entries.
        """
        if not self.db:
            logger.debug("Mock mode: Returning empty search results")
            return []

        query = self.db.collection("knowledge_base")

        if category:
            query = query.where(filter=FieldFilter("category", "==", category))

        results = []
        now = datetime.now(timezone.utc)

        for doc in query.stream():
            data = doc.to_dict()
            doc_embedding = data.get("embedding", [])

            if not doc_embedding:
                continue

            # Cosine similarity
            semantic_score = self._cosine_similarity(query_embedding, doc_embedding)

            # Recency weight
            last_accessed = data.get("last_accessed")
            if last_accessed:
                if hasattr(last_accessed, "timestamp"):
                    days_ago = (now - datetime.fromtimestamp(
                        last_accessed.timestamp(), tz=timezone.utc
                    )).days
                else:
                    days_ago = 0
            else:
                days_ago = 30

            recency_weight = math.exp(-decay_rate * days_ago)

            # Combined score
            final_score = 0.7 * semantic_score + 0.3 * recency_weight

            results.append({
                "doc_id": doc.id,
                "content": data.get("content", ""),
                "category": data.get("category", ""),
                "source": data.get("source", ""),
                "semantic_score": semantic_score,
                "recency_weight": recency_weight,
                "final_score": final_score,
            })

        # Sort by final score and return top results
        results.sort(key=lambda x: x["final_score"], reverse=True)

        # Update access counts for returned results
        for result in results[:limit]:
            doc_ref = self.db.collection("knowledge_base").document(result["doc_id"])
            doc_ref.update({
                "access_count": firestore.Increment(1),
                "last_accessed": firestore.SERVER_TIMESTAMP,
            })

        return results[:limit]

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec_a: First vector.
            vec_b: Second vector.

        Returns:
            Cosine similarity score (0.0 to 1.0).
        """
        if len(vec_a) != len(vec_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

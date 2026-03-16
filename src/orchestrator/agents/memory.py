"""OmniCompanion — Memory Agent

Wrapper agent for short-term and long-term memory operations.
Provides unified read/write/search interface.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

from src.orchestrator.memory.short_term import ShortTermMemory

if TYPE_CHECKING:
    from src.orchestrator.memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class MemoryAgent:
    """Agent 5: Unified memory interface.

    Input: {op: read|write|search, key, data, query}
    Output: {found: bool, data, relevance_score}
    """

    def __init__(
        self,
        short_term: ShortTermMemory,
        long_term: Optional[LongTermMemory] = None,
    ) -> None:
        self.short_term = short_term
        self.long_term = long_term
        self.name = "memory"

    async def execute(self, operation: dict) -> dict:
        """Execute a memory operation.

        Args:
            operation: {
                op: "read" | "write" | "search",
                key: str (for read/write),
                data: Any (for write),
                query: str (for search),
                collection: str (for long-term ops),
            }

        Returns:
            {found: bool, data: Any, relevance_score: float}
        """
        op = operation.get("op", "read")

        if op == "read":
            return await self._read(operation)
        elif op == "write":
            return await self._write(operation)
        elif op == "search":
            return await self._search(operation)
        else:
            return {"found": False, "data": None, "relevance_score": 0.0}

    async def _read(self, operation: dict) -> dict:
        """Read by key — checks short-term first, then long-term."""
        key = operation.get("key", "")

        # Tier 1: Short-term memory
        value = self.short_term.get(key)
        if value is not None:
            return {"found": True, "data": value, "relevance_score": 1.0}

        # Tier 2: Long-term memory (if available)
        if self.long_term:
            collection = operation.get("collection", "knowledge_base")
            try:
                if collection == "knowledge_base":
                    doc = await self.long_term.get_task(
                        self.short_term.session_id, key
                    )
                    if doc:
                        return {"found": True, "data": doc, "relevance_score": 0.8}
            except Exception as e:
                logger.warning(f"Long-term read failed: {e}")

        return {"found": False, "data": None, "relevance_score": 0.0}

    async def _write(self, operation: dict) -> dict:
        """Write data to memory."""
        key = operation.get("key", "")
        data = operation.get("data")

        # Always write to short-term
        self.short_term.set(key, data)

        # Optionally write to long-term
        if self.long_term and operation.get("persist", False):
            try:
                await self.long_term.store_knowledge(
                    doc_id=key,
                    content=str(data),
                    embedding=[],  # Will be generated separately
                    source="agent_write",
                    category=operation.get("category", "workflow"),
                )
            except Exception as e:
                logger.warning(f"Long-term write failed: {e}")

        return {"found": True, "data": data, "relevance_score": 1.0}

    async def _search(self, operation: dict) -> dict:
        """Semantic search in long-term memory."""
        query = operation.get("query", "")

        if not self.long_term:
            return {"found": False, "data": [], "relevance_score": 0.0}

        try:
            # Note: embedding generation should be done before calling this
            query_embedding = operation.get("query_embedding", [])
            if not query_embedding:
                return {"found": False, "data": [], "relevance_score": 0.0}

            results = await self.long_term.search_knowledge(
                query_embedding=query_embedding,
                category=operation.get("category"),
                limit=operation.get("limit", 5),
            )

            if results:
                return {
                    "found": True,
                    "data": results,
                    "relevance_score": results[0]["final_score"],
                }
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")

        return {"found": False, "data": [], "relevance_score": 0.0}

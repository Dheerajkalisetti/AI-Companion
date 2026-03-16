# OmniCompanion — Memory Architecture

## Overview
OmniCompanion uses a **dual-layer memory system**: fast in-memory short-term storage for the current session, and persistent Firestore-backed long-term storage for cross-session learning.

---

## Short-Term Memory

**Implementation:** Python in-memory dictionary
**File:** `src/orchestrator/memory/short_term.py`
**Lifetime:** Single session (pruned on session end)

### Schema
```python
{
    "session_id": "uuid-string",
    "task_history": [
        {
            "task_id": "uuid",
            "goal": "string",
            "status": "pending|in_progress|completed|failed",
            "steps": [
                {
                    "step_id": "uuid",
                    "agent": "planner|vision|executor|browser|memory|verifier|safety",
                    "action": "string",
                    "result": {},
                    "timestamp": "ISO-8601"
                }
            ]
        }
    ],
    "screen_history": [
        {
            "timestamp": "ISO-8601",
            "screenshot_ref": "bytes|gcs_path",
            "ui_elements": [],
            "context": "string"
        }
    ],
    "active_plan": {
        "tasks": [],
        "current_step_index": 0,
        "retry_count": 0
    },
    "token_budget": {
        "used": 0,
        "limit": 1000000,
        "last_reset": "ISO-8601"
    }
}
```

### Pruning Strategy
- Screen history: Keep last 10 screenshots, prune oldest
- Task history: Keep all (bounded by session length)
- Token budget: Reset on session start

---

## Long-Term Memory (Firestore)

**Implementation:** Google Cloud Firestore (Native mode)
**File:** `src/orchestrator/memory/long_term.py`
**Lifetime:** Persistent across sessions

### Collections

#### `sessions/{session_id}/tasks/{task_id}`
```
Fields:
  goal: string              # Original user goal
  steps: array              # Ordered execution steps
    - step_id: string
    - description: string
    - agent: string
    - action: string
    - result: map
    - timestamp: timestamp
  status: string            # pending | in_progress | completed | failed
  created_at: timestamp
  updated_at: timestamp
  outcome: string           # Summary of what happened
  duration_ms: number       # Total time to complete
```

#### `user_preferences/{user_id}`
```
Fields:
  apps_used: array[string]          # List of applications the user commonly uses
  common_goals: array[string]       # Frequently requested goals
  calibration_data: map             # Screen resolution, OS, input preferences
    - screen_width: number
    - screen_height: number
    - os: string
    - preferred_browser: string
  created_at: timestamp
  updated_at: timestamp
```

#### `knowledge_base/{doc_id}`
```
Fields:
  content: string                   # The knowledge content
  embedding: array[number]          # Vertex AI text embedding vector (768 dims)
  source: string                    # Where this knowledge came from
  category: string                  # ui_pattern | app_behavior | error_fix | workflow
  created_at: timestamp
  relevance_score: number           # Decaying relevance (refreshed on access)
  access_count: number              # How many times this knowledge was retrieved
  last_accessed: timestamp
```

---

## Retrieval Strategy

### Three-Tier Lookup

```
Query arrives
    │
    ├─ Tier 1: Exact Key Match
    │   ├─ Check short-term memory dict (O(1))
    │   ├─ Check Firestore by document ID
    │   └─ If found → Return immediately
    │
    ├─ Tier 2: Filtered Query
    │   ├─ Firestore query with field filters
    │   ├─ e.g., tasks where goal matches keywords
    │   └─ If found → Return top 5 results
    │
    └─ Tier 3: Semantic Search
        ├─ Generate embedding for query via Vertex AI
        ├─ Query knowledge_base collection
        ├─ Compute cosine similarity with stored embeddings
        ├─ Apply recency weighting
        └─ Return top 5 results by combined score
```

### Scoring Formula
```
final_score = 0.7 * semantic_similarity + 0.3 * recency_weight

Where:
  semantic_similarity = cosine_similarity(query_embedding, doc_embedding)
  recency_weight = exp(-decay_rate * days_since_last_access)
  decay_rate = 0.05  (half-life ≈ 14 days)
```

---

## Conflict Resolution

| Scenario | Strategy |
|----------|----------|
| Same key, newer data | Newer entry wins — overwrite |
| Same key, behavioral data | Both preserved — merge arrays, average scores |
| Embedding collision | Both stored — semantic search returns both |
| Stale data detected | Update `relevance_score`, don't delete |

---

## Memory Operations

| Operation | Short-Term | Long-Term |
|-----------|:---:|:---:|
| Read by key | ✅ O(1) | ✅ Firestore get |
| Write | ✅ dict update | ✅ Firestore set |
| Search | ❌ | ✅ Semantic search |
| Delete | ✅ dict pop | ❌ (soft delete via score) |
| List recent | ✅ slice | ✅ Firestore query |

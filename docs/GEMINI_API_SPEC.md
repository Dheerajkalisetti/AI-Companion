# OmniCompanion — Gemini API Specification

## Model Configuration

| Parameter | Value |
|-----------|-------|
| Model | `gemini-3-flash` |
| Access | Vertex AI Python SDK (`google-cloud-aiplatform`) |
| Region | `us-central1` |
| Max Output Tokens | 8,192 |
| Temperature | 0.1 (low — deterministic reasoning) |
| Top-P | 0.95 |
| Top-K | 40 |

---

## Authentication

```python
import vertexai
from vertexai.generative_models import GenerativeModel

# Initialize Vertex AI
vertexai.init(
    project=os.environ["GCP_PROJECT_ID"],
    location=os.environ["VERTEX_AI_LOCATION"]
)

# Create model
model = GenerativeModel("gemini-3-flash")
```

---

## Usage Patterns

### Pattern 1: Text Generation (Planner, Safety)
```python
response = model.generate_content(
    contents=[prompt_text],
    generation_config={
        "max_output_tokens": 4096,
        "temperature": 0.1,
        "response_mime_type": "application/json"
    },
    safety_settings=SAFETY_CONFIG
)
```

### Pattern 2: Multimodal Input (Vision, Verifier)
```python
from vertexai.generative_models import Part, Image

screenshot_part = Part.from_image(
    Image.from_bytes(screenshot_png_bytes)
)

response = model.generate_content(
    contents=[screenshot_part, text_prompt],
    generation_config={
        "max_output_tokens": 4096,
        "temperature": 0.1,
        "response_mime_type": "application/json"  
    },
    safety_settings=SAFETY_CONFIG
)
```

### Pattern 3: Streaming Response
```python
response_stream = model.generate_content(
    contents=[prompt],
    stream=True
)

for chunk in response_stream:
    process_chunk(chunk.text)
```

### Pattern 4: Embeddings (Memory Agent)
```python
from vertexai.language_models import TextEmbeddingModel

embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
embeddings = embedding_model.get_embeddings([text])
vector = embeddings[0].values  # 768-dim float vector
```

---

## Safety Configuration

```python
from vertexai.generative_models import HarmCategory, HarmBlockThreshold

SAFETY_CONFIG = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}
```

**Rationale:** Most categories set to BLOCK_ONLY_HIGH to avoid false positives on legitimate UI content. DANGEROUS_CONTENT set stricter because we execute actions on the user's system.

---

## Token Management

### Context Window
- Gemini 1.5 Pro: **1,000,000 token** context window
- Practical limit with images: ~50 screenshots at ~20K tokens each

### Token Counting
```python
# Count tokens before sending
token_count = model.count_tokens(contents)
if token_count.total_tokens > TOKEN_BUDGET:
    # Prune older context from prompt
    contents = prune_context(contents, TOKEN_BUDGET)
```

### Budget Allocation Per Agent
| Agent | Max Tokens Per Call | Calls Per Task |
|-------|-------------------|----------------|
| Planner | 4,096 output | 1 |
| Vision | 4,096 output | 1-3 |
| Verifier | 2,048 output | 1 per step |
| Safety | 1,024 output | 1 per action |
| Memory (embeddings) | 256 dim input | 1-2 |

---

## Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((
        ResourceExhausted,      # Quota exceeded
        ServiceUnavailable,     # Temporary outage
        DeadlineExceeded,       # Timeout
    ))
)
async def call_gemini(contents, config):
    return model.generate_content(contents, generation_config=config)
```

### Error Handling Matrix

| Error | Action | Max Retries |
|-------|--------|-------------|
| `ResourceExhausted` (429) | Exponential backoff: 2s, 4s, 8s | 3 |
| `ServiceUnavailable` (503) | Exponential backoff: 2s, 4s, 8s | 3 |
| `DeadlineExceeded` (504) | Retry with shorter prompt | 2 |
| `InvalidArgument` (400) | Log error, do not retry | 0 |
| `PermissionDenied` (403) | Log error, alert user | 0 |
| Safety block | Log, inform user, skip action | 0 |

---

## Multimodal Input Formatting

### Screenshot Preparation
```python
from PIL import Image
import io

def prepare_screenshot(raw_bytes: bytes) -> bytes:
    """Prepare screenshot for Gemini multimodal input."""
    img = Image.open(io.BytesIO(raw_bytes))
    
    # Resize if too large (max 3072x3072 for optimal performance)
    max_dim = 3072
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
```

### Structured Output
All agents request JSON output via `response_mime_type: "application/json"` to ensure parseable results.

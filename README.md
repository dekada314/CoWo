# CoWo

Document ingestion, knowledge graph and retrieval workspace with a FastAPI
backend and React frontend.

## Project layout

```text
backend/       Python application, migrations and tests
frontend/      React/Vite application and production image
nginx.conf     shared frontend reverse-proxy configuration
docker-compose.yaml
pyproject.toml
uv.lock
alembic.ini
```

## Quick start

1. Copy env template and fill in secrets:
   ```bash
   cp .env.example .env
   # edit .env and replace all `changeme_*` placeholders
   ```

2. Build and start the API and its infrastructure:

   ```bash
   docker compose up --build
   ```

   The startup sequence creates the PostgreSQL schema and the MinIO bucket
   before the API is started.
   PostgreSQL is exposed on `localhost:5432` by default while containers keep
   using the standard internal port `5432`.

3. Check liveness:

   ```bash
   curl http://localhost:8000/api/v1/health/live
   ```

4. Open the web interface:

   ```text
   http://localhost:3000
   ```

   The frontend is built from `frontend/` and served by Nginx. Requests under
   `/api` are proxied to the FastAPI container through the shared Compose network,
   so access headers and refresh cookies use one browser origin.

   Rebuild frontend assets after source changes:

   ```bash
   cd frontend
   npm ci
   npm run build
   cd ..
   docker compose up -d --build frontend
   ```

## Authentication

Create an account and log in before using ingestion or retrieval:

```bash
curl -X POST 'http://localhost:8000/api/v1/auth/register' \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"StrongPass1"}'

curl -X POST 'http://localhost:8000/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -c cookies.txt \
  -d '{"email":"user@example.com","password":"StrongPass1"}'
```

The login response contains a short-lived access JWT. Send it as
`Authorization: Bearer <token>`. The rotating refresh JWT is available only as
an `HttpOnly` cookie and its active session is stored in Redis. Refresh and logout
use the cookie jar:

```bash
curl -X POST 'http://localhost:8000/api/v1/auth/refresh' \
  -b cookies.txt -c cookies.txt

curl -X POST 'http://localhost:8000/api/v1/auth/logout' \
  -b cookies.txt -c cookies.txt
```

Set a random `AUTH_SECRET_KEY` with at least 32 characters. In HTTPS deployments,
set `AUTH_COOKIE_SECURE=true`; `SameSite=None` is rejected unless secure cookies
are enabled. Logout revokes the refresh session immediately. An already issued
access token remains valid for its short configured lifetime.

## Development checks

```bash
uv sync --dev
uv run ruff check .
uv run pytest
```

## Analyst ingestion

The ingestion workflow extracts a summary, key points, a domain and concepts.
Cards live in PostgreSQL (`knowledge_cards`), originals remain private S3 objects,
and an idempotent semantic projection is written to FalkorDB. The graph contains
`Domain` and `Concept` nodes, concept co-occurrence edges and lightweight job IDs
that point back to PostgreSQL cards. Cards are deliberately not graph nodes.
PostgreSQL remains the source of truth for documents, jobs and cards.

The ingestion agent pipeline is:

1. Analyst extracts the structured knowledge card.
2. Normalizer compares concepts with the registry by exact canonical identity and
   embedding similarity, reuses canonical concepts and records aliases.
3. Linker associates the PostgreSQL card ID with its concepts and writes weighted
   concept-to-domain and concept co-occurrence links.
4. Community agent runs separately on the configured cron, applies FalkorDB label
   propagation to `Concept`/`RELATED_TO`, names the resulting clusters and updates
   active generated communities.

CoWo uses a fully local Ollama setup by default. Install a current Ollama release
on the host machine, then download both Qwen models before starting Compose:

```bash
ollama pull llama3.2:3b
ollama pull qwen3-embedding:0.6b
ollama serve
```

On a 16 GB machine keep the chat model at 9B quantized, use one concurrent model
request and a 16K context window. If Ollama is managed as a service, set
`OLLAMA_CONTEXT_LENGTH=16384` in that service's environment before restarting it.
The application configuration is:

```dotenv
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL_ANALYST=llama3.2:3b
LLM_MODEL_RESPONDER=llama3.2:3b
LLM_MODEL_EMBEDDING=qwen3-embedding:0.6b
LLM_API_KEY=
LLM_REASONING_EFFORT=none
LLM_SEED=0
LLM_MAX_CONCURRENCY=1
LLM_EMBEDDING_DIMENSIONS=1024
FALKORDB_GRAPH_NAME=knowledge_graph_qwen35
FALKORDB_EMBEDDING_DIM=1024
```

The backend uses Ollama's OpenAI-compatible `/v1/chat/completions` and
`/v1/embeddings` endpoints. Thinking is disabled for deterministic structured
JSON. Query embeddings receive Qwen's retrieval instruction while document
embeddings remain unprefixed. `host.docker.internal` lets the containers reach
Ollama running on the host; `localhost` inside a worker would point to the worker
container itself. No document text or prompt is sent to an external model API.

The fast local profile uses `LLM_REASONING_EFFORT=none` in all three agents.
Ollama maps this to disabled thinking for models supporting that mode
([Ollama API documentation](https://docs.ollama.com/api/openai-compatibility)).
Generation budgets are separate: `LLM_EVIDENCE_OUTPUT_TOKENS=512` for intermediate
summaries, `LLM_MAX_OUTPUT_TOKENS=2048` for the final card,
`LLM_RESPONDER_OUTPUT_TOKENS=1024` for answers and
`LLM_COMMUNITY_OUTPUT_TOKENS=384` for community names/descriptions. These are
token ceilings, not targets. Prompts request short results; validation still
rejects incomplete JSON. The 600-second request timeout is a failure limit,
not a thinking budget. Real latency depends on hardware and source length.

Use an up-to-date Ollama on the target PC. Configure its service with
`OLLAMA_NUM_PARALLEL=1` and `OLLAMA_CONTEXT_LENGTH=16384` to bound concurrent
inference and context memory across API and worker processes. These variables
belong to the Ollama service, not CoWo's `.env`.

The Qwen embedding model produces 1024-dimensional vectors. The dedicated graph
name prevents them from being mixed with vectors produced by an older provider.
Existing documents from another embedding space must be processed again before
they appear in the Qwen graph and retrieval results.

Start/recreate services after changing `.env`:

```bash
docker compose up --build -d
```

Submit TXT, Markdown, DOCX or PDF as multipart:

```bash
curl -X POST 'http://localhost:8000/api/v1/ingestion/documents' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F 'file=@notes.txt'
```

Submit up to 10 documents in one request. The batch route applies the same upload
workflow to every file in order:

```bash
curl -X POST 'http://localhost:8000/api/v1/ingestion/documents/batch' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F 'files=@notes.txt' \
  -F 'files=@report.pdf'
```

The response is HTTP 202 with a job `id` and a `Location` header. Then use:

```text
GET  /api/v1/ingestion/jobs/{id}           # queued/running/completed/failed
GET  /api/v1/ingestion/documents            # current user's document library
GET  /api/v1/ingestion/jobs/{id}/card      # structured card, 409 until ready
GET  /api/v1/ingestion/jobs/{id}/original  # streamed download
POST /api/v1/ingestion/jobs/{id}/retry     # retry a failed job, resets attempt budget
DELETE /api/v1/ingestion/jobs/{id}         # remove card, graph links and original
```

## Retrieval and answers

The answer endpoint embeds the question with the same model used for concepts,
selects entry concepts by cosine similarity, expands a bounded one or two-hop
beam through `RELATED_TO`, ranks cards and asks the local responder model to write
an answer only from the selected cards.

```bash
curl -X POST 'http://localhost:8000/api/v1/retrieval/answer' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does chunking affect retrieval?"}'
```

The response contains `answer`, validated `citations` and deterministic
`evidence_paths`. Evidence paths contain graph concept names and scores, not hidden
model reasoning. Card IDs and original URLs are assembled by the backend and
cannot be invented by the model.

Retrieval first searches the shared semantic concept registry, then filters every
candidate card through PostgreSQL ownership. A user cannot receive another
user's card, citation or original document.

## Graph API

The visual graph exposes only domains and concepts. Communities are returned as
grouping metadata and rendered as background regions, not clickable graph nodes.
Selecting a concept loads its owned PostgreSQL cards on demand.
The graph uses small circular nodes, thin edges and a force-based layout.
Drag nodes or the background, zoom around the pointer, search by node name,
and toggle labels. Selected-node details appear in a separate side panel.

```text
GET /api/v1/graph
GET /api/v1/graph/concepts/{concept_id}/cards
```

Both routes require an access JWT and filter the result by the current user.

Retrieval breadth is controlled by `RETRIEVAL_ENTRY_TOP_K`,
`RETRIEVAL_MIN_ENTRY_SIMILARITY`, `RETRIEVAL_MAX_HOPS`, `RETRIEVAL_BEAM_WIDTH`,
`RETRIEVAL_NEIGHBORS_PER_CONCEPT`, `RETRIEVAL_MAX_CARDS` and
`RETRIEVAL_PATH_DECAY`.

Concept merging is controlled by `NORMALIZATION_SIMILARITY_THRESHOLD` and
`NORMALIZATION_CANDIDATES`. Community clustering defaults to midnight and is
configured with `CLUSTERING_CRON`, `CLUSTERING_MAX_ITERATIONS`,
`CLUSTERING_MIN_COMMUNITY_SIZE` and `CLUSTERING_MAX_COMMUNITIES`.

The API is bound to localhost. Ingestion resources, graph cards and retrieval
sources are visible only to the user who uploaded them. Canonical domains and
concepts are shared in FalkorDB, while PostgreSQL ownership is the tenant boundary.

### Delivery and scaling

The document version and job are committed together, then the API immediately
publishes the job ID to the dedicated durable RabbitMQ queue. The API requires a
live broker to accept new work. If publishing fails, the job is marked `failed`
and can be started again from the UI after RabbitMQ becomes available.

Workers use short database transactions, atomic claims, lease tokens and
heartbeats. Only the current lease holder can project and commit a card. Graph
writes use stable identifiers and `MERGE`, so repeated delivery updates the same
projection. The PostgreSQL card and completed job status are committed in one
transaction. A crashed worker leaves its RabbitMQ message unacknowledged, so the
broker can redeliver it. After the attempt limit the job becomes `failed`.
Transient LLM errors (timeouts, 429, 5xx, malformed structured output) use
bounded exponential backoff inside the active Taskiq task; permanent document
errors and 4xx configuration errors fail without automatic retries.

Delivery is **at least once**, not exactly once: a crash after the model response
but before the DB commit may repeat an LLM request. Card storage is idempotent.
S3 and PostgreSQL are not one transaction: a failed submission can leave an orphan
object. The Taskiq scheduler runs an hourly reconciliation and deletes only objects
under `INGESTION_CLEANUP_PREFIX` that are older than the configured grace period and
have no reference in `document_versions`. Cleanup is bounded by
`INGESTION_CLEANUP_BATCH_SIZE` per run.

Parsing runs in a cancellable subprocess with a time limit. PDF support is
text-layer only: scanned image-only PDFs fail fast with `document_has_no_text`.
OCR engines and their model/system dependencies are deliberately not installed.
Graph projection always calls the
configured embedding endpoint. Extracted text, upload size, model input and LLM
call count are bounded. Large documents use map/reduce rather than silent
truncation.

Scale worker containers independently; there is no fixed worker container name:

```bash
docker compose up -d --scale worker=3
```

`INGESTION_WORKER_PROCESSES` defaults to 1 per container;
`INGESTION_WORKER_CONCURRENCY` defaults to 2 documents per process.
`LLM_MAX_CONCURRENCY` bounds model requests **per process** and defaults to 1 for
the local 9B model. Do not scale workers above 1 on a single 16 GB model host:
more workers cannot add GPU capacity and only increase memory pressure. Prefetch
is bounded and messages are acknowledged after execution.
Leases and claims remain in PostgreSQL to fence duplicate deliveries. Changing
queue capacity requires a new `INGESTION_QUEUE_NAME`, because RabbitMQ queue
arguments are immutable. High availability also needs replicated RabbitMQ,
PostgreSQL and S3; this Compose configuration is a single-machine development setup.

### Tests

```bash
uv run pytest
# Real migrations/concurrency tests in a temporary, isolated PostgreSQL schema:
COWO_TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost:55433/database \
  uv run pytest backend/tests/test_ingestion_postgres.py -q
```

For an end-to-end check without a real model, explicitly opt into the test stub:

```bash
docker compose -f docker-compose.yaml -f backend/tests/compose.ingestion-test.yaml up -d --scale worker=2
docker compose exec -T app python -m tests.fixtures.run_ingestion_smoke
# Restore the real configuration and remove the test-only service:
docker compose up -d --remove-orphans
```

The stub returns a visibly labelled synthetic card. Never use the test override
for real documents. The smoke script removes only the test documents it created.

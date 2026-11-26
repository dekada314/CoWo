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

Set these values in `.env` before submitting documents:

```dotenv
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL_ANALYST=your-installed-model-name
LLM_MODEL_RESPONDER=
LLM_MODEL_EMBEDDING=intfloat/multilingual-e5-small
LLM_API_KEY=
```

For a temporary OpenAI-backed run, use `https://api.openai.com/v1`, a chat model,
`text-embedding-3-small`, and set `LLM_EMBEDDING_DIMENSIONS=384`. Use a separate
`FALKORDB_GRAPH_NAME` when switching embedding providers so vectors from different
models are never compared in the same semantic space.

Google AI Studio keys work through the Gemini OpenAI-compatible endpoint at
`https://generativelanguage.googleapis.com/v1beta/openai`. A text-only setup can
use `gemini-2.5-flash` and `gemini-embedding-001` with a 3072-dimensional FalkorDB
index. Keep a separate graph name for this embedding space as well.

Use the actual port and model name of your local OpenAI-compatible server.
The endpoint must accept `POST /v1/chat/completions`, `POST /v1/embeddings`,
JSON-object chat responses and the standard OpenAI-compatible parameters. The
embedding endpoint must serve the model named by `LLM_MODEL_EMBEDDING`; the default
`multilingual-e5-small` configuration uses 384-dimensional vectors. The local
server must accept connections from Docker; `localhost` inside a worker means the
worker itself. `host.docker.internal` is configured for Docker Desktop and Linux.
Document ingestion returns 503 until the analyst and embedding model names are
set. `LLM_MODEL_RESPONDER` is optional and falls back to `LLM_MODEL_ANALYST`. No
external/cloud model is selected.

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
Hovering or selecting a concept loads its owned PostgreSQL cards on demand.

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

The document version and job are committed together. The job row also serves as
a durable outbox: a separate dispatcher polls with `FOR UPDATE SKIP LOCKED` and
publishes only the job ID to a dedicated durable RabbitMQ queue. The API
does not need a live broker to accept an upload. A failed/ambiguous publish is
retried after the dispatch visibility interval. The queue has a maximum length
and message TTL to bound repeated deliveries while workers are unavailable;
PostgreSQL remains the source of truth and reissues unclaimed work.

Workers use short database transactions, atomic claims, lease tokens and
heartbeats. Only the current lease holder can project and commit a card. Graph
writes use stable identifiers and `MERGE`, so repeated delivery updates the same
projection. The PostgreSQL card and completed job status are committed in one
transaction. A crashed
worker's lease expires and the dispatcher reissues the job. After the attempt
limit the job becomes `failed`. Transient LLM errors (timeouts, 429, 5xx, malformed
structured output) use bounded exponential backoff; permanent document errors
and 4xx configuration errors fail without automatic retries.

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
`LLM_MAX_CONCURRENCY` bounds model requests **per process**, so 3 replicas with
1 process and a limit of 2 can make up to 6 model requests simultaneously.
Size this to your local model server's capacity; more workers cannot add GPU
capacity. Prefetch is bounded and messages are acknowledged after execution.
Dispatcher replicas can also be scaled; leases and claims are shared through DB.
Changing queue TTL/capacity requires a new `INGESTION_QUEUE_NAME`, because RabbitMQ
queue arguments are immutable. High availability also needs replicated RabbitMQ,
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

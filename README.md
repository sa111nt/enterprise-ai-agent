# Enterprise AI Agent - Corporate HR Assistant (RAG + LangGraph)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi\&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql\&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis\&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-1.12-DC244C)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker\&logoColor=white)

A FastAPI backend for a conversational HR assistant - the kind of thing an employee could ask "how many vacation days do I have left" or "what's the onboarding process for a new hire." Underneath it's a LangGraph ReAct agent with five tools: some query Postgres directly for structured employee and department data, one does vector search over ingested HR policy documents. Responses stream to the client over SSE. Conversation history is kept per-thread in Postgres, and a Redis-backed semantic cache skips the LLM call entirely when a question is close enough to one already answered.

## Tech Stack

| Layer              | Technology                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| Language / Runtime | Python 3.12                                                                                            |
| API framework      | FastAPI, Uvicorn, SSE (`sse-starlette`)                                                                |
| Database           | PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic                                                         |
| Cache              | Redis 7                                                                                                |
| Vector store       | Qdrant                                                                                                 |
| AI / Orchestration | LangChain, LangGraph (prebuilt ReAct agent executor), OpenAI (`gpt-4o-mini`, `text-embedding-3-small`) |
| Auth               | JWT (`PyJWT`), Argon2 password hashing (`pwdlib`)                                                      |
| Testing            | pytest, pytest-asyncio, httpx (ASGI transport), in-memory SQLite                                       |
| Infra              | Docker, Docker Compose                                                                                 |
| Linting            | Ruff                                                                                                   |

## Architecture & Key Design Decisions

### Agentic Framework & State Management

The agent orchestrates reasoning and tool execution using **LangGraph**. The core engineering effort focused on defining strict, Pydantic-validated tool schemas with detailed docstrings, which strictly guide the model's tool selection, and designing a robust state architecture.

Conversation history and agent state are persistently tracked in PostgreSQL using `AsyncPostgresSaver`. This checkpointing guarantees that multi-turn conversations survive server restarts, providing a reliable memory layer keyed by `thread_id`.

### Thread isolation

Each conversation thread is persisted in PostgreSQL and owned by a specific employee. The API validates thread ownership before execution, preventing users from accessing another employee's conversation state.

### Tool-level authorization

Sensitive tools enforce authorization independently of the LLM. Employees can access only their own personal and onboarding data, while admins may query other employees. Access checks are performed inside the tools using the authenticated employee identity and role passed through the agent runtime configuration.

### RAG pipeline

PDFs are loaded page by page (`PyPDFLoader`), split with a recursive character splitter (1000 characters, 200 overlap), embedded with OpenAI's `text-embedding-3-small` (1536 dimensions), and stored in a Qdrant collection using cosine distance. At query time, retrieval pulls the top 5 chunks above a 0.7 similarity score, and each result comes back with its source document's title and page number so the agent can cite where an answer came from instead of just asserting it.

### The semantic cache, and why personal data never gets cached

Every incoming question is embedded and checked against cached query embeddings in Redis before the agent even runs, a cosine similarity above 0.95 counts as a hit, with a 24-hour TTL. To prevent personal data from leaking between users, responses are not cached if the question requires calling sensitive tools like `employee_lookup` or `onboarding_status`.

The lookup itself is a full `SCAN` over every `sem_cache:*` key, followed by a brute-force cosine comparison against each one - O(n) per query. That's fine at the scale this runs at now. Past a few thousand cached entries it would need a real ANN index, most likely a dedicated Qdrant collection, instead of a linear scan.

### Streaming

`/agent/chat` streams over SSE with five event types - `token`, `tool_start`, `tool_end`, `cache_hit`, and `done` - so a frontend can show something like "agent is calling search_regulations" instead of leaving the user staring at a blank spinner.

### Auth

Access tokens last 15 minutes and refresh tokens 7 days, with passwords hashed using Argon2. Both token types include a unique `jti` identifier and can be revoked server-side through a Redis blacklist. Logout invalidates both the access and refresh token until their natural expiration. Two roles are supported: `employee` and `admin`, with document upload locked to admins only.

### Rate limiting

`/agent/chat` is protected by a Redis-backed per-user rate limiter allowing 10 requests per minute, preventing unbounded LLM usage from a single account.

## Project Structure

```text
enterprise-ai-agent/
├── alembic/                     # DB migrations
├── app/
│   ├── agent/                   # LangGraph ReAct agent
│   │   ├── graph.py             # agent compilation, Postgres checkpointer
│   │   ├── prompts.py           # system prompt
│   │   ├── state.py             # agent state schema
│   │   └── tools/               # 5 domain tools (SQL + vector search)
│   ├── api/routers/             # auth, documents, agent (SSE)
│   ├── core/                    # db / redis / qdrant clients, JWT + hashing
│   ├── models/                  # SQLAlchemy ORM models
│   ├── rag/                     # ingestion, embeddings, retriever, semantic cache
│   ├── schemas/                 # Pydantic request/response models
│   ├── services/                # business logic layer
│   ├── config.py
│   └── main.py
├── scripts/seed.py              # dev data seeding
├── tests/{unit,integration}/
├── docker-compose.yaml          # postgres + redis + qdrant + api
└── Dockerfile
```

## Getting Started

### Docker (recommended)

```bash
git clone https://github.com/sa111nt/enterprise-ai-agent.git
cd enterprise-ai-agent
cp .env.example .env
# edit .env: set OPENAI_API_KEY and a real JWT_SECRET_KEY
docker compose up --build
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`. Migrations run automatically on container start (`alembic upgrade head`).

Optional: seed sample departments, employees, and onboarding tasks:

```bash
docker compose exec api python scripts/seed.py
```

### Local (without Docker)

Requires a running PostgreSQL, Redis, and Qdrant instance reachable via the URLs in `.env`.

```bash
pip install -r requirements.txt
cp .env.example .env   # edit values to point at your local services
alembic upgrade head
uvicorn app.main:app --reload
```

## Environment Variables

| Variable                                     | Required | Default                    | Description                                         |
| -------------------------------------------- | -------- | -------------------------- | --------------------------------------------------- |
| `DATABASE_URL`                               | yes      | -                          | Async PostgreSQL DSN (`postgresql+asyncpg://...`)   |
| `REDIS_URL`                                  | no       | `redis://localhost:6379/0` | Semantic cache backend                              |
| `QDRANT_HOST` / `QDRANT_PORT`                | no       | `localhost` / `6333`       | Vector store connection                             |
| `QDRANT_COLLECTION`                          | no       | `company_docs`             | Vector collection name                              |
| `OPENAI_API_KEY`                             | yes      | -                          | Used for chat completions and embeddings            |
| `OPENAI_MODEL`                               | no       | `gpt-4o-mini`              | Chat model                                          |
| `OPENAI_EMBEDDING_MODEL`                     | no       | `text-embedding-3-small`   | Embedding model                                     |
| `JWT_SECRET_KEY`                             | yes      | -                          | Sign this with a real secret, not the example value |
| `ACCESS_TOKEN_EXPIRE_MINUTES`                | no       | `15`                       |                                                     |
| `REFRESH_TOKEN_EXPIRE_DAYS`                  | no       | `7`                        |                                                     |
| `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` | no       | `false` / -                | Optional LangSmith tracing                          |

## API Overview

Full interactive documentation is generated automatically by FastAPI and served at `/docs` once the app is running - that's the source of truth for request/response schemas. Primary endpoints:

| Method | Path                       | Auth     | Description                                           |
| ------ | -------------------------- | -------- | ----------------------------------------------------- |
| `GET`  | `/health`                  | -        | Liveness/version check                                |
| `POST` | `/api/v1/auth/register`    | -        | Create an employee account                            |
| `POST` | `/api/v1/auth/login`       | -        | OAuth2 password flow, returns access + refresh tokens |
| `POST` | `/api/v1/auth/refresh`     | -        | Exchange a refresh token for a new pair               |
| `POST` | `/api/v1/auth/logout`      | employee | Revoke the current access and refresh tokens          |
| `GET`  | `/api/v1/auth/me`          | employee | Current authenticated profile                         |
| `POST` | `/api/v1/documents/upload` | admin    | Upload a PDF for RAG ingestion                        |
| `GET`  | `/api/v1/documents/`       | employee | List indexed documents                                |
| `POST` | `/api/v1/agent/chat`       | employee | SSE stream - chat with the AI HR assistant            |

## Testing

```bash
pytest
```

Tests run against an in-memory SQLite database through `httpx`'s ASGI transport, so nothing external needs to be running to execute the suite. Unit tests cover the Pydantic schemas and JWT/password security. Integration tests cover authentication, document upload, the health endpoint, thread ownership, agent streaming, semantic cache behavior, personal-data cache exclusion, and thread isolation.

A separate agent evaluation pipeline runs a fixed evaluation dataset and checks expected tool selection and answer correctness using structured LLM judging.

For the evaluation dataset, examples include onboarding status, employee lookup, and HR policy questions, with the expected tool and expected answer properties defined explicitly.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

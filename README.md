# iWebify — AI App Compiler

> Natural language in, validated executable applications out.

iWebify is a **compiler for software generation** — not a code generator. It uses a metadata-driven, compiler-mediated architecture to translate natural language descriptions into fully validated application schemas and working previews.

## What Makes iWebify Different

| Feature | Typical AI Builders | iWebify |
|---|---|---|
| Architecture | One-shot LLM generation | 9-stage compiler pipeline |
| Validation | Hope-based (pray it works) | Cross-layer static analysis + smoke tests |
| Hallucination Control | None | Context isolation + unidirectional repair |
| Transparency | Black box | Every decision visible via SSE streaming |
| Output | Raw code (often broken) | Validated schemas + working preview |

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────────────────────────┐
│   Stage 1   │    │   Stage 2    │    │        Stage 3 (Sequential)         │
│   Intent    │───▶│   System     │───▶│  DB → API → Auth → Logic → UI      │
│ Extraction  │    │   Design     │    │   (each gets ONLY predecessors)     │
└─────────────┘    └──────────────┘    └──────────────┬──────────────────────┘
                                                      │
                                                      ▼
                                        ┌─────────────────────────┐
                                        │      Stage 4            │
                                        │  Cross-Layer Validation │◀──┐
                                        │   (Pure Python, $0)     │   │
                                        └──────────┬──────────────┘   │
                                                   │                  │
                                          Pass?    │    Fail?         │
                                            │      │      │           │
                                            ▼      │      ▼           │
                                     ┌──────────┐  │  ┌──────────┐   │
                                     │ Stage 5  │  │  │ Targeted │   │
                                     │Execution │  │  │  Repair  │───┘
                                     │(DB+HTML) │  │  │(downstream│
                                     └──────────┘  │  │  only)    │
                                                   │  └──────────┘
                                                   │
```

### Key Architectural Decisions

1. **Sequential Dependency Injection**: Schemas are generated in strict order (DB → API → Auth → Business → UI). Each layer receives ONLY its direct predecessors as context — preventing context contamination.

2. **Unidirectional Repair**: When validation fails, repair only flows downstream. The DB schema is NEVER modified — it is the single source of truth.

3. **Cross-Layer Validation**: Pure Python validators (zero LLM cost) check every reference across layers — API endpoints must reference real DB tables, UI components must reference real API endpoints, auth roles must match.

4. **Execution Awareness**: The pipeline doesn't just generate schemas — it builds a real SQLite database, seeds sample data, runs smoke tests, and generates a working HTML preview.

## Tech Stack

| Component | Technology |
|---|---|
| Pipeline Orchestration | LangGraph (StateGraph) |
| LLM | Google Gemini 2.0 Flash (structured output) |
| Schema Contracts | Pydantic v2 |
| Backend | FastAPI + SSE (sse-starlette) |
| Database | SQLite (per-session) |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Docker → HuggingFace Spaces |

## Project Structure

```
iwebify/
├── src/
│   ├── schemas/           # 7 Pydantic schema contracts
│   │   ├── intent.py      # Stage 1 output — IntentIR
│   │   ├── design.py      # Stage 2 output — SystemDesign
│   │   ├── database.py    # Stage 3a — DBSchema (FOUNDATION)
│   │   ├── api.py         # Stage 3b — APISchema
│   │   ├── auth.py        # Stage 3c — AuthSchema
│   │   ├── business.py    # Stage 3d — BusinessLogicSchema
│   │   └── ui.py          # Stage 3e — UISchema
│   ├── pipeline/
│   │   ├── state.py       # PipelineState TypedDict
│   │   ├── graph.py       # LangGraph wiring
│   │   └── nodes/         # Pipeline stage implementations
│   │       ├── intent_extraction.py
│   │       ├── system_design.py
│   │       ├── schema_generation.py  # 5 sequential generators
│   │       ├── validation.py
│   │       ├── repair.py             # Unidirectional repair engine
│   │       └── execution.py
│   ├── validation/
│   │   ├── cross_layer.py # Pure Python cross-layer checks
│   │   └── errors.py      # Error taxonomy
│   ├── execution/
│   │   ├── db_builder.py  # SQLite DDL generation + smoke tests
│   │   └── preview_builder.py  # HTML preview generation
│   ├── api/
│   │   ├── routes.py      # FastAPI endpoints + SSE streaming
│   │   └── run_store.py   # In-memory session store
│   ├── evaluation/
│   │   ├── runner.py      # Batch evaluation script
│   │   └── prompts/
│   │       ├── real.json       # 10 real-world product prompts
│   │       └── edge_cases.json # 10 adversarial/edge case prompts
│   ├── config.py
│   └── main.py
├── frontend/
│   └── index.html         # Premium single-page compiler UI
├── tests/
├── Dockerfile
├── pyproject.toml
└── .env.example
```

## Setup & Run

### 1. Clone and install

```bash
git clone https://github.com/BEAST04289/iWEBIFY.git
cd iWEBIFY
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Run locally

```bash
python -m src.main
# Server starts at http://localhost:7860
```

### 4. Run evaluation

```bash
# Run all 10 real-world prompts
python -m src.evaluation.runner --suite real

# Run edge cases
python -m src.evaluation.runner --suite edge_cases

# Run specific prompts
python -m src.evaluation.runner --suite all --ids crm_basic vague_app

# Save results to JSON
python -m src.evaluation.runner --suite all --output results.json
```

### 5. Docker

```bash
docker build -t iwebify .
docker run -p 7860:7860 -e GEMINI_API_KEY=your_key iwebify
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/generate` | Start a compilation pipeline |
| `GET` | `/api/stream/{session_id}` | SSE event stream for real-time progress |
| `GET` | `/api/result/{session_id}` | Full result once pipeline completes |
| `GET` | `/preview/{session_id}` | Serve generated HTML preview |
| `GET` | `/api/download/{session_id}` | Download schemas as JSON |
| `GET` | `/health` | Health check |

## Validation Checks

The cross-layer validator runs **5 categories** of checks with zero LLM cost:

1. **DB Self-Consistency**: Primary keys exist, FKs reference real tables/columns, no circular deps
2. **API → DB**: Every endpoint's `db_table` is a real table, request/response fields match columns
3. **Auth → API + DB**: Protected/public endpoints are real API paths, permission resources are real tables
4. **Business → API + Auth**: Affected endpoints exist, roles are consistent
5. **UI → API + Auth**: Component `api_endpoint` is a real path, `allowed_roles` exist, fields match response

## Schema Contracts

Every schema uses Pydantic v2 with `Literal` types (not Enums) for Gemini's `response_schema`:

- **IntentIR**: Structured understanding of user requirements (entities, features, roles, assumptions)
- **SystemDesign**: Architectural blueprint (relationships, data flows, auth strategy)
- **DBSchema**: SQLite table definitions (columns, types, FKs, indexes)
- **APISchema**: REST endpoint definitions (paths, methods, request/response fields)
- **AuthSchema**: RBAC configuration (roles, permissions, protected routes)
- **BusinessLogicSchema**: Business rules and automations (gates, validations, notifications)
- **UISchema**: Frontend layout (pages, components, navigation)

## License

MIT
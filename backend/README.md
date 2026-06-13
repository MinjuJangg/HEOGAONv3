# Heogaon Flow V2 Backend

FastAPI backend for the planning-document flow:

```text
INTAKE -> NEEDS_INFO -> DIAGNOSIS -> CONFIRM_UNDERSTANDING
-> DOCUMENTS -> DASHBOARD -> SUBMITTED
```

## Responsibilities

- Frontend renders only the `view.type` returned by the API.
- Backend owns case state, step routing, question loop limits, document ordering, and submission routing.
- AI is optional and only handles structured extraction, summaries, and judgement wording.
- GraphRAG is the primary domain expansion boundary for question candidates, documents, and evidence. Catalog constants are the demo fallback.

## Structure

```text
app/
  core/config.py                 environment settings
  integrations/llm_client.py     GMS JSON LLM boundary
  schemas/ai.py                  validated AI output contracts
  repositories/case_repository.py in-memory case store, DB-replaceable
  data/catalog.py                MVP question/document rule seeds
  services/
    graph_rag_service.py         GraphRAG retrieve boundary and response normalizer
    flow_service.py              state-machine orchestration
    intake_agent.py              natural language -> slots
    question_planner.py          backend-owned question loop
    document_service.py          checklist generation/completion
    view_builder.py              backend result -> frontend envelope
    output_guard.py              no definitive/legal wording, PII masking
  flow.py                        thin compatibility facade for existing routes
```

## Env Setup

Use the root `.env` file for both frontend and backend settings. The backend
loads `../.env` when it starts from the `backend` directory.

For AI/GMS, set:

```bash
export LLM_API_KEY="..."
export LLM_MODEL="gpt-4.1"
export LLM_BASE_URL="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
```

`GMS_API_KEY` is also accepted as a fallback for `LLM_API_KEY`.

If no API key is present, the service continues with deterministic rule fallback for demos.

## GraphRAG Setup

To enable remote GraphRAG, add these values to the root `.env`:

```bash
ENABLE_GRAPH_RAG=true
GRAPH_RAG_BASE_URL="http://127.0.0.1:8200"
GRAPH_RAG_API_KEY=""
GRAPH_RAG_TIMEOUT_SECONDS=8
```

The backend calls `POST {GRAPH_RAG_BASE_URL}/retrieve` with `kind` set to `questions`, `documents`, `inquiries`, or `evidence`.

If the remote GraphRAG service is disabled, unreachable, or returns an invalid shape, the backend first tries the checked-in local graph package at `minju/graph/output/final_graph` and falls back to `minju_new/graph/output/final_graph` for older checkouts. If neither local graph can produce a valid response, the affected area falls back to `app/data/catalog.py`. The state machine, retry limits, and next-screen routing stay in FastAPI.

## Run

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 4100
```

## Verify

```bash
python3 -m py_compile $(find app -type f -name '*.py' | sort)
```

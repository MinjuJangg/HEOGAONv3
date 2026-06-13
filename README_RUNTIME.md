# HEOGAONV3 Runtime

This folder is a clean local runtime copy for the merged HEOGAONV3 app.

## What Is Included

- `app`, `src`, `public`: Next.js frontend
- `backend`: FastAPI flow backend
- `minju/intake`, `minju/decision_engine`: intake and judgement logic
- `minju/document_issue_guide`: document metadata DB
- `minju/department_mapping`: Seoul department/document routing DB
- `minju/graph/output/final_graph`: local GraphRAG fallback graph

Large development outputs, old scenario reports, and generated caches are intentionally excluded.

## Env File

Use one local env file at the project root:

- `.env`: frontend, backend, GMS, public API, Kakao, CORS, and LOCALDATA settings

The backend reads the root `.env`, and Next.js also reads the same root `.env`
during build/start. Old split env files such as `.env.local`, `.env.hegaon.ai`,
`.env.hegaon.public`, `.env.hegaon.local`, and `backend/.env` are no longer needed
for this runtime folder.

Required keys include:

```env
NEXT_PUBLIC_HEOGAON_API_BASE_URL=http://127.0.0.1:4100
NEXT_PUBLIC_KAKAO_JS_KEY=
NEXT_PUBLIC_DATA_GO_KR_SERVICE_KEY=
LLM_API_KEY=
LLM_MODEL=gpt-5.5
LLM_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
GMS_API_KEY=
GMS_MODEL=gpt-5.5
GMS_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
JUSO_API_KEY=
DATA_GO_KR_SERVICE_KEY=
KAKAO_REST_API_KEY=
SEOUL_LOCALDATA_INDEX=
CORS_ALLOWED_ORIGINS=http://127.0.0.1:3103,http://localhost:3103
```

`NEXT_PUBLIC_KAKAO_JS_KEY` must be the Kakao Developers JavaScript key, not the REST API key. Register the local web domain you run, for example `http://127.0.0.1:3103`, in the Kakao Developers app settings.

Do not commit real env files.

## Run

```powershell
.\RUN_HEOGAONV3.ps1
```

Backend: `http://127.0.0.1:4100`

Frontend: `http://127.0.0.1:3103`

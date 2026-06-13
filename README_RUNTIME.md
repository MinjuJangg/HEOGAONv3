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

## Env Files

- `backend/.env`: backend runtime env
- `.env.hegaon.ai`: minju/GMS script env
- `.env.hegaon.public`: public data API env
- `.env.local`: frontend API URL

Do not commit real env files.

## Run

```powershell
.\RUN_HEOGAONV3.ps1
```

Backend: `http://127.0.0.1:4100`

Frontend: `http://127.0.0.1:3103`

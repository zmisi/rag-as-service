# rag-web

Next.js frontend for rag-as-service.

## Setup

```bash
cd apps/web
npm install
cp ../../.env.example .env.local   # optional; set API_BACKEND_URL
```

## Run

```bash
npm run dev
```

Browser calls same-origin `/backend/*`; Next rewrites to FastAPI (`API_BACKEND_URL`, default `http://localhost:8000`).

## E2E

```bash
npx playwright install
npm run test:e2e
```

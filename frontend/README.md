# SaaSShadow dashboard (frontend)

Next.js dashboard for SaaSShadow Community Edition.

## Run locally

Start the API from the project root (`uvicorn app.main:app --reload`), then:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. API calls default to http://localhost:8000.

Optional: set `NEXT_PUBLIC_API_URL` in `.env.local` to point at another host.

## Docker

From the project root:

```bash
docker compose up --build
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Development server |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | ESLint |

# Contributing to SaaSShadow

Thank you for contributing to SaaSShadow Community Edition.

## Development setup

Backend API:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend dashboard:

```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
pytest tests/ -v
python scripts/community_smoke.py
cd frontend && npm run build
```

## Pull requests

- Keep changes focused and include tests for behavior changes.
- Ensure `docker compose up --build` remains a valid quick-start path.
- Do not commit secrets, `.env` files, build output (`.next/`), or `data/` artifacts.
- Update documentation when changing user-visible behavior.
- Scope changes to Community Edition features only. Do not add commercial-only
  product surfaces to this repository.

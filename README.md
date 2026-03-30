# MealRiot API

Backend service for MealRiot — a nutrition tracking app with social and gamification features.

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy (async) with PostgreSQL (asyncpg)
- Alembic (migrations)
- Pydantic
- Supabase Auth (JWT validation via JWKS)
- OpenAI API (food parsing, daily insights)

## Prerequisites

- Python 3.12+
- PostgreSQL

## Getting Started

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure environment variables:

```bash
cp .env.example .env
```

Fill in `.env`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
OPENAI_API_KEY=sk-...
ADMIN_EMAIL=your@email.com
FRONTEND_URL=http://localhost:5173
INTERNAL_SECRET=your-random-secret
```

Run database migrations:

```bash
alembic upgrade head
```

Start the dev server:

```bash
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. Interactive docs available at `http://localhost:8000/docs`.

## Project Structure

```
app/
├── api/          # Route handlers (one module per domain)
├── models/       # SQLAlchemy ORM models
├── schemas/      # Pydantic request/response models
├── services/     # Business logic (food parsing, stats, AI chat)
├── middleware/    # Auth, rate limiting
└── core/         # App configuration
```

## Testing

Run all tests:

```bash
pytest
```

Run a single test file:

```bash
pytest tests/test_entries.py
```

Run a specific test:

```bash
pytest tests/test_entries.py -k test_create_entry
```

Tests use SQLite in-memory — no database setup required.

## Related

- [MealRiot Web](../mealriot-web) — Frontend application

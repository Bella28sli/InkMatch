# InkMatchAPI (FastAPI)

## Run
1) Create venv and install deps:
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2) Start server:
```bash
uvicorn app.main:app --reload
```

## Config
Create `.env` (recommended):
```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/inkmatch_db
JWT_SECRET_KEY=CHANGE_ME
ACCESS_TOKEN_TTL_MINUTES=30
REFRESH_TOKEN_TTL_DAYS=60
```

## Migrations (Alembic)
1) Generate initial migration:
```bash
alembic revision --autogenerate -m "init"
```
2) Apply migrations:
```bash
alembic upgrade head
```

## Seed core data (styles/tags)
```bash
python -m app.scripts.seed_core
```

# Database Migrations (Alembic)

This project uses Alembic for schema migrations. The Alembic config is already
wired to `DATABASE_URL` via `alembic/env.py`.

## Create a new migration

1) Make model/schema changes.
2) Generate a revision:

```bash
alembic revision -m "describe change" --autogenerate
```

3) Review the generated file in `alembic/versions/` and adjust if needed.

## Apply migrations locally

```bash
alembic upgrade head
```

## Check current revision

```bash
alembic current
alembic heads
```

`alembic current` should match the single head in normal operation.

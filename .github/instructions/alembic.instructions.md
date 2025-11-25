---
applyTo: "alembic/**/*"
---

# Database Migration Guidelines

## Creating Migrations
- Use `alembic revision --autogenerate -m "description"` to generate migrations.
- Review auto-generated migrations before committing.
- Always test migrations with `alembic upgrade head` and `alembic downgrade -1`.

## Async Engine
- `alembic/env.py` uses async SQLAlchemy engine.
- Migrations run in a synchronous context but connect to async DB.

## Naming Conventions
- Migration files: `versions/<timestamp>_<description>.py`
- Use descriptive revision messages.

## Testing Migrations
- Run `make db-upgrade` to apply pending migrations.
- Run `make db-downgrade` to rollback last migration.
- Ensure both upgrade and downgrade paths work.

## Best Practices
- Never modify existing migrations in production.
- Create new migrations for schema changes.
- Include both `upgrade()` and `downgrade()` functions.

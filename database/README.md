# Database migrations

The backend currently uses SQLAlchemy `create_all()` for a fresh local database. It does not modify tables that already exist, so run the migration below when the backend reports a missing column or table.

From the repository root, with the PostgreSQL container running:

```sh
docker exec -i trust_pass_db psql -U postgres -d trust_pass_db < database/migrations/001_application_pipeline.sql
```

The migration is safe to run more than once. It creates the application tables if they are missing and adds the pipeline columns required by the backend if they are absent.

Run the migrations in order:

```sh
docker exec -i trust_pass_db psql -U postgres -d trust_pass_db < database/migrations/002_officer_decisions.sql
docker exec -i trust_pass_db psql -U postgres -d trust_pass_db < database/migrations/003_officer_auth.sql
```

Create a development officer interactively from the backend directory. The password is entered without being written to the repository:

```sh
PYTHONPATH=. .venv/bin/python scripts/create_officer.py officer@example.com "Development Officer"
```

The officer queue and decision endpoints require the JWT returned by `/api/v1/auth/login`.

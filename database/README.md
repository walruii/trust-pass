# Database migrations

The backend currently uses SQLAlchemy `create_all()` for a fresh local database. It does not modify tables that already exist, so run the migration below when the backend reports a missing column or table.

From the repository root, with the PostgreSQL container running:

```sh
docker exec -i trust_pass_db psql -U postgres -d trust_pass_db < database/migrations/001_application_pipeline.sql
```

The migration is safe to run more than once. It creates the application tables if they are missing and adds the pipeline columns required by the backend if they are absent.

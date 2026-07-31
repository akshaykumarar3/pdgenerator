# Release & Deployment Checklist (v8.7)

This checklist outlines the procedures for deploying the Clinical Data Generator with the new hybrid storage backend (JSON & PostgreSQL) to production.

---

## 1. Installation Steps

1. **Verify Python Environment**: Python 3.10+ is required.
2. **Clone / Pull codebase**: Pull the latest code on the `refactor` branch.
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Ensure psycopg2 compatibility**: If running on production systems, ensure PostgreSQL client library (`libpq`) is installed on the host system.

---

## 2. Environment Setup

Configure the environment variables in `cred/.env`:

1. **Backend Configuration**:
   - Set `PATIENT_STORAGE_BACKEND=postgres` to activate the PostgreSQL database repository.
2. **PostgreSQL Credentials**:
   ```ini
   DB_HOST=your_postgres_host_here
   DB_PORT=5432
   DB_NAME=your_db_name_here
   DB_USER=your_db_user_here
   DB_PASSWORD=your_postgres_password_here
   DB_SSL_MODE=require
   DB_CHANNEL_BINDING=require
   DB_SCHEMA=pdgenerator
   ```
3. **API Configuration**:
   - Verify `API_PORT=410` (or your preferred production port).

---

## 3. Database Initialization

The PostgreSQL persistence layer is designed to self-initialize.
* On first query or operation, the `PostgresPatientRepository` executes the DDL script in `src/core/schema.sql` automatically.
* Schema validation prevents invalid schema names from causing SQL injection: schema name must match regex `^[a-zA-Z_][a-zA-Z0-9_]*$`.

---

## 4. Migration Steps (JSON → PostgreSQL)

To migrate all current local patient records to the PostgreSQL database, execute:

```bash
# Recommended command using virtual environment python:
./venv/bin/python3 migrate_data.py --direction json_to_db --strategy update
```

### Conflict Resolution Strategies (`--strategy`)
* `update` (Default): Overwrite existing records in destination if a conflict arises.
* `skip`: Skip migrating that record, leaving the destination data untouched.
* `fail`: Immediately abort the migration process if any conflicts are detected.

---

## 5. Rollback Procedure

In the event of a database failure or emergency rollback:

1. **Extract PostgreSQL data to JSON**:
   ```bash
   ./venv/bin/python3 migrate_data.py --direction db_to_json --strategy update
   ```
   This ensures any new patient records generated during PostgreSQL deployment are synced back into the local `src/core/patients_db.json`.
2. **Change Backend**:
   - In `cred/.env`, set `PATIENT_STORAGE_BACKEND=json`.
3. **Restart API Server / Application**: The application will resume operations using local JSON files immediately with zero downtime.

---

## 6. Backup Recommendations

* **PostgreSQL Backup**:
  Schedule a daily cron job to back up the schema using `pg_dump`:
  ```bash
  pg_dump -h <host> -U <user> -d <dbname> -n <schema_name> > backup_schema.sql
  ```
* **JSON Database Backup**:
  Keep the gitignored `src/core/patients_db.json` backed up periodically or copied to an offline storage volume before running migrations.

---

## 7. Post-Deployment Verification

Execute the following checks immediately after deployment:

1. **Verify Connection & Tests**:
   ```bash
   ./venv/bin/pytest
   ```
2. **Ping API endpoints**:
   ```bash
   curl -I http://localhost:410/api/patients
   ```
3. **Verify Database Table**:
   Connect via `psql` or database manager and check that the table `<schema_name>.patients` exists with populated records.

---

## 8. Known Limitations

* **Neon DB Cold Start**: If using Neon PostgreSQL serverless instances, first connections after inactivity may experience 3-5 seconds latency.
* **psycopg2 Compilation**: When building on Alpine Linux or specific light containers, ensure `build-base` and `postgresql-dev` packages are present to compile dependency binaries, or use `psycopg2-binary`.

---

## 9. Future Enhancements

* **Connection Pooling**: Implement `psycopg2.pool.SimpleConnectionPool` or integration with PgBouncer.
* **Schema Migration Engine**: Integrate Alembic for tracking version changes in table structures.
* **Cache Layer**: An in-memory name cache has been implemented (`src/core/name_cache.py`). For further performance improvements, consider a more robust solution like Redis.

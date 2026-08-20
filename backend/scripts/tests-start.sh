#! /usr/bin/env bash
set -e
set -x

# The suite deletes every row of soccer data (see tests/conftest.py), so it must
# never point at the development database. Everything below exists to guarantee
# that; conftest refuses to run if this is not honoured.
export POSTGRES_DB="${POSTGRES_DB_TEST:-${POSTGRES_DB:-app}_test}"

# CREATE DATABASE cannot run inside a transaction, hence autocommit. Connects to
# the "postgres" maintenance DB because the target may not exist yet.
python - <<'PY'
import psycopg
from app.core.config import settings

target = settings.POSTGRES_DB
admin = (
    f"host={settings.POSTGRES_SERVER} port={settings.POSTGRES_PORT} "
    f"user={settings.POSTGRES_USER} password={settings.POSTGRES_PASSWORD} "
    f"dbname=postgres"
)
with psycopg.connect(admin, autocommit=True) as conn:
    exists = conn.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", (target,)
    ).fetchone()
    if not exists:
        conn.execute(f'CREATE DATABASE "{target}"')
        print(f"created test database {target}")
    else:
        print(f"test database {target} already present")
PY

python app/tests_pre_start.py

# Schema comes from migrations, same as production — so a broken migration fails
# the suite rather than being papered over by create_all().
alembic upgrade head

bash scripts/test.sh "$@"

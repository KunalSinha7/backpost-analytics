#! /usr/bin/env bash
set -e
set -x

# The suite deletes every row of soccer data (see tests/conftest.py), so it must
# never point at the development database. Everything below exists to guarantee
# that; conftest refuses to run if this is not honoured.
if [ -n "$DATABASE_URL" ]; then
    case "$DATABASE_URL" in
        *_test) ;;
        *) export DATABASE_URL="${DATABASE_URL}_test" ;;
    esac
fi
export POSTGRES_DB="${POSTGRES_DB_TEST:-${POSTGRES_DB:-app}_test}"

# CREATE DATABASE cannot run inside a transaction, hence autocommit. Connects to
# the "postgres" maintenance DB because the target may not exist yet.
python - <<'PY'
import psycopg
from app.core.config import settings

target = settings.POSTGRES_DB
hosts = settings.DATABASE_URL.hosts() if settings.DATABASE_URL else []
host_info = hosts[0] if hosts else {}
host = host_info.get("host", "localhost")
port = host_info.get("port", 5432) or 5432
user = host_info.get("username", "postgres")
password = host_info.get("password", "")

admin = f"host={host} port={port} user={user} password={password} dbname=postgres"
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

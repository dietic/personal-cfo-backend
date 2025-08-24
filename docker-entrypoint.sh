#!/usr/bin/env sh
set -e

# Preflight: patch existing DB & decide migration strategy
python - <<'PY'
import os, sys
from urllib.parse import urlparse
import psycopg2
url = os.environ.get('DATABASE_URL')
if not url or not url.startswith('postgresql'):
    sys.exit(0)
if url.startswith('postgresql+psycopg2://'):
    url = url.replace('postgresql+psycopg2://','postgresql://',1)
parsed = urlparse(url)
conn = psycopg2.connect(dbname=parsed.path.lstrip('/'), user=parsed.username, password=parsed.password, host=parsed.hostname, port=parsed.port)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT to_regclass('public.users');")
users_exists = cur.fetchone()[0] is not None
cur.execute("SELECT to_regclass('public.alembic_version');")
av_tbl = cur.fetchone()[0]
if users_exists:
    if not av_tbl:
        cur.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num));")
    cur.execute('SELECT COUNT(*) FROM alembic_version;')
    empty = cur.fetchone()[0] == 0
    if empty:
        # We will stamp heads directly later
        # create placeholder to allow stamp
        cur.execute("INSERT INTO alembic_version (version_num) VALUES ('manual_bootstrap') ON CONFLICT DO NOTHING;")
    # Ensure billing columns
    billing_cols = [
        ("plan_tier", "VARCHAR NOT NULL DEFAULT 'free'"),
        ("plan_status", "VARCHAR NOT NULL DEFAULT 'inactive'"),
        ("billing_currency", "VARCHAR NOT NULL DEFAULT 'PEN'"),
        ("current_period_end", "TIMESTAMPTZ NULL"),
        ("cancel_at_period_end", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("provider_customer_id", "VARCHAR NULL"),
        ("provider_subscription_id", "VARCHAR NULL"),
        ("last_payment_status", "VARCHAR NULL"),
    ]
    for name, ddl in billing_cols:
        cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name=%s", (name,))
        if cur.fetchone() is None:
            cur.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl};")
    cur.execute("SELECT 1 FROM pg_class WHERE relname='ix_users_plan_tier';")
    if cur.fetchone() is None:
        cur.execute("CREATE INDEX ix_users_plan_tier ON users(plan_tier);")
    # signal to shell to stamp instead of upgrade
    with open('/tmp/stamp_heads','w') as f: f.write('1')
cur.close(); conn.close()
PY

if [ -f /tmp/stamp_heads ]; then
  echo "[migrate] Existing schema detected; stamping heads to avoid baseline duplication"
  alembic stamp heads || true
else
  alembic upgrade heads
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers

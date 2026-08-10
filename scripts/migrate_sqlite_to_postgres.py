"""One-time data migration: copy all rows from a local SQLite snapshot into
the Postgres database the app will use in production.

Usage:
    venv\\Scripts\\python.exe scripts\\migrate_sqlite_to_postgres.py <path-to-sqlite-db> <postgres-url>

Example:
    venv\\Scripts\\python.exe scripts\\migrate_sqlite_to_postgres.py ^
        "C:\\Users\\safee\\Desktop\\WORk\\Technosys_fam\\resource_platform.db" ^
        "postgresql://user:pass@host/dbname"

The Postgres URL is the "External Database URL" from the Render Postgres
dashboard (Connect tab) -- needed because this runs from your machine, not
from inside Render's network.

Safe to re-run: existing rows in the target tables are wiped and replaced --
do not point this at a Postgres database with data you want to keep alongside
the SQLite data being imported.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Resource, ResourceHistory, Deal, DealHistory, FunnelSnapshot

TABLES_IN_ORDER = [Resource, Deal, ResourceHistory, DealHistory, FunnelSnapshot]


def migrate(sqlite_path: str, postgres_url: str):
    if not os.path.exists(sqlite_path):
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    if postgres_url.startswith("postgres://"):
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)
    if not postgres_url.startswith("postgresql://"):
        raise SystemExit(f"Expected a postgresql:// URL, got: {postgres_url}")

    sqlite_engine = create_engine(f"sqlite:///{os.path.abspath(sqlite_path)}")
    postgres_engine = create_engine(postgres_url)

    SqliteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)

    print(f"Source (SQLite): {sqlite_path}")
    print(f"Target (Postgres): {postgres_url.split('@')[-1]}")  # omit credentials from stdout

    Base.metadata.create_all(postgres_engine)

    src = SqliteSession()
    dst = PostgresSession()

    try:
        for model in TABLES_IN_ORDER:
            rows = src.query(model).all()
            table_name = model.__tablename__

            dst.query(model).delete()

            count = 0
            for row in rows:
                data = {c.name: getattr(row, c.name) for c in model.__table__.columns}
                dst.add(model(**data))
                count += 1

            dst.commit()
            print(f"{table_name}: migrated {count} row(s)")

    finally:
        src.close()
        dst.close()

    print("Migration complete.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)
    migrate(sys.argv[1], sys.argv[2])

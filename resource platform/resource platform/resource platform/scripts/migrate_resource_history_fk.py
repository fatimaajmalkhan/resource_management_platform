"""One-time migration: drop the FK constraint from resource_history.emp_id
so a resource's history (including its "deleted" event) can survive the
resource itself being deleted. SQLite has no ALTER TABLE ... DROP CONSTRAINT,
so this rebuilds the table: rename -> recreate -> copy rows -> drop old.
Idempotent -- safe to run multiple times.

Run with: python scripts\\migrate_resource_history_fk.py"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sqlalchemy import text
from app.db import engine


def main():
    with engine.begin() as conn:
        fk_rows = conn.execute(text("PRAGMA foreign_key_list(resource_history)")).fetchall()
        if not fk_rows:
            print("No FK constraint on resource_history -- already migrated, nothing to do.")
            return

        conn.execute(text("ALTER TABLE resource_history RENAME TO resource_history_old"))
        conn.execute(text("""
            CREATE TABLE resource_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id INTEGER NOT NULL,
                field_name VARCHAR NOT NULL,
                old_value VARCHAR,
                new_value VARCHAR,
                changed_at DATETIME NOT NULL,
                source VARCHAR NOT NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO resource_history (history_id, emp_id, field_name, old_value, new_value, changed_at, source)
            SELECT history_id, emp_id, field_name, old_value, new_value, changed_at, source FROM resource_history_old
        """))
        old_count = conn.execute(text("SELECT COUNT(*) FROM resource_history_old")).scalar()
        new_count = conn.execute(text("SELECT COUNT(*) FROM resource_history")).scalar()
        if old_count != new_count:
            raise RuntimeError(f"Row count mismatch after copy: old={old_count} new={new_count} -- aborting, not dropping old table")
        conn.execute(text("DROP TABLE resource_history_old"))
        print(f"Migrated resource_history: dropped FK constraint, {new_count} row(s) preserved.")


if __name__ == "__main__":
    main()

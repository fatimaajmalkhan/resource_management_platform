"""One-time backfill: canonicalize existing employee_type values that are
typo/case/abbreviation variants of the same category (e.g. "contract" ->
"Contractual", "probation" -> "Probationary"). Logs each correction to
ResourceHistory and best-effort mirrors it to the source Excel file, same as
any other tracked change. Idempotent -- safe to run multiple times.

Run with: python scripts\\normalize_employee_type.py"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.db import get_session
from app.models import Resource
from app.history import log_change
from app.etl import normalize_employee_type, update_resource_in_excel, DB_FIELD_TO_EXCEL_HEADER


def main():
    fixed = 0
    with get_session() as session:
        resources = session.query(Resource).all()
        for r in resources:
            old_value = r.employee_type
            new_value = normalize_employee_type(old_value)
            if new_value == old_value:
                continue

            setattr(r, "employee_type", new_value)
            log_change(session, r.emp_id, "employee_type", old_value, new_value, source="normalize_migration")
            fixed += 1
            print(f"  emp_id {r.emp_id}: {old_value!r} -> {new_value!r}")

            try:
                record = {"emp_id": r.emp_id, **{f: getattr(r, f) for f in DB_FIELD_TO_EXCEL_HEADER}}
                update_resource_in_excel(record)
            except Exception as e:
                print(f"    Excel update failed for emp_id {r.emp_id}: {e}")

        session.commit()
    print(f"Done -- {fixed} resource(s) normalized.")


if __name__ == "__main__":
    main()

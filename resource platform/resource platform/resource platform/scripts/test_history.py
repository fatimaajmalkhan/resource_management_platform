"""Makes one real change and proves it gets logged.
   python scripts\\test_history.py"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import get_session
from app.models import Resource
from app.history import log_change, get_history

with get_session() as session:
    # pick any one resource to test with
    r = session.query(Resource).first()
    print(f"Testing with: {r.resource_name} (currently grade {r.grade})\n")

    old_grade = r.grade
    new_grade = "L3" if old_grade != "L3" else "L2"

    # this is exactly what a real edit (dashboard or sync) would do
    log_change(session, r.emp_id, "grade", old_grade, new_grade, source="manual_test")
    r.grade = new_grade
    session.commit()

    print(f"Changed grade: {old_grade} -> {new_grade}\n")
    print("History for this person now shows:")
    for h in get_history(session, r.emp_id):
        print(f"  {h.field_name}: {h.old_value} -> {h.new_value}  ({h.source}, {h.changed_at})")